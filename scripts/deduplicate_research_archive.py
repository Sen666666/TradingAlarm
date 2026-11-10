#!/usr/bin/env python3
"""Verify and coalesce identical immutable archive payloads, preserving every path.

No algorithm is imported. No pickle is deserialized. Current inputs, all source,
conclusions and current M12 diagnostics are excluded. Applying replaces redundant
archive copies with read-only hard links only after whole-file SHA256 equality.
Original external source directories and the application's runtime are untouched.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
ARCHIVE = ROOT / 'research_rounds/all_in_one_20261110'
OUT = ROOT / 'reports/repository-retention-20261110'
sys.path.insert(0, str(ARCHIVE / 'tools'))
from archive_paths import ArchivePaths

ALLOWED = {'.pkl', '.parquet', '.npz', '.gz', '.json', '.jsonl', '.csv'}
MIN_BYTES = 1024 * 1024


def digest(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for data in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def atomic_json(p, obj):
    tmp = p.with_suffix(p.suffix + '.new')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2))
    os.replace(tmp, p)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--apply', action='store_true')
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    paths = ArchivePaths(ARCHIVE)
    protected = set()
    with (ROOT / 'docs/handoff_2026-11-10/CURRENT_INPUT_DEPENDENCIES.csv').open(encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):
            protected.add(str(paths.resolve(row['absolute_path']).relative_to(ARCHIVE)))
    groups = defaultdict(list)
    exclusion = Counter()
    total_files = total_bytes = 0
    for fn in ['FILES.csv', 'SUPPLEMENTAL_FILES.csv']:
        with (ARCHIVE / 'manifest' / fn).open() as f:
            for row in csv.DictReader(f):
                if row['kind'] != 'file':
                    continue
                total_files += 1
                n = int(row['bytes'])
                total_bytes += n
                rel = row['destination']
                p = ARCHIVE / rel
                if rel in protected:
                    exclusion['current_frozen_input'] += 1
                elif 'mainline_candidate_v12' in rel or 'm12_runtime' in rel or 'mainline_v12_' in rel:
                    exclusion['current_m12_evidence'] += 1
                elif p.suffix not in ALLOWED or n < MIN_BYTES:
                    exclusion['source_conclusion_small_or_unsupported'] += 1
                elif p.is_symlink() or not p.is_file() or p.stat().st_size != n:
                    exclusion['not_plain_stable_file'] += 1
                else:
                    groups[n].append(rel)
    candidates = [rel for v in groups.values() if len(v) > 1 for rel in v]
    groups.clear()
    print(json.dumps({'phase': 'size_candidates', 'files': len(candidates), 'protected_inputs': len(protected)}, ensure_ascii=False), flush=True)

    def sample(rel):
        p = ARCHIVE / rel
        before = p.stat()
        with p.open('rb') as f:
            h = hashlib.sha256(f.read(65536))
            f.seek(max(0, before.st_size - 65536))
            h.update(f.read(65536))
        after = p.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise RuntimeError('File changed during sample: ' + rel)
        return before.st_size, h.hexdigest(), rel

    samples = defaultdict(list)
    with ThreadPoolExecutor(max_workers=4) as pool:
        for n, partial, rel in pool.map(sample, candidates):
            samples[(n, partial)].append(rel)
    candidates = [rel for v in samples.values() if len(v) > 1 for rel in v]
    print(json.dumps({'phase': 'full_sha256', 'files': len(candidates),
                      'bytes': sum((ARCHIVE / r).stat().st_size for r in candidates)}), flush=True)

    def full(rel):
        p = ARCHIVE / rel
        before = p.stat()
        sha = digest(p)
        after = p.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise RuntimeError('File changed during hash: ' + rel)
        return sha, rel, before

    exact = defaultdict(list)
    with ThreadPoolExecutor(max_workers=4) as pool:
        count = 0
        for sha, rel, st in pool.map(full, candidates):
            exact[(st.st_size, sha)].append((rel, st))
            count += 1
            if count % 250 == 0:
                print(f'Fully hashed {count}/{len(candidates)} candidates', flush=True)
    plan = []
    for (size, sha), entries in exact.items():
        if len(entries) < 2:
            continue
        entries.sort(key=lambda x: x[0])
        keeper, keepstat = entries[0]
        for rel, st in entries[1:]:
            if st.st_ino == keepstat.st_ino:
                continue
            assert rel not in protected and keeper not in protected
            plan.append(dict(path=rel, canonical=keeper, bytes=size, sha256=sha,
                             original_mode=stat.S_IMODE(st.st_mode), original_mtime_ns=st.st_mtime_ns,
                             original_inode=st.st_ino, canonical_inode=keepstat.st_ino))
    with (OUT / 'EXACT_DUPLICATE_PLAN.csv').open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['path', 'canonical', 'bytes', 'sha256', 'original_mode',
                                            'original_mtime_ns', 'original_inode', 'canonical_inode'])
        writer.writeheader(); writer.writerows(plan)
    summary = dict(archive_regular_files=total_files, archive_logical_bytes_before=total_bytes,
                   protected_current_inputs=len(protected), exclusions=dict(exclusion),
                   duplicate_copies=len(plan), byte_identical_logical_bytes=sum(x['bytes'] for x in plan),
                   mode='PLAN_ONLY', applied=0, original_external_files_deleted=0,
                   no_source_conclusions_or_current_m12_evidence_deleted=True)
    atomic_json(OUT / 'DEDUPLICATION.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    if not args.apply:
        return
    free_before = shutil.disk_usage(ARCHIVE).free
    ledger = OUT / 'DEDUPLICATION_LEDGER.jsonl'
    if ledger.exists():
        raise RuntimeError('Refusing to overwrite an existing mutation ledger')
    done = 0
    with ledger.open('x') as log:
        for row in plan:
            p, keeper = ARCHIVE / row['path'], ARCHIVE / row['canonical']
            assert p.is_file() and keeper.is_file() and not p.is_symlink() and not keeper.is_symlink()
            assert p.stat().st_size == keeper.stat().st_size == row['bytes']
            assert p.stat().st_ino == row['original_inode']
            # These were both wholly hashed above; stat identity prevents swapping
            # an unrelated file between verification and atomic replacement.
            assert keeper.stat().st_ino == row['canonical_inode']
            temporary = p.with_name(p.name + '.dedup-verified-link')
            if temporary.exists():
                raise RuntimeError('Unexpected temporary path')
            os.link(keeper, temporary)
            assert temporary.stat().st_ino == keeper.stat().st_ino
            os.replace(temporary, p)
            os.chmod(keeper, stat.S_IMODE(keeper.stat().st_mode) & ~0o222)
            log.write(json.dumps(dict(row, action='REPLACED_REDUNDANT_COPY_WITH_READ_ONLY_HARDLINK'), ensure_ascii=False) + '\n')
            log.flush()
            os.fsync(log.fileno())
            done += 1
    for row in plan:
        assert (ARCHIVE / row['path']).stat().st_ino == (ARCHIVE / row['canonical']).stat().st_ino
    summary.update(mode='APPLIED_BYTE_IDENTICAL_HARDLINKS', applied=done,
                   file_paths_removed=0, unique_information_deleted=0,
                   free_bytes_before=free_before, free_bytes_after=shutil.disk_usage(ARCHIVE).free,
                   free_space_is_observation_not_attributable_saving=True)
    atomic_json(OUT / 'DEDUPLICATION.json', summary)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
