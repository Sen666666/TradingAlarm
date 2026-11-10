#!/usr/bin/env python3
"""Verify the frozen handoff payload without network access or credential reads."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def main():
    manifest = json.loads((ROOT / 'docs/payload-manifest.json').read_text())
    failures = []
    for row in manifest['files']:
        path = ROOT / row['path']
        if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            failures.append(row['path'])
    print(json.dumps({'checked': len(manifest['files']), 'failures': failures}, ensure_ascii=False))
    raise SystemExit(bool(failures))

if __name__ == '__main__':
    main()
