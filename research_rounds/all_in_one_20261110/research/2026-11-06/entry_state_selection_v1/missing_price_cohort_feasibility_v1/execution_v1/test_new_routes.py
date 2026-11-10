"""No-cash new cohort routing, gate and candidate identity checks."""
from pathlib import Path
from types import SimpleNamespace
import json,hashlib
import pandas as pd
from cohort_config import O,CONFIG
from gates import require_economic_authorization
from joint_engine import JointConsumer
from market_adapter import MarketAdapter
assert not (O/'ROOT_EXTENSION_AUTHORIZATION.json').exists(),'Run this pre-authorization only'
for old in ['2022','2024']:
 try:require_economic_authorization(old);raise AssertionError('old window admitted')
 except ValueError as e:assert str(e)=='ONLY_NEW_FROZEN_WINDOWS'
for w in CONFIG:
 try:require_economic_authorization(w);raise AssertionError('unsigned run admitted')
 except PermissionError as e:assert str(e)=='NEW_COHORT_PARENT_AUTHORIZATION_REQUIRED'
rows=[]
for w,(lo,hi) in CONFIG.items():
 s=SimpleNamespace(cal=pd.DatetimeIndex([lo,hi]),EVENTS=[]);j=JointConsumer(s,MarketAdapter(),w)
 assert not j.states and not j.seq and not j.books
 assert j.window==w and j.start==pd.Timestamp(lo) and j.birth_end==pd.Timestamp(hi)
 x=j._candidate_frame();assert len(x) and x.window.eq(w).all() and x.day.between(lo,hi).all()
 assert not x.duplicated(['sid','day']).any() and x.receipt_id.notna().all()
 assert all(rid[1]==str(day.date()) for rid,day in zip(x.receipt_id,x.day))
 assert all(rid[0]==sid for rid,sid in zip(x.root_id,x.sid))
 rows.append(dict(window=w,candidates=len(x),candidate_sids=x.sid.nunique(),start_flat=True,dates_exact=True,ids_exact=True))
result=dict(status='PASS_NEW_ROUTE_NO_CASH',windows=rows,old_windows_rejected=True,unsigned_new_windows_rejected=True,cash_loops=0)
with (O/'NEW_ROUTE_QA.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result),flush=True)
