#!/usr/bin/env python3
"""Inspect archive retention or break a verified duplicate alias before editing."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def make_independent(path, expected_sha, mode=0o644, mtime_ns=None):
    """Materialize a separate inode with identical bytes; never edit shared bytes."""
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected a regular archive file')
    if sha(path) != expected_sha:
        raise ValueError('Content identity changed; refusing to replace it')
    old = path.stat()
    fd, temp = tempfile.mkstemp(prefix='.independent-', dir=path.parent)
    os.close(fd)
    temporary = Path(temp)
    try:
        shutil.copyfile(path, temporary)
        if sha(temporary) != expected_sha:
            raise ValueError('Independent copy failed SHA256 verification')
        os.chmod(temporary, mode)
        stamp = old.st_mtime_ns if mtime_ns is None else mtime_ns
        os.utime(temporary, ns=(old.st_atime_ns, stamp))
        assert temporary.stat().st_ino != old.st_ino
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--project-root', type=Path, default=Path(__file__).resolve().parents[1])
    sub = ap.add_subparsers(dest='command', required=True)
    sub.add_parser('status')
    one = sub.add_parser('make-independent')
    one.add_argument('archive_relative_path')
    args = ap.parse_args()
    root = args.project_root.resolve()
    state = json.loads((root / 'manifest/RETENTION_STATE.json').read_text())
    if args.command == 'status':
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return
    rel = Path(args.archive_relative_path)
    if rel.is_absolute() or '..' in rel.parts:
        raise ValueError('Use an archive-relative path without parent traversal')
    path = root / rel
    if not path.resolve().is_relative_to(root):
        raise ValueError('Path escapes archive')
    ledger = root / state['ledger_relative_path']
    if not ledger.exists():
        raise SystemExit('This source-only view has no local data ledger. Use the complete local archive for materialization.')
    match = None
    with ledger.open() as f:
        for line in f:
            row = json.loads(line)
            if row['path'] == rel.as_posix():
                match = row
                break
    if match is None:
        raise ValueError('Path is not a redundant copy in the retention ledger')
    make_independent(path, match['sha256'], match['original_mode'], match['original_mtime_ns'])
    print(json.dumps({'path': str(rel), 'independent': True, 'sha256': match['sha256']}))


if __name__ == '__main__':
    main()
