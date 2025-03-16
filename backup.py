# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "spotipy",
# ]
# ///

#!/usr/bin/env python3

from spotipy import Spotify, SpotifyOAuth
from subprocess import run
from pathlib import Path
import sys

here = Path(__file__).parent

tokens = json.loads(here / "tokens.json")

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
results = spotify.current_user_saved_tracks()
tracks = results["items"]
# while results["next"]:
#    results = spotify.next(results)
#    tracks.extend(results["items"])
del results

print(tracks)

# Boil them down to (artists, title, album)
new_tracks = [
    '\t'.join([
        ", ".join(a["name"] for a in t["track"].get("artists", [])),
        t["track"].get("name", None),
        # t["track"]["album"]["name"],
    ])
    for t in tracks
]

# Get whole library
lib = list(library.read_text('utf8').splitlines())
tracks, header = lib[1:], lib[0]
# Add our tracks
tracks.extend(new_tracks)
# Sort
tracks.sort()
# Write back library
library.write_text('\n'.join([header] + tracks), encoding='utf8')
# Git add commti and push
run(["git", "add", library])
run(["git", "commit", "-m", "update"])
run(["git", "push"])
