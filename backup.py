# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "rich",
#     "spotipy",
#     "PyYAML",
#     "docopt",
#     "python-slugify",
#     "requests",
#     "helium",
#     "python-dotenv",
# ]
# ///

#!/usr/bin/env python3

from typing import Literal
from datetime import datetime, timedelta
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
from download_cover_arts_of_playlist import download_artworks
from update_artist_counts import update_artist_counts


def git_add(path: Path | str):
    run(["git", "add", str(path)], capture_output=True)


MAX_UPDATE_AGE = timedelta(hours=4)

here = Path(__file__).parent

tokens = json.loads((here / "secrets.json").read_text())

if "last_run" in tokens:
    if datetime.fromtimestamp(tokens["last_run"]) + MAX_UPDATE_AGE > datetime.now():
        print(
            f"⋆𐙚₊˚⊹♡ Backup ran recently (less than {MAX_UPDATE_AGE} ago), skipping ⋆౨ৎ˚⟡˖ ࣪"
        )
        sys.exit(0)

tokens["last_run"] = datetime.now().timestamp()
(here / "secrets.json").write_text(json.dumps(tokens), encoding="utf8")

gitignore = Path(".gitignore")

# ensure secrets.json is gitignored
if not gitignore.exists() or "\nsecrets.json\n" not in gitignore.read_text():
    gitignore.write_text(
        (gitignore.read_text() if gitignore.exists() else "") + "\nsecrets.json\n",
        encoding="utf8",
    )


# Initial setup
print("Initializing spotify client")
spotify = Spotify(
    auth_manager=SpotifyOAuth(
        scope=[
            "user-follow-modify",
            "user-library-read",
            "user-library-modify",
            "user-follow-read",
            "playlist-modify-public",
            "playlist-modify-private",
            "user-read-playback-state",
        ],
        client_id=tokens["id"],
        client_secret=tokens["secret"],
        redirect_uri="http://127.0.0.1:8080",
        cache_handler=MemoryCacheHandler(),
    )
)

print("Getting access token")
tokens["access_token"] = spotify.auth_manager.get_access_token(as_dict=False)
tokens["scopes"] = spotify.auth_manager.scope
(here / "secrets.json").write_text(json.dumps(tokens), encoding="utf8")


def sync_tsv_file(results: dict[Literal["items"], list], target: Path):
    print(f"Syncing {target}")

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

    git_add(target)


# Get playlists defined on Spotify by user
print("Syncing playlists")
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
print("Syncing liked tracks")
results = spotify.current_user_saved_tracks()

sync_tsv_file(results, here / "library.tsv")

print("Syncing playlists")
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

    if playlist_definition_file.parent.stem == "niceartworks":
        download_artworks(definition["from"], here / "niceartworks")
        git_add(here / "niceartworks")


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
        git_add(here / name)
    except Exception as e:
        print(f"\tCouldn't create playlist: {e}")

# Get all followed artists
print("Syncing followed artists")
get_all = False
results = spotify.current_user_followed_artists(limit=50)
artists = set(
    Path("followed_artists.txt").read_text("utf8").splitlines()
    if Path("followed_artists.txt").exists()
    else []
)
artists |= {a["name"] for a in results["artists"]["items"]}
while get_all and results["artists"]["next"]:
    results = spotify.next(results["artists"])
    artists |= {a["name"] for a in results["artists"]["items"]}


# Write artists to followed_artists.txt
Path("followed_artists.txt").write_text(
    "\n".join(sorted(a for a in artists)), encoding="utf8"
)
git_add("followed_artists.txt")

print("Syncing liked counts")
update_artist_counts()
git_add("counts.tsv")

git_add(__file__)

# Git add commit and push
print("⋆𐙚₊˚⊹♡ Beaming up to github ⋆౨ৎ˚⟡˖ ࣪")
run(["git", "commit", "-m", "update"], capture_output=True)
run(["git", "pull", "--autostash"], capture_output=True)
run(["git", "push"], capture_output=True)
