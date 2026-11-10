"""Export original canonical traces from frozen numeric caches; never call calculate/derive."""
from pathlib import Path
import sys,json,time,hashlib,traceback
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'q2-normal-continuation-20261031'))
import continuation as E
J,L,T=E.J,E.L,E.J.T
BEGIN='2022-01-01';END='2022-12-30';CUT='2022-06-30'
KEYS=['canonical_series','scale_id','source_segment','original_E0_episode_id','confirmed_day','receipt_id','decision_evidence_key','formation_start_exclusive','formation_end_inclusive','anchor_observation_id','confirmation_observation_id','previous_market_receipt_id','original_candidate','original_scale','scale_frozen_at','new_advance_price_event_ids','new_log_price_displacement','original_credit','evidence_signature','trace_unknown']
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):E.IO.write_json(p,T.norm(J.W.canon(x)))
def compact(rows):return [{k:r[k] for k in KEYS} for r in rows]
def one(r,industry=False,prefix=False):
 started=time.monotonic();sid=r['series' if industry else 'symbol'];refs=r['refs'];sources={}
 for path,h in r['source_sha256'].items():assert sha(path)==h,(sid,'source changed',path);sources[path]=h
 for path,h in r['output_sha256'].items():assert sha(path)==h,(sid,'original output changed',path)
 qfull=pd.read_parquet(refs['CP1_input']);zfull=pd.read_parquet(refs['CP1']);q=qfull.loc[:END];z=zfull.loc[:END]
 ep=q.e0_valid if industry else pd.read_parquet(refs['facts'],columns=['e0_target']).e0_target.reindex(q.index).astype(bool)
 eventpath=next(p for p in sources if p.endswith('/events.parquet'));events=pd.read_parquet(eventpath).reindex(q.index)
 T.BEGIN=BEGIN;T.END=END
 rr,_,checks=T.trace(sid,q,z,events,ep)
 expected=z.loc[BEGIN:END].receipt.eq(True);assert [r['confirmed_day'] for r in rr]==[str(d.date()) for d in z.loc[BEGIN:END].index[expected]],(sid,'trace/native receipt dates')
 assert len({r['receipt_id'] for r in rr})==len(rr)
 assert not any(r['trace_unknown'] for r in rr),(sid,'unknown trace origins')
 assert all(r['formation_start_exclusive']<r['confirmed_day']==r['formation_end_inclusive'] for r in rr)
 checks=dict(checks,exact_native_receipt_dates=True,unique_canonical_ids=True,formation_known=True,numeric_models_recomputed=False)
 if industry:
  state=pd.read_parquet(refs['state']);by={x['day']:x for x in state.to_dict('records')}
  assert all(by[x['confirmed_day']]['receipt_id']==x['receipt_id'] for x in rr);checks['fullwarm_industry_state_receipt_IDs_exact']=True
 if prefix:
  sr,_,_=T.trace(sid,q.loc[:CUT],z.loc[:CUT],events.loc[:CUT],ep.loc[:CUT]);assert compact(sr)==compact([x for x in rr if x['confirmed_day']<=CUT]);checks['physical_June30_ID_interval_prefix_exact']=True
  # Compare to the originally frozen 2025-26 receipt export without changing it.
  T.BEGIN='2025-07-01';T.END='2026-06-30';evfull=pd.read_parquet(eventpath).reindex(qfull.index);epfull=qfull.e0_valid if industry else pd.read_parquet(refs['facts'],columns=['e0_target']).e0_target.reindex(qfull.index).astype(bool)
  old,_,_=T.trace(sid,qfull.loc[:T.END],zfull.loc[:T.END],evfull.loc[:T.END],epfull.loc[:T.END]);assert compact(old)==read(refs['receipts']),(sid,'old original receipt identity differs');checks['existing_2025_26_export_exact']=True;T.BEGIN=BEGIN;T.END=END
 path=O/'inputs'/('industry-receipts' if industry else 'stock-receipts')/(sid+'.json');save(path,compact(rr))
 result=dict(sid=sid,industry=industry,refs=refs,sources=sources,original_output_sha256=r['output_sha256'],output_path=str(path),output_sha256=sha(path),receipt_count=len(rr),observations=len(q),checks=checks,seconds=time.monotonic()-started)
 save(O/'inputs/items'/(sid+'.json'),result);return result
def main():
 started=time.monotonic();sm=read(L.U/'STOCK_MANIFEST.json');im=read(L.U/'INDUSTRY_MANIFEST.json');freeze=O/'inputs/FREEZE.json'
 identity={str(p):sha(p) for p in [Path(__file__),L.U/'STOCK_MANIFEST.json',L.U/'INDUSTRY_MANIFEST.json',L.U/'FREEZE.json',W/'cp1-evidence-trace-20261031/trace.py']}
 if freeze.exists():assert read(freeze)['source_SHA256']==identity
 else:save(freeze,dict(before_export=True,window=[BEGIN,END],source_SHA256=identity,fullwarm_numeric_cache_reuse=True,new_model_calculations=0,account_paths=0,workers=1))
 pilotstocks=sorted(sm,key=lambda x:x['symbol'])[:3];pilotindustries=sorted(im,key=lambda x:x['series'])[:3];pilotids={r['symbol'] for r in pilotstocks}|{r['series'] for r in pilotindustries};pilot=[]
 for r in pilotstocks+pilotindustries:pilot.append(one(r,'series' in r,True))
 ps=sum(x['seconds'] for x in pilot);estimate=sum(x['seconds'] for x in pilot if not x['industry'])/3*1709+sum(x['seconds'] for x in pilot if x['industry'])/3*90
 save(O/'inputs/PILOT.json',dict(passed=True,series=pilot,pilot_seconds=ps,conservative_total_estimate_seconds=estimate,estimate_includes_pilot_extra_old_export_and_prefix_checks=True,new_models=0));print('PILOT_PASS',round(ps,3),'total_estimate',round(estimate,2),flush=True)
 rows=[];resumed=0
 for i,r in enumerate(sm+im):
  sid=r.get('symbol',r.get('series'));item=O/'inputs/items'/(sid+'.json');old=read(item) if item.exists() else None
  if old and old['original_output_sha256']==r['output_sha256'] and Path(old['output_path']).exists() and sha(old['output_path'])==old['output_sha256']:out=old;resumed+=1
  else:out=one(r,'series' in r)
  rows.append(out)
  if (i+1)%100==0:
   save(O/'inputs/PROGRESS.json',dict(done=len(rows),total=1799,seconds=time.monotonic()-started,resumed=resumed,last=sid));print('EXPORT',len(rows),round(time.monotonic()-started,2),flush=True)
 save(O/'inputs/MANIFEST.json',rows);save(O/'inputs/COMPLETION.json',dict(passed=True,series=len(rows),stock_receipts=sum(r['receipt_count'] for r in rows if not r['industry']),industry_receipts=sum(r['receipt_count'] for r in rows if r['industry']),seconds=time.monotonic()-started,original_outputs_unchanged=True,new_models=0,new_account_paths=0));print('EXPORT_DONE',round(time.monotonic()-started,2),flush=True)
if __name__=='__main__':
 try:main()
 except BaseException as e:save(O/'inputs/ERROR.json',dict(type=type(e).__name__,reason=str(e),traceback=traceback.format_exc(),account_paths=0));raise
