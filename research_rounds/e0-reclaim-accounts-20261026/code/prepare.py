from pathlib import Path
import sys,json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parents[1];R=O.parents[1];BASE=R/'research_rounds/tech-finite-compound-20261026';P=BASE/'prepared-v2';Q=R/'research_rounds/e0-reclaim-quick-20261026'
sys.path[:0]=[str(R/'research_rounds/b5-g1-20261025/code'),str(R/'research_rounds/pv-strength-b5-20261025/code'),str(R/'research_rounds/pv-participation-response-20261020/code')]
from policies_g1 import project
from api import run_b5
from policy import e0_policy
from data_utils import eligible_prices

def state(q,col,floor):
 b=pd.DataFrame(index=q.index);b['target']=q[col];b['floor']=q[floor];prior=q[col].shift().fillna(0).where(q.segment_id.eq(q.segment_id.shift()),0);b['entered']=q[col].eq(1)&prior.eq(0);b['entry_kind']='original_event';return b
if __name__=='__main__':
 out=O/'prepared/facts';out.mkdir(parents=True,exist_ok=False);audit=[]
 for path in sorted((P/'facts').glob('*.parquet')):
  f=pd.read_parquet(path);sid=path.stem;cached=Q/'states'/path.name
  if cached.exists():
   q=pd.read_parquet(cached);e=q[['close','segment_id']].copy();e['valid_price_observation']=True
   g=f[['g_grade','g_ready','g_fresh_up','g_acute_down']].copy();g.columns=['grade','ready','fresh_up','acute_down']
   a=state(q,'a','floor_a');b=state(q,'b','floor_b');control=project(e,a,g,'G1_I')
   for x,y in [('target','i_target'),('floor','i_floor'),('buy_event','i_buy')]:np.testing.assert_allclose(control[x].astype(float),f[y].astype(float),rtol=0,atol=0,equal_nan=True)
  else:
   e=eligible_prices(pd.read_parquet(P/'signals'/path.name))[['open','high','low','close','volume','segment_id']].copy();e['valid_price_observation']=True;e['valid_strength_observation']=np.isfinite(e.volume)&e.volume.gt(0)
   z=run_b5(e);a=z['state'];e=z['evidence'];e['decline_candidate']=False;b,_=e0_policy(e);g=f[['g_grade','g_ready','g_fresh_up','g_acute_down']].copy();g.columns=['grade','ready','fresh_up','acute_down']
   for x,y in [('target','e0_target'),('floor','e0_floor')]:np.testing.assert_allclose(a[x].astype(float),f[y].astype(float),rtol=0,atol=0,equal_nan=True)
  ip=project(e,b,g,'G1_I');new=f.copy();new['e0_target']=b.target;new['e0_floor']=b.floor;new['i_target']=ip.target;new['i_floor']=ip.floor;new['i_buy']=ip.buy_event
  new.to_parquet(out/path.name);audit.append(dict(symbol=sid,rows=len(f),e0_changed=int((new.e0_target!=f.e0_target).sum()),i_changed=int((new.i_target!=f.i_target).sum()),input_sha=hashlib.sha256(path.read_bytes()).hexdigest(),output_sha=hashlib.sha256((out/path.name).read_bytes()).hexdigest()))
 pd.DataFrame(audit).to_csv(O/'prepare-audit.csv',index=False);print('prepared',len(audit),flush=True)
