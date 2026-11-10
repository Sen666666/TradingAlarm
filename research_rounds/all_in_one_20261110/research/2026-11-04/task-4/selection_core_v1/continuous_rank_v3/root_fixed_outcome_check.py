"""Independent fixed-policy first moments/tail counts; no ranking changes."""
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LABEL = ROOT.parent / 'industry_channels_v2/diagnostics/INDUSTRY_PRICE_PATH_LABELS.csv'
labels = {(r['date'], r['sector_id_static']): r for r in csv.DictReader(LABEL.open())}
days = defaultdict(list)
for r in csv.DictReader((ROOT / 'ranking/DAILY_RANKINGS.csv').open()):
    r['_label'] = labels[(r['date'], r['sector_id_static'])]
    days[r['date']].append(r)
att_days = defaultdict(dict)
for r in csv.DictReader((ROOT / 'original_baselines/ATT_ORIGINAL_SAVED_DAILY.csv').open()):
    att_days[r['date']][r['sector_id_static']] = float(r['ATT_original'])

records = defaultdict(list)
denoms = Counter()
for date, rows in sorted(days.items()):
    phase = '2022_2023' if date < '2024' else '2024' if date < '2025' else '2025_2026H1'
    values = [float(r['_label']['mfe20_rel_log']) for r in rows]
    counts = Counter(values)
    ranks = {}
    below = 0
    for x in sorted(counts):
        ranks[x] = (2 * below + counts[x], len(values))
        below += counts[x]
    tail = {r['sector_id_static'] for r, x in zip(rows, values) if x > 0 and 5 * ranks[x][0] >= 9 * ranks[x][1]}
    selected = {p: {r['sector_id_static'] for r in rows if r['common_' + flag + '_selected'] == 'True'}
                for p, flag in [('A5_E3', 'UNION'), ('H1', 'H1'), ('D', 'D')]}
    scopes = [(phase, selected)]
    if date in att_days:
        n = len(selected['A5_E3'])
        att = sorted(att_days[date], key=lambda sid: (-att_days[date][sid], sid))[:n]
        scopes.append(('ATT_AVAILABLE_2025H2_2026H1', {**selected, 'ATT': set(att)}))
    for scope, policies in scopes:
        denoms[scope] += len(tail)
        denoms[scope + '_days'] += 1
        for policy, ids in policies.items():
            for r in rows:
                if r['sector_id_static'] in ids:
                    y = r['_label']
                    assert y['label_valid20'] == 'True'
                    records[(scope, policy)].append((float(y['final20_rel_log']), float(y['final20_abs_log']),
                                                      float(y['mae20_abs_log']), r['sector_id_static'] in tail))

out = []
for (scope, policy), xs in sorted(records.items()):
    n = len(xs)
    hits = sum(x[3] for x in xs)
    out.append({'scope': scope, 'policy': policy, 'days': denoms[scope + '_days'], 'selected_industry_days': n,
                'relative_final20_mean_log': math.fsum(x[0] for x in xs) / n,
                'absolute_final20_mean_log': math.fsum(x[1] for x in xs) / n,
                'absolute_final20_nonpositive_fraction': sum(x[1] <= 0 for x in xs) / n,
                'relative_final20_nonpositive_fraction': sum(x[0] <= 0 for x in xs) / n,
                'absolute_mae20_mean_log': math.fsum(x[2] for x in xs) / n,
                'main_tail_hits': hits, 'main_tail_denominator': denoms[scope],
                'main_tail_coverage_micro': hits / denoms[scope] if denoms[scope] else None,
                'main_tail_precision': hits / n})
(ROOT / 'ROOT_EARLY_FIXED_OUTCOMES.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
with (ROOT / 'ROOT_EARLY_FIXED_OUTCOMES.csv').open('w') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print(json.dumps(out, ensure_ascii=False, indent=2))
