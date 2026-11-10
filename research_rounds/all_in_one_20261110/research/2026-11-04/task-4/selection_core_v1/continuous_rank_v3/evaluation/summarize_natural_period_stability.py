"""Natural-year/month summaries of saved snapshots/runs, no list or clock recompute."""
from pathlib import Path
import numpy as np
import pandas as pd
from evaluation_core import distribution
O=Path(__file__).resolve().parent
for scope in ['primary','att_available']:
 p=O/scope;t=pd.read_parquet(p/'DAILY_AND_TRUE_WEEKEND_LIST_TURNOVER.parquet');s=pd.read_parquet(p/'DAILY_SELECTED_LIST_RUNS.parquet');a=pd.read_parquet(p/'SELECTED_EXISTING_PRICE_LABELS.parquet')
 rows=[]
 for grouping,n in [('year',4),('month',7)]:
  t[grouping]=t.date.str[:n]
  for (freq,period,method),g in t.groupby(['frequency',grouping,'method']):
   z={'grouping':grouping,'period':period,'frequency':freq,'method':method,'snapshot_count':len(g),'pair_known_count':int(g.pair_known.sum()),'pair_unknown_count':int((~g.pair_known).sum()),'entered_total':float(g.entered.sum()),'left_total':float(g.left.sum())}
   for value in ['symmetric_turnover','jaccard']:
    for key,v in distribution(g[value]).items():z[value+'_'+key]=v
   rows.append(z)
 pd.DataFrame(rows).to_csv(p/'LIST_TURNOVER_NATURAL_YEAR_MONTH.csv',index=False)
 birth=[]
 for grouping,n in [('start_year',4),('start_month',7)]:
  for period in sorted(a.date.str[:n].unique()):
   for method in sorted(a.method.unique()):
    g=s[s.method.eq(method)&s.start.str[:n].eq(period)];c=g[g.complete_uncensored];mass=int(c.length.sum())
    z={'grouping':grouping,'period':period,'method':method,'observed_new_runs':len(g),'left_censored':int(g.left_censored.sum()),'right_censored':int(g.right_censored.sum()),'complete_uncensored_runs':len(c),'complete_run_active_day_mass':mass,
     'attribution':'Full existing stage-clipped runs grouped by start year/month; not month-clipped runs and not current-month holdings.'}
    for key,v in distribution(c.length).items():z['complete_duration_'+key]=v
    z['complete_duration_max']=float(c.length.max()) if len(c) else np.nan
    for h in [1,3,5]:
     q=c[c.length.le(h)];z[f'complete_duration_le{h}_fraction']=len(q)/len(c) if len(c) else np.nan;z[f'duration_le{h}_complete_active_day_fraction']=float(q.length.sum()/mass) if mass else np.nan
    birth.append(z)
 pd.DataFrame(birth).to_csv(p/'LIST_DURATION_BY_START_YEAR_MONTH.csv',index=False)
print('Saved natural-year/month stability summaries; no ranking or return rerun.')
