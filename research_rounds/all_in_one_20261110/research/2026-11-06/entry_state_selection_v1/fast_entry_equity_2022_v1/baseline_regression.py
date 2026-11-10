"""Existing baseline prefix regression only, not a new-arm economic run."""
import lifecycle as l
from pathlib import Path
import pandas as pd,numpy as np
s=l.s;O=Path(__file__).resolve().parent;cut=pd.Timestamp('2022-01-31')
l.reset(False);s.run_window('A_UNION_B',stop=cut)
def equal(a,b,keys):
 a=a.sort_values(keys).reset_index(drop=True);b=b.sort_values(keys).reset_index(drop=True)
 assert len(a)==len(b),(len(a),len(b))
 for c in b:
  if c not in a:
   assert b[c].isna().all(),c;continue
  x,y=a[c],b[c]
  if pd.api.types.is_numeric_dtype(y) and not pd.api.types.is_bool_dtype(y):
   assert np.isclose(pd.to_numeric(x,errors='coerce').astype(float),y.astype(float),atol=1e-7,rtol=1e-12,equal_nan=True).all(),c
  else:
   def norm(v):
    if pd.isna(v):return ''
    z=str(v);return z[:10] if len(z)>10 and z[4:5]=='-' and z[7:8]=='-' and z[10:11] in ('T',' ') else z
   assert x.map(norm).equals(y.map(norm)),c
 return dict(rows=len(a),columns=len(b.columns),exact_with_numeric_tolerance=True)
qa={}
for name,rows,keys in [('ACTIONS',s.actions,['round_id','day','side']),('DECISIONS',s.decisions,['event_id']),('RANKING_AUDIT',s.ranking_audit,['event_id'])]:
 old=pd.read_csv(l.BASE/'dynamic'/(name+'.csv'),low_memory=False);old=old[old.arm.eq('A_UNION_B')&pd.to_datetime(old.day).le(cut)]
 qa[name]=equal(pd.DataFrame(rows),old,keys)
old=pd.read_csv(l.BASE/'dynamic/ROUNDS.csv',low_memory=False);old=old[old.arm.eq('A_UNION_B')&pd.to_datetime(old.status_day).le(cut)]
actual=pd.DataFrame(s.rounds);actual=actual[~actual.status.str.contains('CENSORED')]
qa['TERMINATED_ROUNDS']=equal(actual,old,['round_id'])
qa['scope']='Only original baseline through 2022-01-31, no fast-arm economics; reused original NET80 functions with adapter off. Full 2022 baseline remains cached.'
s.save(O/'BASELINE_OFF_PREFIX_QA.json',qa);print(qa,flush=True)
