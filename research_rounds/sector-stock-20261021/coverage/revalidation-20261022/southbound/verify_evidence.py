"""Independent saved-output/source replay checks; offline, no output overwrites."""
import bisect
import csv
import hashlib
import io
import json
from collections import defaultdict
from pathlib import Path

import openpyxl

ROOT = Path(__file__).resolve().parent


def load_csv(name):
    with (ROOT / name).open(encoding='utf-8', newline='') as stream:
        return list(csv.DictReader(stream))


def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


sources = json.loads((ROOT / 'sources.json').read_text())
initial = load_csv('initial-members.csv')
changes = load_csv('adjustments.csv')
intervals = load_csv('conditional-list-state-intervals.csv')
pilot = load_csv('pilot-symbols.csv')
assert all(digest(Path(s['path'])) == s['sha256'] for s in sources.values())
assert [int(r['source_ordinal']) for r in initial] == list(range(1, 418))
assert len({r['code'] for r in initial}) == 417
assert len(changes) == 1331
book = openpyxl.load_workbook(io.BytesIO(Path(sources['adjustments_xlsx']['path']).read_bytes()), read_only=True, data_only=True)
sheet = book.active
sheet.reset_dimensions()
raw = list(sheet.iter_rows(values_only=True))
for row in changes:
    source = raw[int(row['source_row']) - 1]
    assert [row['code'], row['name_cn'], row['name_en'], row['action_raw'], row['effective_date']] == list(source)
assert sorted(int(r['source_row']) for r in changes) == list(range(2, 1333))
assert all(not r['known_at'] and not r['announced_at'] for r in initial + changes + intervals)
assert all(r['eligible_for_account_input'] == 'False' for r in initial + changes + intervals)
assert all(r['executable_eligibility'] == 'unknown' for r in intervals + pilot)

by_code = defaultdict(list)
by_date = defaultdict(list)
for row in intervals:
    by_code[row['code']].append(row)
for row in changes:
    by_date[row['effective_date']].append(row)
for code, rows in by_code.items():
    assert rows[0]['effective_from_inclusive'] == '2016-12-05'
    assert rows[-1]['effective_to_exclusive'] == '2026-10-22'
    assert all(a['effective_to_exclusive'] == b['effective_from_inclusive'] for a, b in zip(rows, rows[1:]))
starts = {code: [r['effective_from_inclusive'] for r in rows] for code, rows in by_code.items()}
members = {r['code'] for r in initial}
date_checks = 0
member_counts = []
for day in ['2016-12-05'] + sorted(by_date):
    for event in by_date.get(day, []):
        code = event['code']
        if event['action_raw'] == '调入':
            assert code not in members
            members.add(code)
        else:
            assert code in members
            members.remove(code)
    derived = {code for code, rows in by_code.items()
               if rows[bisect.bisect_right(starts[code], day)-1]['reconstructed_list_state'] == 'listed'}
    assert derived == members
    member_counts.append({'effective_date': day, 'conditional_members': len(members)})
    date_checks += 1
assert len(members) == 417 + 806 - 525 == 698
assert len(by_code) == 1080
pilot_expected = {
    ('00005','2016-12-05'): 'listed', ('00700','2016-12-05'): 'listed',
    ('02318','2016-12-05'): 'listed', ('01810','2016-12-05'): 'absent_from_initial_list',
    ('09988','2016-12-05'): 'absent_from_initial_list',
    ('01810','2020-01-02'): 'listed', ('09988','2020-01-02'): 'absent_from_initial_list',
}
for row in pilot:
    key = row['code'], row['asof_date']
    if key in pilot_expected:
        assert row['reconstructed_list_state'] == pilot_expected[key]
    if row['asof_date'] == '2015-01-05':
        assert row['reconstructed_list_state'] == 'unknown_outside_source_coverage'
assert all((ROOT / f'source-review/initial-page-{page:02d}.png').exists() for page in range(1, 11))
validation = {
    'status': 'passed', 'source_hash_checks': len(sources),
    'exact_source_adjustment_row_checks': len(changes), 'initial_contiguous_ordinals': len(initial),
    'interval_code_coverage_checks': len(by_code), 'effective_date_full_set_replays': date_checks,
    'final_conditional_member_count': len(members), 'announced_and_known_times_all_null': True,
    'all_account_input_flags_false': True, 'source_pdf_pages_rendered': 10,
    'pdf_visual_review': 'All 10 full pages viewed; pilot rows 5, 144 and 339 visually checked. Names not recoverable in CJK text layer left missing except these manual checks.',
    'unexpected_membership_sequence_conflicts': 0,
    'full_southbound_eligibility_proven': False,
    'verifier_sha256': digest(Path(__file__)),
    'source_builder_sha256_matches_summary': digest(ROOT / 'build_evidence.py') == json.loads((ROOT/'summary.json').read_text())['builder_sha256'],
}
assert validation['source_builder_sha256_matches_summary']
with (ROOT / 'effective-date-member-counts.csv').open('x', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['effective_date','conditional_members'])
    writer.writeheader()
    writer.writerows(member_counts)
with (ROOT/'validation.json').open('x', encoding='utf-8') as f:
    json.dump(validation, f, ensure_ascii=False, indent=2)
    f.write('\n')
print(json.dumps(validation, ensure_ascii=False, indent=2))
