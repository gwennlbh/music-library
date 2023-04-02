#!/usr/bin/env python
from pathlib import Path
import re
from sys import argv

here = Path(__file__).parent


def natsort(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s.strip())]


if __name__ == "__main__":
    print("counting artists")
    # datasource = map(lambda t: t.name, here.iterdir())
    datasource = (here / "library.tsv").read_text().splitlines()
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

    (here / "counts.tsv").write_text(
        "\n".join(
            reversed(sorted((f"{v:2}\t{k}" for k, v in counts.items()), key=natsort))
        )
    )

    if len(argv) < 2 or argv[1] != "--silent":
        print((here / "counts.tsv").read_text())
