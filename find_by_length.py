# /// script
# requires-python = ">=3.11"
# dependencies = [
#   "pandas",
#   "spotipy",
#   "tqdm",
#   "requests",
#   "rich",
# ]
# ///

from __future__ import annotations

import random
import time
import json
from pathlib import Path
from rich import print

import pandas as pd
from requests.exceptions import HTTPError
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
from spotipy.cache_handler import MemoryCacheHandler
from tqdm import tqdm

###############################################################################

HERE = Path(__file__).parent

TOKENS = json.loads((HERE / "secrets.json").read_text())
cached = json.loads((HERE/"cachedlengths.json").read_text("utf8") if (HERE/"cachedlengths.json").exists() else "[]")

spotify = Spotify(
    auth_manager=SpotifyOAuth(
        scope=[
            "user-library-read",
        ],
        client_id=TOKENS["id"],
        client_secret=TOKENS["secret"],
        redirect_uri="http://127.0.0.1:8080",
        cache_handler=MemoryCacheHandler(),
    )
)

###############################################################################

MIN_SECONDS = 8 * 60 + 30
MAX_SECONDS = 30 * 60 + 30

CSV_OUT = HERE / "candidate_tracks.csv"
HTML_OUT = HERE / "gallery.html"

###############################################################################


def spotify_call(fn, *args, **kwargs):
    """
    Retry on:
        429
        5xx

    using exponential backoff + jitter.
    """

    delay = 1.0

    while True:
        try:
            return fn(*args, **kwargs)

        except HTTPError as e:
            response = getattr(e, "response", None)

            if response is None:
                raise

            status = response.status_code

            if status == 429:
                retry_after = response.headers.get("Retry-After")

                if retry_after:
                    delay = max(delay, float(retry_after))

            elif not (500 <= status < 600):
                raise

            sleep = delay + random.uniform(0, 0.5)

            print(f"Spotify returned {status}; sleeping {sleep:.1f}s")

            time.sleep(sleep)

            delay = min(delay * 2, 60)


###############################################################################

tracks = []

offset = 0
limit = 50

total = spotify_call(
    spotify.current_user_saved_tracks,
    limit=1,
)["total"]

progress = tqdm(total=total)


if not cached:

    while True:

        page = spotify_call(
            spotify.current_user_saved_tracks,
            limit=limit,
            offset=offset,
        )

        items = page["items"]

        if not items:
            break

        for item in items:

            t = item["track"]

            if t is None:
                continue

            seconds = t["duration_ms"] / 1000


            images = t["album"]["images"]
            artist = ", ".join(
                        a["name"]
                        for a in t["artists"]
                    )

            tracks.append(
                {
                    "artist": artist,
                    "title": t["name"],
                    "album": t["album"]["name"],
                    "duration": f"{int(seconds//60)}:{int(seconds%60):02}",
                    "seconds": round(seconds, 2),
                    "release": t["album"]["release_date"],
                    "popularity": t["popularity"],
                    "cover": images[0]["url"] if images else "",
                    "spotify": t["external_urls"]["spotify"],
                }
            )



        offset += len(items)
        progress.update(len(items))

    progress.close()

    (HERE/"cachedlengths.json").write_text(json.dumps(tracks))

else:
    tracks = cached

seen = {f"{t['artist']}\t{t['title']}" for t in tracks}

print(f"{seen=}")

remaining: set[tuple[str, str]] = {
        tuple(row.split("\t")[:2]) for row in (HERE/"library.tsv").read_text("utf8").splitlines()
        if "\t".join(row.split("\t")[:2]) not in seen
}

print(f"The following tracks were not found in spotify liked tracks:")
if len(seen) < 30: print(seen)
else: print(f"a lot ({len(seen)})")

for (artist, track) in tqdm(remaining):

    try:
        results = spotify_call(
            spotify.search,
            q=f'artist:"{artist}" track:"{track}"',
            limit=1,
            offset=0
        )

        items = results["tracks"]["items"]

        if not items:
            print(f"Nothing found for {artist} - {track}")
            continue

        t = items[0]

        if t is None:
            continue

        seconds = t["duration_ms"] / 1000

        images = t["album"]["images"]
        artist = ", ".join(
                    a["name"]
                    for a in t["artists"]
                )

        tracks.append(
            {
                "artist": artist,
                "title": t["name"],
                "album": t["album"]["name"],
                "duration": f"{int(seconds//60)}:{int(seconds%60):02}",
                "seconds": round(seconds, 2),
                "release": t["album"]["release_date"],
                "popularity": t["popularity"],
                "cover": images[0]["url"] if images else "",
                "spotify": t["external_urls"]["spotify"],
            }
        )
    except:
        continue


tracks = [ t for t in tracks if MIN_SECONDS <= t["seconds"] <= MAX_SECONDS ]




###############################################################################

df = pd.DataFrame(tracks)

df = (
    df.sort_values(
        ["seconds", "artist", "title"]
    )
    .reset_index(drop=True)
)

df.to_csv(CSV_OUT, index=False)

###############################################################################

html = [
    """
<html>
<head>
<meta charset="utf8">

<style>

body{
    font-family:sans-serif;
    background:#111;
    color:white;
}

.grid{
    display:flex;
    flex-wrap:wrap;
    gap:20px;
}

.card{
    width:220px;
    padding:12px;
    border-radius:10px;
    background:#222;
}

img{
    width:100%;
    border-radius:8px;
}

.small{
    color:#aaa;
    font-size:90%;
}

a{
    color:#6cf;
}

</style>

</head>

<body>

<h1>13:30–14:30 candidates</h1>

<div class="grid">
"""
]

for row in df.itertuples():

    html.append(
        f"""
<div class="card">

<img src="{row.cover}">

<h3>{row.title}</h3>

<div>{row.artist}</div>

<div class="small">
{row.album}
<br>
{row.duration}
<br>
{row.release}
</div>

<p>

<a href="{row.spotify}">
Open in Spotify
</a>

</p>

</div>
"""
    )

html.append("</div></body></html>")

HTML_OUT.write_text(
    "\n".join(html),
    encoding="utf8",
)

###############################################################################

print()
print(df)
print()
print(f"Wrote {CSV_OUT}")
print(f"Wrote {HTML_OUT}")
print(f"{len(df)} candidate tracks")
