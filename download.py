#!/usr/bin/env python
from sys import exit
from pathlib import Path
from subprocess import run
import requests
import json
from bs4 import BeautifulSoup
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from mutagen.easyid3 import EasyID3
from rich import print 
from dotenv import load_dotenv 
from hashlib import md5

here = Path(__file__).parent
load_dotenv(here / ".env")
spotify = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials())

library_file = here / "library.tsv"
library = [
        t.replace("/", "⁄").split("\t", 2)
        for t in library_file.read_text("UTF-8").splitlines()
        ]

def tag_track(title: str, artists: set[str], file: Path) -> bool:
    """
    Returns True if the tag was applied, False if it was already applied
    """
    track = EasyID3(str(file))
    if set(track.get("artist", [])) == artists and track.get("title", [])[0] == title:
        # print(f"Checked {track.get('artist', [])!r} against {artists!r}")
        # print(f"Checked {track.get('title', [''])[0]!r} against {title!r}")
        # print("⤷  Skipped")
        return False
    track["title"] = title
    track["artist"] = "\0".join(artists)
    track.save()
    print(f"Tagged {file.name!r} as {', '.join(artists)} — {title}")
    return True

def download(track: tuple[str, str]) -> bool:
    """
    Returns True if the download succeeded False otherwise
    """
    artist, title = track
    # Use a MD5 hash to prevent youtube-dl from choking on weird file names.
    hash = md5(bytes(artist + title, "utf-8")).hexdigest()

    if not list(here.glob(f"{hash}*.mp3")):
        try:
            run(
                    [
                        "yt-dlp",
                        "-x",
                        "--audio-format",
                        "mp3",
                        "--output",
                        str(here / f"{hash}%(id)s.mp3"),
                        f"ytsearch15:{artist} {title}",
                        "--max-downloads=1",
                        "--ignore-errors",
                        "--age-limit=20" # to prevent download errors due to agewall
                        ]
                    )
        except KeyboardInterrupt:
            print("Download skipped by user, continuing…")
            return 

    try:
        file = list(here.glob(f'{hash}*.mp3'))[0]
        youtube_id = file.name.split('.')[0].replace(hash, "")
        try:
            tag_track(artists=artist.split(", "), title=title, file=file)
            file.rename(here / f"{artist}  {title.replace('/', '∕')}  {youtube_id}.mp3")
        except OSError as e:
            print(f"Couldn't rename file: {e}")
    except IndexError as e:
        print(f"[{hash}]")
        print(f"\tTried using file {file} and youtube ID {youtube_id}")
        print(e)
        exit(1)
        pass


def main():
    for track in library:
        if len(track) != 2:
            print(f"{track} format is incorrect")
            continue
        already_downloaded = False

        for file in library_file.parent.iterdir():
            if file.name.startswith((" " * 2).join(track)):
                already_downloaded = True
                break
            # if file.name.startswith("⣎⡇ꉺლ"):
            #     already_downloaded = True
            #     print(f"{track} already downloaded")
            #     break

        if not already_downloaded:
            download(track)


def duration_from_youtube(id: str) -> float:
    body = requests.get(f"https://yewtu.be/watch?v={id}").text
    video_data = BeautifulSoup(body, features="lxml").find(id="video_data").contents[0]
    return json.loads(video_data).get("length_seconds")


def duration_from_spotify(track: tuple[str, str]) -> float:
    return spotify.search(" ".join(track))["tracks"]["items"][0]["duration_ms"] * 1e-3


def duration_delta_acceptable(artist: str, title: str, video_id: str) -> bool:
    youtube_duration = duration_from_youtube(video_id)
    spotify_duration = duration_from_spotify((artist, title))
    Δ = abs(youtube_duration - spotify_duration) / spotify_duration

    print(f"\t[red]{youtube_duration}[/] vs [green]{spotify_duration}[/green]")
    print(f"\t[yellow]{Δ=}")

    return Δ <= 1 / 4


def verify_durations():
    for track in here.iterdir():
        if track.suffix != ".mp3":
            continue
        if len(parts := track.name.split("  ")) != 3:
            continue
        artist, title, video_id = parts

        print(
            f"[{'green' if duration_delta_acceptable(*parts) else 'red'}]{artist}: {title}"
        )


if __name__ == "__main__":
    main()
# TODO: compare metadata tags instead of file names to check if already downloaded, maybe it'll work better
