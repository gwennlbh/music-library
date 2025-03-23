# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "rich",
#     "spotipy",
# ]
# ///

#!/usr/bin/env python3

from spotipy import Spotify, SpotifyOAuth
from subprocess import run
from pathlib import Path
import sys
import json
from rich import print
from rich.console import Console
from rich.table import Table

here = Path(__file__).parent

tokens = json.loads((here / "secrets.json").read_text())

# Initial setup
library = here / "library.tsv"
spotify = Spotify(
    auth_manager=SpotifyOAuth(
        scope=["user-follow-modify", "user-library-read"],
        client_id=tokens["id"],
        client_secret=tokens["secret"],
        redirect_uri="http://localhost:8080",
    )
)

# Get tracks from API
results = spotify.current_user_saved_tracks()['items']
# while results["next"]:
#    results = spotify.next(results)
#    tracks.extend(results["items"])

# Get whole library
lib = list(library.read_text('utf8').splitlines())
tracks, header = set(lib[1:]), lib[0]

# Boil them down to (artists, title, album)
new_tracks = {
    '\t'.join([
        ", ".join(a["name"] for a in t["track"].get("artists", [])),
        t["track"].get("name", None),
        # t["track"]["album"]["name"],
    ])
    for t in results
} - tracks

if new_tracks:
    print(f"⋆𐙚₊˚⊹♡ I got [bold][cyan]{len(new_tracks)}[reset] new tracks for ya 💖 ⋆౨ৎ˚⟡˖ ࣪")

    table = Table.grid(padding=(0, 2))
    table.add_column(style="bold dim")
    table.add_column()
    for new_track in new_tracks:
        artist, title = new_track.split('\t')
        table.add_row(artist, title)
    Console().print(table)
else:
    print(f"⋆𐙚₊˚⊹♡ Nyathing new to add. Go listen to sum new music :3 ⋆౨ৎ˚⟡˖ ࣪")
    sys.exit()

print("")

# Add our tracks
tracks |= new_tracks
# Sort
tracks = list(tracks)
tracks.sort()
# Write back library
library.write_text('\n'.join([header] + tracks), encoding='utf8')
# Git add commti and push
print(f"⋆𐙚₊˚⊹♡ Beaming up to github ⋆౨ৎ˚⟡˖ ࣪")
run(["git", "add", library], capture_output=True)
run(["git", "commit", "-m", "update"], capture_output=True)
run(["git", "pull", "--autostash"], capture_output=True)
run(["git", "push"], capture_output=True)
