#!/usr/bin/env python3
"""Derive a lean, already-sanitized source/research view; no original deletion."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '.github-publication/TradingAlarm'
TARGET = ROOT / '.github-publication/TradingAlarm-lean'
META = re.compile(r'^(?:.*_)?(?:contract|protocol|rules|algorithm|registry|freeze|results|summary|'
                  r'completion|complete|status|verdict|decision|selected_strategy|run_status|'
                  r'final_delivery|known_historical_failure|snapshot_verification)(?:[-_v0-9.]|$)', re.I)
RAW_SNAPSHOTS = {'unpacked', 'build45', 'runtime-recovery-03', 'qa_runs', 'reference_export',
                 'gzip_export', 'prior_entrypoints', 'validation_pass1', 'validation_pass2'}


def keep(path, size):
    p = Path(path)
    if path.startswith(('.git/', '.github/workflows/', 'publication/')):
        return False, 'old_git_ci_or_verbose_export_inventory'
    if any(x in RAW_SNAPSHOTS for x in p.parts):
        return False, 'duplicate_build_or_repeated_validation_snapshot'
    if 'trend-animal-reconstruction-20261024' in p.parts and p.suffix not in {'.md', '.txt'}:
        return False, 'third_party_reconstruction_tooling_local_archive'
    if p.name.endswith(('.pdf.txt', '_fulltext.txt', '_independent_fulltext.txt')) or 'official.pdf' in p.name:
        return False, 'third_party_notice_source_local_archive'
    if p.suffix in {'.py', '.md'}:
        return True, 'source_or_research_document'
    if p.suffix == '.txt':
        if re.search(r'(STDOUT|STDERR|SOURCE-EXPORT|INPUT-PREP)', p.name):
            return False, 'repetitive_console_dump_local_archive'
        return True, 'research_text_or_requirements'
    if p.suffix in {'.sh', '.command', '.toml', '.cfg', '.yml', '.yaml', '.asm'}:
        return True, 'source_configuration'
    if p.suffix in {'.js', '.html', '.css', '.svg'}:
        return (path.startswith('TradingAlarm/static/') or '/web/' in path) and size < 512 * 1024, 'application_assets_only'
    if p.suffix == '.json':
        if path.startswith(('TradingAlarm/desk/', 'TradingAlarm/contracts/')) or p.name == 'settings.example.json':
            return True, 'product_contract_and_calendar'
        if path.startswith('TradingAlarm/') and len(p.parts) == 2 and size < 64 * 1024:
            return True, 'product_acceptance_record'
        if any(x in {'full', 'sample', 'runs', 'timelines', 'checkpoint_20240927', 'once_20250120'} for x in p.parts):
            return False, 'per_step_or_repeated_run_record_local_archive'
        return bool(META.search(p.name)) and size <= 16 * 1024, 'bounded_research_contract_or_verdict'
    if p.suffix == '.csv':
        return bool(re.search(r'(proposed-pool|classification|mapping|roster|eight_cells|comparison|results|conclusion|missing_official|potential_event_boundaries)', p.name, re.I)) and size <= 256 * 1024, 'small_roster_or_final_result_table'
    return path == '.gitignore', 'other_local_material'


def main():
    if TARGET.exists():
        raise SystemExit('Lean target already exists')
    TARGET.mkdir(parents=True)
    stats, included, omitted = Counter(), [], []
    for p in sorted(SOURCE.rglob('*')):
        if not p.is_file() or p.is_symlink() or '.git' in p.relative_to(SOURCE).parts or '__pycache__' in p.parts:
            continue
        rel = p.relative_to(SOURCE).as_posix()
        ok, reason = keep(rel, p.stat().st_size)
        row = {'path': rel, 'bytes': p.stat().st_size, 'reason': reason}
        if ok:
            dest = TARGET / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, dest)
            included.append(row)
        else:
            omitted.append(row)
            stats[reason] += p.stat().st_size
    # Preserve the actual export recipe as source, not the discarded old Git history.
    dest = TARGET / 'scripts/prepare_lean_github.py'
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(Path(__file__), dest)
    (TARGET / 'publication').mkdir()
    summary = {'kind': 'LEAN_CODE_AND_RESEARCH_RECORDS', 'files_from_sanitized_view': len(included),
               'bytes_from_sanitized_view': sum(x['bytes'] for x in included),
               'omitted_from_github_only_files': len(omitted), 'omitted_from_github_only_bytes': sum(x['bytes'] for x in omitted),
               'omission_categories_bytes': dict(stats), 'original_research_files_deleted': 0,
               'large_data_and_full_evidence_retained_locally': True,
               'workflow_not_uploaded_no_workflow_scope_requested': True}
    (TARGET / 'publication/LEAN_EXPORT.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    report = ROOT / 'reports/repository-retention-20261110'
    report.mkdir(parents=True, exist_ok=True)
    with (report / 'GITHUB_OMITTED_BUT_RETAINED_LOCALLY.csv').open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(omitted[0])); w.writeheader(); w.writerows(omitted)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
