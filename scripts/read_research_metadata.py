#!/usr/bin/env python3
"""List or read preserved research metadata without unpacking a data archive."""
import argparse
import csv
import hashlib
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('path', nargs='?', help='Exact original relative path from METADATA_INDEX.csv')
    args = ap.parse_args()
    with (ROOT / 'research_archive/METADATA_INDEX.csv').open() as f:
        rows = list(csv.DictReader(f))
    if not args.path:
        for row in rows:
            print(row['path'])
        return
    row = next((r for r in rows if r['path'] == args.path), None)
    if row is None:
        raise SystemExit('Metadata path not present in the preserved index')
    with tarfile.open(ROOT / 'research_archive/research_metadata.tar.gz', 'r:gz') as tar:
        member = tar.getmember(args.path)
        if not member.isfile():
            raise SystemExit('Expected an ordinary metadata member')
        contents = tar.extractfile(member).read()
    if hashlib.sha256(contents).hexdigest() != row['sha256']:
        raise SystemExit('Metadata SHA256 mismatch')
    print(contents.decode('utf-8-sig'))


if __name__ == '__main__':
    main()
