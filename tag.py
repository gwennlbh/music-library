#!/usr/bin/env python3
from pathlib import Path
from mutagen.easyid3 import EasyID3 

here = Path(__file__).parent
library_file = here / "library.tsv"
library = [
    t.replace("/", "⁄").split("  ", 2)
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

if __name__ == "__main__":
    for artists_str, title in library:
        artists = set(artists_str.split(", "))
        for file in library_file.parent.iterdir():
            if file.name.startswith(f"{artists_str}  {title}") and file.name.endswith(".mp3"):
                tag_track(title, artists, file)




