#!/usr/bin/env python3
"""Build a reviewed source/research export without copying private Git history.

Does not push, download data, import research engines, or modify original inputs.
The target must be new. Credential matches are reported by path/rule, never value.
"""
import argparse
import base64
import csv
import hashlib
import json
import os
from pathlib import Path
import plistlib
import re
import shutil
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'research_rounds/all_in_one_20261110'
SOURCE_EXT = {'.py', '.md', '.txt', '.js', '.css', '.html', '.svg', '.asm', '.sh',
              '.command', '.toml', '.yaml', '.yml', '.ini', '.cfg'}
PRUNE = {'.git', '.codex', '.agents', '.tools', '.venv', '__pycache__', 'node_modules',
         'runtime', 'private', 'handshake', 'captures', 'responses', 'downloads',
         'data', 'raw', 'rights', 'actions', 'paper-quotes', '.github-publication'}
META = re.compile(r'(conclusion|report|readout|rules|contract|protocol|summary|verification|'
                  r'complete|completion|status|decision|registry|freeze|qa|results|source.hash|'
                  r'frozen.input|coverage|audit|repair|admission|delivery|gate|boundary|manifest|'
                  r'latest|mapping|classification|roster|pool|counts|calendar|schema|scope)', re.I)
DENY_NAME = re.compile(r'(session-preferences|session-status|session\.bin|settings\.json|'
                       r'credential|\.env(?:\.|$)|preferences\.plist|\.pcap|\.pem$|\.key$)', re.I)
SECRET_RULES = {
    'github_token': re.compile(rb'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,})'),
    'openai_key': re.compile(rb'sk-(?:proj-)?[A-Za-z0-9_-]{40,}'),
    'aws_access_key': re.compile(rb'(?:AKIA|ASIA)[A-Z0-9]{16}'),
    'private_key': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'literal_passport64': re.compile(rb'passport64=[A-Za-z0-9+/=]{40,}'),
    'literal_hxsignature': re.compile(rb'"HXSignature"\s*:\s*"[A-Za-z0-9+/=]{16,}"'),
}


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('target', type=Path)
    args = ap.parse_args()
    dest = args.target.resolve()
    if dest.exists():
        raise SystemExit('Target must not already exist')
    dest.mkdir(parents=True)
    secrets = []
    pref = ROOT / 'private/session-preferences.plist'
    if pref.exists():
        for v in plistlib.loads(pref.read_bytes()).values():
            if isinstance(v, str) and len(v) >= 16:
                secrets.extend([v.encode(), base64.b64encode(v.encode())])
    wire = ROOT / 'private/session.bin'
    if wire.exists():
        for v in re.findall(rb'passport64=([^\r\n\x00]+)', wire.read_bytes()):
            if len(v) > 20:
                secrets.append(v)
                try:
                    secrets.append(base64.b64decode(v))
                except ValueError:
                    pass
    secrets = list(set(v for v in secrets if len(v) >= 16))
    rows, skipped, matches, copied = [], Counter(), [], set()

    def copy(p, relative):
        relative = Path(relative)
        key = relative.as_posix()
        if key in copied:
            return
        if p.is_symlink() or DENY_NAME.search(p.name):
            skipped['private_name_or_symlink'] += 1
            return
        content = p.read_bytes()
        hits = [name for name, pat in SECRET_RULES.items() if pat.search(content)]
        if any(v in content for v in secrets):
            hits.append('known_local_session_material')
        if hits:
            matches.append({'path': key, 'rules': hits, 'action': 'EXCLUDED_ENTIRE_FILE'})
            skipped['credential_content'] += 1
            return
        out = dest / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(p, out)
        copied.add(key)
        rows.append({'path': key, 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(),
                     'source_relative': str(p.relative_to(ROOT))})

    def walk(base, relative, metadata=True, prune_extra=()):
        for parent, dirs, files in os.walk(base):
            dirs[:] = sorted(d for d in dirs if d not in PRUNE and d not in prune_extra)
            for name in sorted(files):
                p = Path(parent) / name
                if p.is_symlink():
                    skipped['symlink'] += 1
                    continue
                rel = p.relative_to(base)
                size = p.stat().st_size
                if p.suffix.lower() in SOURCE_EXT and size <= 2 * 1024 * 1024:
                    copy(p, Path(relative) / rel)
                elif metadata and p.suffix.lower() in {'.json', '.csv'} and size <= 256 * 1024 and len(rel.parts) <= 3 and META.search(name):
                    copy(p, Path(relative) / rel)
                else:
                    skipped['large_binary_raw_or_unselected_result'] += 1

    # Current application, decoder source and tests; no market dumps or accounts.
    walk(ROOT / 'TradingAlarm', 'TradingAlarm')
    for n in ['capture-decode.py', 'capture-hxdecode.py', 'capture-hxzip.asm']:
        copy(ROOT / 'artifacts/ths-analysis-20261016/deep' / n,
             Path('artifacts/ths-analysis-20261016/deep') / n)
    walk(ROOT / 'scripts', 'scripts')
    walk(ROOT / 'docs', 'docs', prune_extra={'snapshots', 'supplement_20261029', 'prior_entrypoints',
                                           'prior', 'staged', 'workspace-prior', 'validation_pass1', 'validation_pass2'})
    # Preserve original October experiment layout and select only bounded metadata.
    for experiment in sorted((ROOT / 'research_rounds').iterdir()):
        if experiment.is_dir() and experiment != ARCHIVE:
            walk(experiment, Path('research_rounds') / experiment.name)
    # Canonical copies of November research; omit the duplicate project/ payload.
    if ARCHIVE.exists():
        for part in ['docs', 'tools']:
            walk(ARCHIVE / part, Path('research_rounds/all_in_one_20261110') / part)
        for date in sorted((ARCHIVE / 'research').iterdir()):
            for project in sorted(date.iterdir()):
                target = Path('research_rounds/all_in_one_20261110/research') / date.name / project.name
                if project.is_dir():
                    if project.name == 'task' and (project / 'research_rounds').exists():
                        for experiment in sorted((project / 'research_rounds').iterdir()):
                            if experiment.is_dir():
                                walk(experiment, target / 'research_rounds' / experiment.name)
                        # Root-level contracts and support modules outside research_rounds.
                        for p in project.iterdir():
                            if p.is_file() and p.suffix in SOURCE_EXT and p.stat().st_size <= 2 * 1024 * 1024:
                                copy(p, target / p.name)
                    else:
                        walk(project, target)
                elif project.suffix in SOURCE_EXT:
                    copy(project, target)
        for p in (ARCHIVE / 'manifest').iterdir():
            if p.is_file() and p.suffix in {'.json', '.md'} and p.stat().st_size <= 256 * 1024:
                copy(p, Path('research_rounds/all_in_one_20261110/manifest') / p.name)
        copy(ARCHIVE / 'README.md', 'research_rounds/all_in_one_20261110/README.md')
    walk(ROOT / 'reports', 'reports')
    for name in ['requirements-research.txt', 'requirements-fetch.txt', 'HANDOFF_2026-11-10.md']:
        copy(ROOT / name, name)
    copy(ROOT / 'README.md', 'docs/history/README.before-github-publication.md')
    copy(ROOT / 'AGENTS.md', 'docs/history/AGENTS.before-github-publication.md')
    # These private-migration instructions do not apply to this source export.
    for n in ['docs/PRIVATE_MIGRATION.md', 'docs/SECURITY.md']:
        p = dest / n
        if p.exists():
            p.unlink()
            rows[:] = [r for r in rows if r['path'] != n]
    publish = dest / 'publication'
    publish.mkdir()
    with (publish / 'EXPORTED_FILES.csv').open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['path', 'bytes', 'sha256', 'source_relative'])
        writer.writeheader()
        writer.writerows(rows)
    summary = {'type': 'SANITIZED_SOURCE_AND_RESEARCH_EXPORT', 'source_private_history_included': False,
               'source_files': len(rows), 'source_bytes': sum(r['bytes'] for r in rows),
               'excluded_counts': dict(skipped), 'credential_content_exclusions': matches,
               'data_archive_included': False, 'local_source_git_unchanged': True}
    (publish / 'EXPORT_SUMMARY.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
