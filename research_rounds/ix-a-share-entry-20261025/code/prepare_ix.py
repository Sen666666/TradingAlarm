"""Frozen full-pool B5/G1 replay, without an account engine or any fetch."""
from concurrent.futures import ProcessPoolExecutor
import sys,time
import pandas as pd
import numpy as np
from util_ix import *
from entry_rules import events

def worker(job):
 sid,rec=job
 sys.path.insert(0,str(B5/'code'))
 import api
 sys.path.insert(0,str(G1/'code'))
 from grade import classify
 from policies_g1 import project
 sys.path.insert(0,str(ROOT/'research_rounds/pv-participation-response-20261020/code'))
 from data_utils import eligible_prices
 a=rec['files']['signal'];p=OLD/'prepared-v2'/a['path'];assert sha(p)==a['sha256']
 signal=pd.read_parquet(p);f=eligible_prices(signal)[['open','high','low','close','volume','segment_id']].copy()
 f['valid_price_observation']=True;f['valid_strength_observation']=np.isfinite(f.volume)&f.volume.gt(0)
 t=time.time();r=api.run_b5(f,enhancements=False);e=r['evidence'];b=r['state'];g,j=classify(e);ix=project(e,b,g,'G1_IX');ee=events(g,ix)
 oldp=OLD/'prepared-v2'/rec['files']['states']['path'];assert sha(oldp)==rec['files']['states']['sha256'];old=pd.read_parquet(oldp)
 assert old.index.equals(b.index)
 for col in ['ready','target','entered','exited','floor','pending','pending_lower','pending_reclaim']:
  np.testing.assert_array_equal(b[col].to_numpy(dtype=float,na_value=np.nan),old[col].to_numpy(dtype=float,na_value=np.nan),err_msg=sid+':'+col)
 out=HERE/'signals'/f'{sid}.parquet'
 keep=pd.DataFrame(index=f.index)
 for c in ['segment_id','open','high','low','close','volume','valid_strength_observation']:keep[c]=f[c]
 for c in ['ready','target','entered','exited','floor','entry_kind']:keep['e0_'+c]=b[c]
 for c in ['grade','score','proposal','phase','z5','z21','fresh_up','up_reasons','promotion_blocked','acute_down','acute_up']:keep[c]=g[c]
 keep['strength_ready']=g.ready
 for c in ['target','entered','exited','floor','entry_kind','exit_reason']:keep['ix_'+c]=ix[c]
 keep=keep.join(ee)
 oldentry=np.flatnonzero(b.entered.to_numpy(dtype=float,na_value=0)==1);ages=np.full(len(f),np.nan)
 if len(oldentry):
  loc=np.searchsorted(oldentry,np.arange(len(f)),side='right')-1;ok=loc>=0;ages[ok]=np.arange(len(f))[ok]-oldentry[loc[ok]]
 keep['e0_age_observations']=ages
 # All public compact fields are saved once; no account-dependent rewriting.
 keep.to_parquet(out)
 z=keep.loc['2015-01-01':'2026-10-22']
 return dict(symbol=sid,rows=len(f),source_rows=len(signal),first=str(f.index[0].date()),last=str(f.index[-1].date()),E0_identity=True,events={k:int(z[k].sum()) for k in ENTRY_TYPES},raw_transition_counts={k:int(z['raw_'+k].sum()) for k in ENTRY_TYPES[1:]},strength_unknown=int(z.grade.isna().sum()),seconds=time.time()-t,source_signal=dict(path=str(p.resolve()),sha256=a['sha256']),source_states=dict(path=str(oldp.resolve()),sha256=rec['files']['states']['sha256']),output_sha256=sha(out))

def main():
 out=HERE/'signals';out.mkdir(exist_ok=False)
 ids=frozen();verify(ids);write(HERE/'old-identity-before.json',dict(recorded_at=now(),sha256=ids))
 records={r['series_id']:r for r in read(OLD/'prepared-v2/manifest.json')['series']}
 selection=read(OLD/'inputs-v2/selection.json');stocks=sorted(x['security_id'] for x in selection['lines'])
 assert len(stocks)==1711 and len(read(OLD/'inputs-v2/input-manifest.json')['sector_series'])==90
 jobs=[(sid,records[sid]) for sid in stocks];results=[]
 with ProcessPoolExecutor(max_workers=6) as pool:
  for row in pool.map(worker,jobs,chunksize=1):
   results.append(row)
   if len(results)%40==0:print(dict(done=len(results),total=len(jobs),rows=sum(x['rows'] for x in results),last=row['symbol']),flush=True)
 write(out/'manifest.json',dict(recorded_at=now(),stocks=len(stocks),eligible_stocks=1709,unknown_cap_retained=2,industry_source_unchanged=True,series=results,entry_totals={k:sum(x['events'][k] for x in results) for k in ENTRY_TYPES},B5_E0_identity_all=True,account_runs=0,workers=6,network_requests=0))
 print(dict(done=True,stocks=len(stocks),total_rows=sum(x['rows'] for x in results),events=read(out/'manifest.json')['entry_totals']),flush=True)

if __name__=='__main__':main()
