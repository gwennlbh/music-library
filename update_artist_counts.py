#!/usr/bin/env python
from pathlib import Path
import re
from sys import argv

here = Path(__file__).parent


def natsort(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s.strip())]


def update_artist_counts(silent=True):
    print("counting artists")
    # datasource = map(lambda t: t.name, here.iterdir())
    datasource = (here / "library.tsv").read_text("utf8").splitlines()
    print(f"using library with {len(datasource)} lines")
    tracks = [
        t.split("\t")[0]
        for t in datasource
        if t.count("\t") >= 1 and not t.startswith("# vim")
    ]
    print(f"from {len(tracks)} tracks")
    tracks_nested = [a.split(", ") for a in tracks]

    artists = []
    for t in tracks_nested:
        artists += t

    counts = {artist: artists.count(artist) for artist in artists}

    total = sum(counts.values())

    (here / "counts.tsv").write_text(
        f"{total}\t\n" +
        "\n".join(
            reversed(sorted((f"{v:2}\t{k}" for k, v in counts.items()), key=natsort))
        ),
        encoding="utf8",
    )

    if not silent:
        print((here / "counts.tsv").read_text("utf8"))


if __name__ == "__main__":
    update_artist_counts(slient=len(argv) < 2 or argv[1] != "--silent")
