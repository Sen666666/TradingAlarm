from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1');p=R/'local_v2'
e=pd.read_parquet(p/'SCORED_LOCAL_ENTRY_EVENTS.parquet');m=pd.read_csv(p/'QUARTERLY_MATURED_MODEL.csv');out=[]
for _,r in m[m.known].iterrows():
 c=pd.Timestamp(r.cutoff);q=e[(e.mature_dt<c)&(e.signal_dt>=c-pd.DateOffset(years=3))&e.open_proxy_ok&e.proxy_ret60.notna()&e.cell.eq(r.cell)]
 bl=q.groupby('entry_month').proxy_ret60.mean()
 out.append(dict(quarter=r.quarter,cell=r.cell,N=len(q),stocks=q.sid.nunique(),months=q.entry_month.nunique(),event_mean_gross=q.proxy_ret60.mean(),event_mean_net=q.proxy_ret60.mean()-.005,month_equal_gross=bl.mean(),month_equal_net=bl.mean()-.005,lcb=r.lcb_net))
a=pd.DataFrame(out);a.to_csv(p/'ESTIMAND_AND_COST_DIAGNOSTIC.csv',index=False)
v=R/'epoch_v3'/'rolling_prebreak_v31';c=pd.read_csv(v/'KNOWN_CASE_DAYS.csv');rows=[]
D=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')
for sid,g in c.groupby('sid'):
 f=pd.read_parquet(D/(sid+'.parquet'),columns=['day','price__open','price__high','price__low','price__close']).set_index('day')
 for _,r in g.iterrows():
  if not pd.isna(r.S):
   t=f.index.get_loc(pd.Timestamp(r.day));rr=r.to_dict()
   if t+1<len(f):
    z=f.iloc[t+1];rr['next_observed_common_open']=z.price__open;rr['open_support_risk_frac']=(z.price__open-r.S)/z.price__open;rr['open_gap']=z.price__open/r.close-1;rr['flat_OHLC_posthoc']=z.price__open==z.price__high==z.price__low==z.price__close
   rows.append(rr)
pd.DataFrame(rows).to_csv(v/'CASE_OPEN_RISK_DIAGNOSTIC.csv',index=False)
print('saved diagnostics')
