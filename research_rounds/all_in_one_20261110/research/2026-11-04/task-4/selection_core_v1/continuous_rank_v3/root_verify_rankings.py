"""Independent CSV/Fraction verification; signal arithmetic only, no accounts."""
import csv
import hashlib
import json
from collections import Counter, defaultdict
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PATH = ROOT / 'ranking/DAILY_RANKINGS.csv'
groups = defaultdict(list)
for row in csv.DictReader(PATH.open()):
    groups[row['date']].append(row)
failures = []
total = 0
for date, rows in sorted(groups.items()):
    total += len(rows)
    if len(rows) != 90 or len({r['sector_id_static'] for r in rows}) != 90:
        failures.append([date, 'dimension'])
    ps = {}
    for raw, saved in [('rs_ind20', 'p_r20'), ('rs_ind5', 'p_r5'),
                       ('B_now', 'p_breadth'), ('dB5_paired', 'p_delta_b5'),
                       ('share_change_diagnostic', 'p_share_change')]:
        values = [float(r[raw]) for r in rows]
        counts = Counter(values)
        ranks = {}
        below = 0
        for value in sorted(counts):
            ranks[value] = Fraction(2 * below + counts[value], 2 * len(values))
            below += counts[value]
        ps[raw] = [ranks[x] for x in values]
        for r, value in zip(rows, ps[raw]):
            if abs(float(value) - float(r[saved])) > 1e-12:
                failures.append([date, r['sector_id_static'], saved])
    for i, row in enumerate(rows):
        row['_A'] = (2 * ps['rs_ind20'][i] + ps['rs_ind5'][i] + ps['B_now'][i] + ps['dB5_paired'][i]) / 5
        row['_E'] = (ps['rs_ind5'][i] + ps['dB5_paired'][i]) / 2
        row['_D'] = (ps['share_change_diagnostic'][i] + ps['dB5_paired'][i]) / 2
        row['_H1'] = float(row['H1_cache_same_date_score'])
        for score in ['A', 'E', 'D']:
            if row['_' + score] != Fraction(row[score + '_score_exact']):
                failures.append([date, row['sector_id_static'], score + '_exact'])
    orders = {k: sorted(rows, key=lambda r: (-r['_' + k], r['sector_id_static'])) for k in ['A', 'E', 'D', 'H1']}
    a = {r['sector_id_static'] for r in orders['A'][:5]}
    e = {r['sector_id_static'] for r in orders['E'][:3]}
    union = a | e
    selected = {'A': a, 'E': e, 'UNION': union,
                'D': {r['sector_id_static'] for r in orders['D'][:len(union)]},
                'H1': {r['sector_id_static'] for r in orders['H1'][:len(union)]}}
    for key, ids in selected.items():
        observed = {r['sector_id_static'] for r in rows if r['common_' + key + '_selected'] == 'True'}
        if observed != ids:
            failures.append([date, key, 'selection'])
    for row in rows:
        if row['C_t_member'] != 'True' or int(row['N_C']) != 90 or int(row['N_common_union']) != len(union):
            failures.append([date, row['sector_id_static'], 'comparison_population'])

out = {'scope': 'independent complete ranking arithmetic; no labels/accounts/parameters',
       'rows': total, 'sessions': len(groups),
       'source_sha256': hashlib.sha256(PATH.read_bytes()).hexdigest(),
       'design_sha256': hashlib.sha256((ROOT / 'FROZEN_DESIGN.txt').read_bytes()).hexdigest(),
       'failure_count': len(failures), 'failures': failures}
(ROOT / 'ROOT_COMPLETE_RANKING_ARITHMETIC_AUDIT.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(out, ensure_ascii=False, indent=2))
assert total == 97650 and len(groups) == 1085 and not failures
