"""Original-window feature/receipt controls only. Never imports an old economic runner."""
from pathlib import Path
import json,sys,hashlib,time
import pandas as pd
from cohort_config import O,R,ORIGINAL_J
from market_adapter import MarketAdapter
start=time.monotonic();a=MarketAdapter();p=R/'independent_channel_full1709_preflight_v1/DAILY_STATES.parquet';rows=[]
ids=json.loads((O.parent/'PROTOCOL.json').read_text())['fixture_sids']
fields=['root_day','born','active','failed','root_unknown','phase','S_old','S_new','confirmed_at','confirmed_now','new_frontier','receipt','volume_credit_known','a_day','U','B','R','e0_raised']
for sid in ids:
 full=a.load_sid(sid);old=pd.read_parquet(p,filters=[('sid','==',sid)]).set_index('day')
 for window,lo,hi in [('2022','2022-01-01','2022-12-31'),('2024_924','2024-09-01','2024-12-31')]:
  z=old.loc[lo:hi].copy();original_dates=z.index;z.index=z.index.as_unit('ns');assert (z.index.as_unit('us')==original_dates.as_unit('us')).all();pd.testing.assert_frame_equal(full.loc[z.index,fields],z[fields],check_exact=True,check_dtype=False,check_freq=False)
  pd.testing.assert_series_equal(full.loc[z.index,'market_credit_Q'],z.Q,check_exact=True,check_dtype=False,check_names=False)
  pd.testing.assert_series_equal(full.loc[z.index,'market_frontier_F'],z.F,check_exact=True,check_dtype=False,check_names=False)
  rows.append(dict(sid=sid,window=window,rows=len(z),receipts=int(z.receipt.sum()),all_market_fields_exact=True))
 a._market.clear()
old=json.loads((O.parent/'OLD_TREE_SHA256_BEFORE.json').read_text());assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in old.items())
result=dict(result='PASS_ORIGINAL_TWO_WINDOWS_SIX_STOCK_FEATURE_RECEIPT_CONTROLS',checks=rows,old_files_hash_exact=len(old),historical_cash_loops=0,old_gate_test='one stale negative test blocked by existing run-once before reset/loop; retained separately, not PASS',seconds=time.monotonic()-start)
with (O/'READ_ONLY_CONTROL_QA.json').open('x') as f:json.dump(result,f,indent=2)
print(json.dumps(result),flush=True)
