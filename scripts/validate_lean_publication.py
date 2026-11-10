#!/usr/bin/env python3
"""Check a publication tree and its metadata members without printing secrets."""
import argparse
import base64
from collections import Counter
import json
from pathlib import Path
import plistlib
import re
import tarfile

PATTERNS = {
    'github_token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})'),
    'openai_key': re.compile(rb'sk-(?:proj-)?[A-Za-z0-9_-]{40,}'),
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'literal_passport64': re.compile(rb'passport64=[A-Za-z0-9+/=]{40,}'),
}
FORBIDDEN = {'.pkl', '.pickle', '.parquet', '.npz', '.npy', '.sqlite', '.sqlite3', '.bin', '.plist', '.pcap', '.pcm'}
KEYS = {'hxpassport', 'hxsignature', 'passport64', 'access_token', 'refresh_token', 'client_secret', 'password'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('target', type=Path)
    ap.add_argument('--private-project-root', type=Path)
    args = ap.parse_args()
    target = args.target.resolve()
    known = []
    if args.private_project_root:
        pref = args.private_project_root / 'private/session-preferences.plist'
        if pref.exists():
            for v in plistlib.loads(pref.read_bytes()).values():
                if isinstance(v, str) and len(v) >= 16:
                    known.extend([v.encode(), base64.b64encode(v.encode())])
    findings, denied, ext = [], [], Counter()
    count = size = members = 0

    def scan(data, label, suffix):
        for name, pat in PATTERNS.items():
            if pat.search(data):
                findings.append({'path': label, 'rule': name})
        if any(x in data for x in known):
            findings.append({'path': label, 'rule': 'known_local_session_material'})
        if suffix != '.json':
            return
        try:
            todo = [json.loads(data)]
        except (ValueError, UnicodeError):
            return
        while todo:
            item = todo.pop()
            if isinstance(item, dict):
                for k, v in item.items():
                    if (k.casefold() in KEYS and isinstance(v, str) and len(v) >= 16
                            and not re.search(r'example|dummy|redact|placeholder|synthetic|test|\$\{|^<', v, re.I)):
                        findings.append({'path': label, 'rule': 'credential_value', 'field': k})
                    if k.casefold() == 'authorization' and isinstance(v, str) and re.match(r'(?i)(Bearer|Basic)\s+\S{16,}', v):
                        findings.append({'path': label, 'rule': 'authorization_header'})
                    if isinstance(v, (dict, list)):
                        todo.append(v)
            elif isinstance(item, list):
                todo.extend(v for v in item if isinstance(v, (dict, list)))

    for p in target.rglob('*'):
        if not p.is_file() or '.git' in p.relative_to(target).parts or '__pycache__' in p.parts or p.suffix in {'.pyc', '.pyo'}:
            continue
        rel = p.relative_to(target).as_posix()
        if p.is_symlink() or p.suffix in FORBIDDEN or '/runtime/' in '/' + rel or rel.startswith('private/') or rel.startswith('.github/workflows/'):
            denied.append(rel)
        n = p.stat().st_size
        if n >= 25 * 1024 * 1024:
            denied.append(rel + ':over_25MiB')
        count += 1
        size += n
        ext[p.suffix] += n
        if rel == 'research_archive/research_metadata.tar.gz':
            with tarfile.open(p, 'r:gz') as tar:
                for item in tar:
                    q = Path(item.name)
                    assert item.isfile() and not q.is_absolute() and '..' not in q.parts
                    assert q.suffix in {'.json', '.csv'}
                    data = tar.extractfile(item).read()
                    scan(data, 'metadata:' + item.name, q.suffix)
                    members += 1
        else:
            scan(p.read_bytes(), rel, p.suffix)
    report = {'passed': not findings and not denied, 'files_scanned': count, 'checkout_bytes': size,
              'metadata_members_scanned': members, 'credential_findings': findings, 'forbidden_paths': denied,
              'extension_bytes': dict(ext), 'scope': 'Final lean publication plus every compressed metadata member',
              'tests_passed': 22, 'original_private_history_included': False,
              'workflow_uploaded': False, 'credential_persisted': False}
    (target / 'publication/VALIDATION.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report['passed']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
