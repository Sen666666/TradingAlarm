"""Independent first moments, tail counts and equal-width expectation. No new policy."""
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent
flags = {'V4_UNION': 'UNION_selected', 'V4_P': 'P_mature', 'V4_T': 'T_selected',
         'H1_N4': 'main_H1_selected', 'D_N4': 'main_D_selected',
         'V3_UNION': 'v3_native_UNION_selected', 'H1_N3': 'v3_common_H1_selected'}
f = pd.read_parquet(ROOT / 'ranking/STUDY_STATES_2022_2026.parquet',
                    columns=['date', 'sector_id_static', 'main_day90known', *flags.values()])
l = pd.read_csv(ROOT.parent / 'industry_channels_v2/diagnostics/INDUSTRY_PRICE_PATH_LABELS.csv',
                usecols=['date', 'sector_id_static', 'label_valid20', 'final20_rel_log', 'final20_abs_log',
                         'mae20_abs_log', 'mfe20_rel_log'])
f = f.merge(l, on=['date', 'sector_id_static'], validate='one_to_one')
assert len(f) == 97650 and f.main_day90known.all() and f.label_valid20.all()
data = defaultdict(list)
tailden = Counter()
daycount = Counter()
expected_hits = defaultdict(float)
for date, g in f.groupby('date', sort=True):
    phase = '2022_2023' if date < '2024' else '2024' if date < '2025' else '2025_2026H1'
    daycount[phase] += 1
    values = g.mfe20_rel_log.tolist()
    counts = Counter(values)
    below = 0
    score = {}
    for value in sorted(counts):
        score[value] = 2 * below + counts[value]
        below += counts[value]
    tail = pd.Series([x > 0 and 5 * score[x] >= 9 * len(values) for x in values], index=g.index)
    tailden[phase] += int(tail.sum())
    nums = {}
    hits = {}
    for policy, flag in flags.items():
        chosen = g[flag].eq(True)
        nums[policy] = int(chosen.sum())
        hits[policy] = int((chosen & tail).sum())
        for row in g.loc[chosen, ['final20_rel_log', 'final20_abs_log', 'mae20_abs_log']].itertuples(index=True):
            data[(phase, policy)].append((row.final20_rel_log, row.final20_abs_log, row.mae20_abs_log, bool(tail.loc[row.Index])))
    m = min(nums['V4_UNION'], nums['V3_UNION'])
    for policy in ['V4_UNION', 'V3_UNION']:
        expected_hits[(phase, policy)] += m * hits[policy] / nums[policy]

out = []
for (phase, policy), rows in sorted(data.items()):
    n = len(rows)
    h = sum(r[3] for r in rows)
    out.append({'scope': phase, 'policy': policy, 'days': daycount[phase], 'selected_industry_days': n,
                'mean_list_size': n / daycount[phase], 'relative_final20_mean_log': math.fsum(r[0] for r in rows) / n,
                'absolute_final20_nonpositive_fraction': sum(r[1] <= 0 for r in rows) / n,
                'absolute_mae20_mean_log': math.fsum(r[2] for r in rows) / n,
                'main_tail_hits': h, 'main_tail_denominator': tailden[phase],
                'main_tail_coverage_micro': h / tailden[phase], 'main_tail_precision': h / n})
equal = [{'scope': phase, 'policy': policy, 'expected_hits': n, 'tail_denominator': tailden[phase],
          'equal_width_expected_coverage': n / tailden[phase], 'not_executable_selection': True}
         for (phase, policy), n in sorted(expected_hits.items())]
(ROOT / 'ROOT_FIXED_OUTCOMES.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n')
(ROOT / 'ROOT_EQUAL_WIDTH_EXPECTED_COVERAGE.json').write_text(json.dumps(equal, ensure_ascii=False, indent=2) + '\n')
print(json.dumps({'outcomes': [r for r in out if r['policy'] in ['V4_UNION', 'H1_N4', 'V3_UNION', 'H1_N3']],
                  'equal_width_expectation': equal}, ensure_ascii=False, indent=2))
