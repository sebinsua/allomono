"""Fetch Allo, the font allomono is made from: `python -m allomono.fetch`.

Allo is not kept in this repository. One file of it is needed, its variable
font, at a pinned commit and checked against a known checksum, so that every
build starts from the same letters.
"""
import hashlib
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
COMMIT = "60992c5e12a4ad5cad41c54cd8dba370163a4828"  # Allo 1.0.3
SHA256 = "cdc994466d3a2dc77d5f72bd4f60c1bbf4d65dad5901ac064c7cc04e182c4fe4"
FILES = {
    "fonts/variable/AlloVariable.ttf": SHA256,
    "OFL.txt": None,
}
BASE = "https://raw.githubusercontent.com/joshpuckett/allo/%s/" % COMMIT


def main():
    for path, digest in FILES.items():
        dest = ROOT / "upstream" / "allo" / path
        if dest.exists() and (digest is None or hashlib.sha256(dest.read_bytes()).hexdigest() == digest):
            print("have", dest.relative_to(ROOT))
            continue
        data = urllib.request.urlopen(BASE + path).read()
        if digest and hashlib.sha256(data).hexdigest() != digest:
            sys.exit("checksum mismatch for %s: not the Allo this was built from" % path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        print("fetched", dest.relative_to(ROOT))


if __name__ == "__main__":
    main()
