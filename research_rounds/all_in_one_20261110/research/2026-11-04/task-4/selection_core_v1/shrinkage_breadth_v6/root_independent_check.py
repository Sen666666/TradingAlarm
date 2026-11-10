"""Independent exact formula and fixed T0/T10 outcome counts; no new policy."""
import csv
import json
import math
from collections import Counter, defaultdict
from fractions import Fraction as Q
from pathlib import Path

ROOT = Path(__file__).resolve().parent
labels = list(csv.DictReader((ROOT.parent/'industry_channels_v2/diagnostics/INDUSTRY_PRICE_PATH_LABELS.csv').open()))
by_day = defaultdict(list)
lab = {}
for r in labels:
    by_day[r['date']].append(r)
    lab[(r['date'],r['sector_id_static'])] = r
tails = {}
denoms = Counter()
for day, rows in by_day.items():
    vals = [float(r['mfe20_rel_log']) for r in rows]
    counts = Counter(vals); below = 0; units = {}
    for value in sorted(counts):
        units[value] = 2*below+counts[value]; below += counts[value]
    tails[day] = {r['sector_id_static'] for r,v in zip(rows,vals) if v>0 and 5*units[v]>=9*len(vals)}
    phase = '2022_2023' if day<'2024' else '2024' if day<'2025' else '2025_2026H1'
    denoms[phase] += len(tails[day])

selected = defaultdict(list); sparse = Counter(); drift = Counter(); lost = []; checks = 0
rows = list(csv.DictReader((ROOT/'features/DAILY_SHRINKAGE_FEATURES.csv').open()))
for r in rows:
    day,sid = r['date'],r['sector_id_static']; n=int(r['n']); u0=int(r['u0']); u1=int(r['u1'])
    m0=Q(r['m0_exact']); m1=Q(r['m1_exact']); self=Q(u1-u0,n+10); market=10*(m1-m0)/(n+10)
    assert Q(r['B1_shrunk_exact'])==(u1+10*m1)/(n+10)
    assert Q(r['B0_paired_shrunk_exact'])==(u0+10*m0)/(n+10)
    assert Q(r['D_shrunk_exact'])==self+market==Q(r['Self_exact'])+Q(r['Market_exact'])
    checks += 3
    phase = '2022_2023' if day<'2024' else '2024' if day<'2025' else '2025_2026H1'
    tail=sid in tails[day]; y=lab[(day,sid)]; old=r['T0_selected']=='True'; new=r['T10_selected']=='True'
    if u1==u0 and self+market>0:
        drift[(phase,'rows')] += 1; drift[(phase,'T10_selected')] += int(new)
    for name,flag in [('T0',old),('T10',new)]:
        if flag:
            selected[(phase,name)].append((tail,float(y['final20_rel_log']),float(y['final20_abs_log']),float(y['mae20_abs_log'])))
    if n<=10 and old!=new:
        sparse[(phase,'added_signals' if new else 'removed_signals')] += 1
        if tail:
            sparse[(phase,'added_tail' if new else 'removed_tail')] += 1
            if old:
                lost.append({k:r[k] for k in ['date','sector_id_static','industry_static','n','T0_order','T10_order']} |
                            {k:y[k] for k in ['label_end20','mfe20_rel_log','final20_rel_log','final20_abs_log']} |
                            {'study_window':phase,'evaluation_only_not_realtime_winner_label':True})
summary=[]
for (phase,method),values in sorted(selected.items()):
    n=len(values); hits=sum(x[0] for x in values)
    summary.append({'study_window':phase,'method':method,'selected_industry_days':n,'tail_hits':hits,
                    'tail_denominator':denoms[phase],'coverage':hits/denoms[phase],
                    'relative_final20_mean_log':math.fsum(x[1] for x in values)/n,
                    'absolute_final20_nonpositive_fraction':sum(x[2]<=0 for x in values)/n,
                    'absolute_mae20_mean_log':math.fsum(x[3] for x in values)/n})
out={'formula_rows':len(rows),'exact_formula_cells':checks,'summary':summary,
     'sparse':{phase:{k:sparse[(phase,k)] for k in ['added_signals','removed_signals','added_tail','removed_tail']} for phase in sorted(denoms)},
     'net_zero_count_positive_shrink':{phase:{k:drift[(phase,k)] for k in ['rows','T10_selected']} for phase in sorted(denoms)}}
(ROOT/'ROOT_INDEPENDENT_FORMULA_AND_OUTCOME_CHECK.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
lost.sort(key=lambda r:(r['date'],r['sector_id_static']))
with (ROOT/'ALL_REMOVED_SPARSE_UPPER_TAIL_EVALUATION_ONLY.csv').open('w') as f:
    w=csv.DictWriter(f,fieldnames=list(lost[0]));w.writeheader();w.writerows(lost)
examples=[]
for phase in sorted(denoms):examples.extend([r for r in lost if r['study_window']==phase][:2])
print(json.dumps({'formula_rows':len(rows),'exact_formula_cells':checks,'summary':summary,'sparse':out['sparse'],
                  'drift':out['net_zero_count_positive_shrink'],'removed_sparse_examples_first_dates':examples},ensure_ascii=False,indent=2))
