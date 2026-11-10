from pathlib import Path
import sys,json,hashlib
import numpy as np,pandas as pd
from concurrent.futures import ProcessPoolExecutor
ROOT=Path(__file__).resolve().parents[3]; OUT=Path(__file__).resolve().parents[1]
SRC=ROOT/'research_rounds/tech-finite-compound-20261026/prepared-v2'
sys.path[:0]=[str(ROOT/'research_rounds/pv-strength-b5-20261025/code'),str(ROOT/'research_rounds/pv-participation-response-20261020/code')]
from api import run_b5
from policy import e0_policy
from data_utils import eligible_prices

def work(path):
 sid=path.stem; f=eligible_prices(pd.read_parquet(path))[['open','high','low','close','volume','segment_id']].copy()
 f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
 z=run_b5(f);a=z['state']; ev=z['evidence'].copy();ev['decline_candidate']=False;b,_=e0_policy(ev)
 old=pd.read_parquet(SRC/'facts'/path.name)
 assert a.index.equals(old.index),sid
 np.testing.assert_array_equal(a.target.astype(float),old.e0_target.astype(float))
 np.testing.assert_allclose(a.floor.astype(float),old.e0_floor.astype(float),rtol=0,atol=0,equal_nan=True)
 out=f.copy();out['a']=a.target;out['b']=b.target;out['floor_a']=a.floor;out['floor_b']=b.floor;out['entry_kind']=a.entry_kind
 (OUT/'states').mkdir(exist_ok=True);out.to_parquet(OUT/'states'/path.name)
 records=[]
 for m in z['ledger'].itertuples():
  if m.independent_entry!=1 or m.resolved_date<'2024-01-02':continue
  t=pd.Timestamp(m.resolved_date);g=out.loc[out.segment_id.astype(str).eq(str(m.segment_id))];n=g.index.get_loc(t);c=float(g.close.iloc[n]);aft=g.iloc[n+1:];on=np.flatnonzero(aft.b.to_numpy()==1)
  rec=dict(symbol=sid,date=m.resolved_date,created=m.created_date,lower=m.lower,reclaim=m.reclaim,close=c,b_active=int(g.b.iloc[n]),b_delay=0 if g.b.iloc[n] else (int(on[0]+1) if len(on) else None),activity_ratio=m.resolution_volume_ratio,past21=float(c/g.close.iloc[n-21]-1) if n>=21 else None)
  for h in [21,63]:
   q=aft.iloc[:h];ok=len(q)==h
   rec.update({f'ret{h}':float(q.close.iloc[-1]/c-1) if ok else None,f'max{h}':float(q.close.max()/c-1) if ok else None,f'min{h}':float(q.close.min()/c-1) if ok else None,f'break{h}':bool((q.close<=m.lower).any()) if ok else None})
  records.append(rec)
 q=out.loc['2024-01-02':];return records,dict(symbol=sid,rows=len(f),extra=int(((q.a==1)&(q.b==0)).sum()),missing=int(((q.a==0)&(q.b==1)).sum()),source_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
if __name__=='__main__':
 paths=sorted((SRC/'signals').glob('*.parquet'));paths=[p for p in paths if p.stem.endswith(('.SH','.SZ','.BJ'))];assert len(paths)==407,len(paths)
 recs=[];audit=[]
 with ProcessPoolExecutor(max_workers=4) as pool:
  for r,s in pool.map(work,paths):
   recs+=r;audit.append(s)
   if len(audit)%40==0:print('verified',len(audit),flush=True)
 pd.DataFrame(recs).to_csv(OUT/'events.csv',index=False);pd.DataFrame(audit).to_csv(OUT/'audit.csv',index=False)
 print('DONE',len(audit),len(recs),flush=True)
