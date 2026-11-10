from pathlib import Path
import pandas as pd, numpy as np
R=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
D=Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/daily_signal_cache_pilot20_v1/full_universe_v1/artifacts')
ev=pd.read_csv(R/'CASE_ALL_EVENTS.csv')
for sid,g in ev.groupby('sid'):
 f=pd.read_parquet(D/(sid+'.parquet'),columns=['price__open','price__close'])
 o=f.price__open.to_numpy();c=f.price__close.to_numpy()
 for i,row in g.iterrows():
  if pd.isna(row.first_open):continue
  ent=int(row.first_open)
  for h in [20,60]:
   p=c[ent:ent+h];ok=len(p)==h and np.isfinite(p).all() and (p>0).all()
   ev.loc[i,'entry_inclusive_ret'+str(h)]=p[-1]/o[ent]-1 if ok else np.nan
   ev.loc[i,'entry_inclusive_mae'+str(h)]=min(0,p.min()/o[ent]-1) if ok else np.nan
   ev.loc[i,'entry_inclusive_mfe'+str(h)]=max(0,p.max()/o[ent]-1) if ok else np.nan
ev.to_csv(R/'REPORTING_CASE_EVENTS_CORRECTED_PATHS.csv',index=False)
print('corrected entry paths',ev.first_open.notna().sum())
