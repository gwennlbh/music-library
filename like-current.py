# /// script
# requires-python = ">=3.12"
# dependencies = [
#     "rich",
#     "spotipy",
#     "python-dotenv",
# ]
# ///

#!/usr/bin/env python3

from typing import Literal
from datetime import datetime, timedelta
from spotipy import Spotify, SpotifyOAuth, CacheFileHandler
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

here = Path(__file__).parent

tokens = json.loads((here / "secrets.json").read_text())
spotify_cache = here / "spotify_cache.json"

gitignore = Path(".gitignore")

# ensure secrets.json is gitignored
if not gitignore.exists() or "\nsecrets.json\n" not in gitignore.read_text():
    gitignore.write_text(
        (gitignore.read_text() if gitignore.exists() else "") + "\nsecrets.json\n",
        encoding="utf8",
    )

# ensure spotify_cache.json is gitignored
if not gitignore.exists() or "\nspotify_cache.json\n" not in gitignore.read_text():
	gitignore.write_text(
		(gitignore.read_text() if gitignore.exists() else "") + "\nspotify_cache.json\n",
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
        cache_handler=CacheFileHandler(
			cache_path=str(spotify_cache)
		),
    )
)

# Like currently playing track
current = spotify.current_user_playing_track()
if current and current["item"]:
	spotify.current_user_saved_tracks_add([current["item"]["id"]])

print(f"Liked {' × '.join(artist['name'] for artist in current['item']['artists'])} — {current['item']['name']}")
