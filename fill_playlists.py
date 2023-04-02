#!/usr/bin/env python3.10
import re
from itertools import chain
from pathlib import Path
from subprocess import run
import subprocess
from sys import stderr
from time import sleep
import requests
import json
import yaml
from bs4 import BeautifulSoup
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from typing import NamedTuple, Iterable, Optional, Union
from rich import print
from dotenv import load_dotenv
from download import download


here = Path(__file__).parent
load_dotenv(here / ".env")
spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())


class Track:
    title: str
    artists: set[str]
    youtube_source_video_id: str
    filepath: Path

    def __init__(
        self,
        filepath: Path,
        title: str = "",
        artists: set[str] = set(),
        youtube_source_video_id: Optional[str] = None,
    ) -> None:
        self.title = title
        self.artists = artists
        self.filepath = filepath
        self.artists = set(
            self.artists or self.filepath.name.split("\t")[0].split(", ")
        )
        self.youtube_source_video_id = (
            youtube_source_video_id or self.filepath.name.split("\t")[2]
        )

    @property
    def remixed(self) -> bool:
        return len(self.artists) >= 2 and "remix" in map(str.lower, list(self.title))

    def __str__(self) -> str:
        return f"{', '.join(self.artists)} — {self.title}"

    __repr__ = __str__


def find_file_of_track(library: Iterable[Path], artists: set[str], title: str) -> Path:
    for track in library:
        t_artists_str, t_title, *_ = track.name.split("\t")
        t_title = t_title.replace('∕', '/')
        t_artists = set(t_artists_str.split(', '))
        if title.strip() == t_title.strip():
            return track
    raise KeyError(
        f"No file found in given library ({[f.name for f in library]}) for track {artists}\t{title}"
    )


def from_spotify_playlist(url: str) -> set[Track]:
    tracks_raw = [item["track"] for item in spotify.playlist_tracks(url)["items"]]
    tracks = set()

    for t in tracks_raw:
        title = t["name"]
        artists = set(a["name"] for a in t["artists"])

        try:
            filepath = find_file_of_track(
                [t.filepath for t in all_tracks()], artists=artists, title=title
            )
            tracks.add(Track(filepath=filepath))

        except KeyError:
            print(
                f" [yellow]⚠  Track [bold]{', '.join(artists)} [/]—[bold] {title}[/] not downloaded yet, downloading...",
                file=stderr,
            )
            download((", ".join(artists), title))


    return tracks


class ContainConstraint(NamedTuple):
    set: str = ""  # predefined set to match, e.g. "japanese characters"
    regex: str = ""  # regular expression
    raw: str = ""  # a plain string

    CJK_CHARACTERS = [
        range(ord("\u3300"), ord("\u33ff")),  # compatibility ideographs
        range(ord("\ufe30"), ord("\ufe4f")),  # compatibility ideographs
        range(ord("\uf900"), ord("\ufaff")),  # compatibility ideographs
        range(ord("\U0002F800"), ord("\U0002fa1f")),  # compatibility ideographs
        range(ord("\u3040"), ord("\u309f")),  # Japanese Hiragana
        range(ord("\u30a0"), ord("\u30ff")),  # Japanese Katakana
        range(ord("\u2e80"), ord("\u2eff")),  # cjk radicals supplement
        range(ord("\u4e00"), ord("\u9fff")),
        range(ord("\u3400"), ord("\u4dbf")),
        range(ord("\U00020000"), ord("\U0002a6df")),
        range(ord("\U0002a700"), ord("\U0002b73f")),
        range(ord("\U0002b740"), ord("\U0002b81f")),
        range(ord("\U0002b820"), ord("\U0002ceaf")),  # included as of Unicode 8.0
    ]

    def matches_set(self, string: str) -> bool:
        if self.set == "":
            return False
        elif self.set in {
            "japanese characters",
            "chinese characters",
            "korean characters",
            "cjk characters",
        }:
            print("TODO: CJK matching")
            # TODO: CJK matching
            return False
            for r in self.CJK_CHARACTERS:
                if set(map(ord, set(string))) ^ set(r):
                    return True
            return False
        else:
            raise ValueError(f"Unknown character set {self.set!r}")

    def matches(self, string: str) -> bool:
        return (
            string == self.raw
            or bool(re.compile(self.regex).match(string))
            # or self.matches_set(string)
        )


class MetadataConstraint:
    contain: ContainConstraint

    def __init__(self, contain: Union[dict, ContainConstraint, str]):
        self.contain = (
            ContainConstraint(raw=contain)
            if isinstance(contain, str)
            else (
                ContainConstraint(**contain) if isinstance(contain, dict) else contain
            )
        )

    def matches(self, metadata_piece: str) -> bool:
        return self.contain.matches(metadata_piece)


class PlaylistSpec(NamedTuple):
    directory: Path
    artists: set[str] = set()
    remixes: bool = True
    except_: set[tuple[str, str]] = set()
    tracks: set[tuple[str, str]] = set()
    from_: set[str] = set()
    titles: set[MetadataConstraint] = set()
    artist_names: set[MetadataConstraint] = set()
    name: str = ""
    runs: str = ""

    @classmethod
    def from_yaml(cls, filepath: Path) -> "PlaylistSpec":
        spec = yaml.safe_load(filepath.read_text("UTF-8"))
        if "except" in spec:
            spec["except_"] = set(spec["except"])
            del spec["except"]
        if "artists" in spec:
            spec["artists"] = set(spec["artists"])
        if "tracks" in spec:
            if any(len(t) < 2 for t in spec["tracks"]):
                raise TypeError(
                    f"tracks: tracks should have at least an artist and a title"
                )
            spec["tracks"] = set(
                Track(
                    filepath=find_file_of_track(
                        [f.filepath for f in all_tracks()],
                        artists=set(t[:-1]),
                        title=t[-1],
                    )
                )
                for t in spec["tracks"]
                if len(t) >= 2
            )
        else:
            spec["tracks"] = set()
        if "from" in spec:
            url = str(spec["from"])
            spec["from_"] = url
            del spec["from"]
            if url.startswith("https://open.spotify.com/playlist/"):
                spec["tracks"] |= from_spotify_playlist(url)
        if "titles" in spec:
            if isinstance(spec["titles"], list):
                spec["titles"] = set(
                    map(lambda s: MetadataConstraint(**s), spec["titles"])
                )
            else:
                spec["titles"] = {MetadataConstraint(**spec["titles"])}
        if "artist names" in spec:
            if isinstance(spec["artist names"], list):
                spec["artist names"] = set(
                    map(lambda s: MetadataConstraint(**s), spec["artist names"])
                )
            else:
                spec["artist names"] = {MetadataConstraint(**spec["artist names"])}
            spec["artist_names"] = spec["artist names"]
            del spec["artist names"]

        if "directory" not in spec:
            spec["directory"] = filepath.parent

        spec["directory"] = Path(spec["directory"])

        print(cls(**spec))
        return cls(**spec)

    def matches(self, track: Track) -> bool:
        matches = {
            "artists": self.artists & track.artists != set(),
            "track": any(
                t.artists & track.artists and t.title == track.title
                for t in self.tracks
            ),
            #             "titles": any(
            #                 constraint.matches(track.title) for constraint in self.titles
            #             ),
            "artist_names": any(
                constraint.matches(track.title) for constraint in self.artist_names
            ),
        }
        conditions = {
            "remixes": self.remixes or not track.remixed,
            "except": not (", ".join(track.artists), track.title) in self.except_,
            "runs": subprocess.run(self.runs.format(track=track)).returncode == 0
            if self.runs
            else True,
        }

        # print(f"{track} \t {' '.join( '{0} {1}'.format(k, v) for k, v in (matches|conditions).items())}")
        return any(matches.values()) and all(conditions.values())

    def pick_from(self, library: Iterable[Track]) -> Iterable[Track]:
        return filter(self.matches, library)

    def m3u(self, library: Iterable[Track]) -> str:
        return (
            "#EXTM3U\n"
            + (f"#PLAYLIST:{self.name}\n" if self.name else "")
            + "\n".join(str(self.directory / track.filepath.name) for track in self.pick_from(library))
        )


def autofill(playlist: PlaylistSpec, tracks: list[Track]) -> Iterable[tuple[Track, Path]]:
    """
    Yields tuples of type (Track, Path), where the first is the track picked and the second is the path the track's file was symlinked to
    """
    for track in tracks:
        if (created := not (playlist.directory / track.filepath.name).exists()) :
            (playlist.directory / track.filepath.name).symlink_to(track.filepath)
        print(f"  [{'bold' if created else 'dim'}]- [/][green]{track}")


def all_tracks() -> Iterable[Track]:
    for track in here.iterdir():
        if track.suffix != ".mp3":
            continue
        if len(track.name.split("\t")) != 3:
            continue
        yield Track(filepath=track)


if __name__ == "__main__":

    def do(dir: Path):
        for file in dir.iterdir():
            if not file.is_dir():
                continue
            if not (file / "autofill.yaml").exists():
                do(file)
                continue

            print(f"[blue]{file.name}[/][yellow]:")
            playlist = PlaylistSpec.from_yaml(file / "autofill.yaml")
            tracks = list(playlist.pick_from(all_tracks()))
            (playlist.directory / "playlist.m3u").write_text(playlist.m3u(tracks))
            autofill(playlist, tracks)

    do(here)
