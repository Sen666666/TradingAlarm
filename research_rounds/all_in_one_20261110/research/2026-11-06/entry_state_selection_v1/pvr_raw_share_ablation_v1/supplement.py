"""Reporting-only supplement over sealed scores and existing evaluations; no new ranking."""
from pathlib import Path
import sys,json
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;R=O.parent;sys.path.insert(0,str(O));import experiment as e
c=pd.read_parquet(O/'ALL_CANDIDATES_WITH_LABELS.parquet');s=pd.read_parquet(O/'SELECTED_WITH_PRICE_LABELS.parquet')
rr=pd.read_parquet(O/'NATIVE_ROOT_SELECTION_COVERAGE.parquet')
changed=c[c.selection_group.isin(['added','removed'])].copy()
meta_path=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/metadata.json')
meta=json.loads(meta_path.read_text());changed['name']=changed.sid.map(lambda sid:meta.get(sid,{}).get('name'))
changed.to_csv(O/'ALL_19_SWAPS_WITH_LABELS.csv',index=False)
out=[];lost=[]
for h in [5,20,60]:
 for scope,ok in [('ALL_CANDIDATES_COMPLETE',c.groupby('day')['complete'+str(h)].all()),('SELECTED_UNION_COMPLETE',s.groupby('day')['complete'+str(h)].all())]:
  z=s[s.day.isin(ok[ok].index)&s.day.between('2022-01-01','2025-12-31')]
  means=z.groupby(['day','method'])['ret'+str(h)].mean().unstack()
  out.append(dict(period='2022_2025',scope=scope,H=h,N_each=len(z)//2,PVR_mean_day=float(means.PVR.mean()),SHARES_mean_day=float(means.SHARES.mean()),**e.blocks(means.SHARES-means.PVR,e.calendar())))
 a=rr.PVR_lag.between(0,h-1);b=rr.SHARES_lag.between(0,h-1)
 zz=rr[rr.big60&(a^b)].copy();zz['capture_horizon']=h;zz['change']=np.where(a.loc[zz.index],'lost','added');lost.append(zz)
pd.DataFrame(out).to_csv(O/'COMBINED_2022_2025_RESULTS.csv',index=False)
pd.concat(lost,ignore_index=True).to_csv(O/'BIG60_CAPTURE_CHANGED_ROOTS.csv',index=False)
# Identical membership can be verified even when future-label support is sparse.
major=[]
for name,mask in [('2024_ALL',c.day.between('2024-01-01','2024-12-31')),('2024_924',c.day.between('2024-09-24','2024-10-31')),('2026Q1_SEMICONDUCTOR',c.day.between('2026-01-01','2026-03-31')&c.sector.eq('URFI881121'))]:
 z=c[mask];major.append(dict(period=name,candidates=len(z),both=int(z.selection_group.eq('both').sum()),added=int(z.selection_group.eq('added').sum()),removed=int(z.selection_group.eq('removed').sum()),same_membership=not z.selection_group.isin(['added','removed']).any()))
pd.DataFrame(major).to_csv(O/'MAJOR_PERIOD_MEMBERSHIP.csv',index=False)
e.save('SUPPLEMENT_SOURCE_HASHES.json',{str(meta_path):e.sha(meta_path),str(O/'supplement.py'):e.sha(O/'supplement.py')})
print(pd.DataFrame(out).to_string(index=False));print(pd.DataFrame(major).to_string(index=False))
print(pd.concat(lost,ignore_index=True)[['sid','name','I_root','PVR_first','SHARES_first','capture_horizon','change']].to_string(index=False))
