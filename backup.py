# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "rich",
#     "spotipy",
#     "PyYAML",
# ]
# ///

#!/usr/bin/env python3

from typing import Literal
from spotipy import Spotify, SpotifyOAuth, MemoryCacheHandler
from subprocess import run
from pathlib import Path
import re
import sys
import json
import yaml
from rich import print
from rich.console import Console
from rich.table import Table

here = Path(__file__).parent

tokens = json.loads((here / "secrets.json").read_text())

gitignore = Path(".gitignore")

# ensure secrets.json is gitignored
if not gitignore.exists() or "\nsecrets.json\n" not in gitignore.read_text():
    gitignore.write_text(
        (gitignore.read_text() if gitignore.exists() else "") + "\nsecrets.json\n",
        encoding="utf8",
    )


# Initial setup
spotify = Spotify(
    auth_manager=SpotifyOAuth(
        scope=["user-follow-modify", "user-library-read"],
        client_id=tokens["id"],
        client_secret=tokens["secret"],
        redirect_uri="http://localhost:8080",
        cache_handler=MemoryCacheHandler()
    )
)


def sync_tsv_file(results: dict[Literal["items"], list], target: Path):
    # Fix quoting
    def fix_quoting(tracks):
        return {re.sub(r'"([^"]+)"', r"“\1”", track) for track in tracks}

    if not target.exists():
        print(f"⋆𐙚₊˚⊹♡ Creating [bold][magenta]{target}[reset] ⋆౨ৎ˚⟡˖ ࣪")
        target.write_text("Artist\tTitle\n", encoding="utf8")

    # Get whole library
    lib = list(target.read_text("utf8").splitlines())
    tracks, header = set(lib[1:]), lib[0]
    tracks = fix_quoting(tracks)

    # Boil them down to (artists, title, album)
    new_tracks = (
        fix_quoting(
            {
                "\t".join(
                    [
                        ", ".join(a["name"] for a in t["track"].get("artists", [])),
                        t["track"].get("name", None),
                        # t["track"]["album"]["name"],
                    ]
                )
                for t in results["items"]
            }
        )
        - tracks
    )

    if new_tracks:
        print(
            f"⋆𐙚₊˚⊹♡ I got [bold][cyan]{len(new_tracks)}[reset] new tracks for ya in [bold][magenta]{target}[reset] 💖 ⋆౨ৎ˚⟡˖ ࣪"
        )

        table = Table.grid(padding=(0, 2))
        table.add_column(style="bold dim")
        table.add_column()
        for new_track in new_tracks:
            artist, title = new_track.split("\t")
            table.add_row(artist, title)
        Console().print(table)
    else:
        print(
            f"⋆𐙚₊˚⊹♡ Nyathing new to add to [magenta][bold]{target}[reset]. Go listen to sum new music :3 ⋆౨ৎ˚⟡˖ ࣪"
        )
        return

    print("")

    # Add our tracks
    tracks |= new_tracks
    # Sort
    tracks = list(tracks)
    tracks.sort()
    # Write back library
    target.write_text("\n".join([header] + tracks), encoding="utf8")

    run(["git", "add", target], capture_output=True)


# Get playlists defined on Spotify by user
playlists_resp = spotify.current_user_playlists()
playlists = playlists_resp["items"]
while playlists_resp["next"]:
    playlists_resp = spotify.next(playlists_resp)
    playlists.extend(playlists_resp["items"])

# Store IDs of playlists we have to autocreate
autocreate_playlists = set(
    [
        playlist["external_urls"]["spotify"]
        for playlist in playlists
        if playlist["owner"]["id"] == spotify.current_user()["id"]
    ]
)


# Get tracks from API
results = spotify.current_user_saved_tracks()

sync_tsv_file(results, here / "library.tsv")

for playlist_definition_file in here.glob("**/autofill.yaml"):
    definition = yaml.safe_load(playlist_definition_file.read_text())
    if not definition.get("from", "").startswith("https://open.spotify.com/playlist/"):
        continue

    autocreate_playlists.discard(definition["from"])

    results = spotify.playlist_tracks(
        definition["from"],
        limit=100,
    )
    tracks = results["items"]
    get_all = not Path("tracklist.tsv").exists()
    get_all = True
    while get_all and results["next"]:
        results = spotify.next(results)
        tracks.extend(results["items"])

    sync_tsv_file(
        {"items": tracks},
        playlist_definition_file.parent / "tracklist.tsv",
    )

# Create playlists we have to create
for spotifyurl in autocreate_playlists:
    name = next(
        playlist["name"]
        for playlist in playlists
        if playlist["external_urls"]["spotify"] == spotifyurl
    )
    print(f"⋆𐙚₊˚⊹♡ Creating playlist [bold][magenta]{name}[reset] ⋆౨ৎ˚⟡˖ ࣪")
    try:
        Path(here, name).mkdir(exist_ok=True, parents=True)
        Path(here, name, "autofill.yaml").write_text(
            f"from: {spotifyurl}", encoding="utf8"
        )
        run(["git", "add", str(Path(here, name))], capture_output=True)
    except Exception as e:
        print(f"\tCouldn't create playlist: {e}")


# Git add commti and push
print("⋆𐙚₊˚⊹♡ Beaming up to github ⋆౨ৎ˚⟡˖ ࣪")
run(["git", "commit", "-m", "update"], capture_output=True)
run(["git", "pull", "--autostash"], capture_output=True)
run(["git", "push"], capture_output=True)
