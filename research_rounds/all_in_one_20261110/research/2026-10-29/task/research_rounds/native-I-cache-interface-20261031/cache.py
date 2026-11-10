from pathlib import Path
import sys,json,hashlib,time,datetime,traceback,importlib.util,collections
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');R=ROOT/'research_rounds';OLD=R/'a-share-selection-e0-20261024/prepared-v2';IX=R/'ix-a-share-entry-20261025';NEW=ROOT/'TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared';END='2026-09-28';BEGIN='2025-07-01'
sys.path[:0]=[str(R/'pv-strength-b5-20261025/code'),str(R/'b5-g1-20261025/code'),str(R/'pv-participation-response-20261020/code')]
from policy import e0_policy
from policies_g1 import project
from data_utils import eligible_prices
sys.path.insert(0,str(ROOT));from TradingAlarm.desk.refresh import prepare_facts
RECORDS={r['series_id']:r for r in json.loads((OLD/'manifest.json').read_text())['series']}
IXRECORDS={r['symbol']:r for r in json.loads((IX/'signals/manifest.json').read_text())['series']}
COLS=['close','segment_id','e0_target','e0_floor','i_target','i_floor','i_buy','g_grade','g_fresh_up','g_acute_down','g_ready','e0_ready','factor','raw_close']
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False))
def derive(sid,cut=END):
 start=time.monotonic();rec=RECORDS[sid];paths={k:OLD/rec['files'][k]['path'] for k in ['signal','events','states']}
 for k,p in paths.items():assert sha(p)==rec['files'][k]['sha256'],(sid,k)
 ip=IX/'signals'/f'{sid}.parquet';assert sha(ip)==IXRECORDS[sid]['output_sha256']
 signal=pd.read_parquet(paths['signal']).loc[:cut];x=pd.read_parquet(ip).loc[:cut];event=pd.read_parquet(paths['events']).reindex(x.index);state=pd.read_parquet(paths['states']).reindex(x.index);valid=eligible_prices(signal);assert valid.index.equals(x.index),(sid,'same price-observation clock')
 if x.empty:return pd.DataFrame(columns=COLS,index=pd.DatetimeIndex([],name=signal.index.name)),dict(sid=sid,status='no_observation_before_cut',rows=0,seconds=time.monotonic()-start)
 for c in ['open','high','low','close','volume','segment_id']:np.testing.assert_equal(x[c].to_numpy(),valid[c].to_numpy(),err_msg=sid+'/'+c)
 e=x[['segment_id','open','high','low','close','volume']].copy();e['valid_price_observation']=True;e['price_observation']=e.groupby('segment_id',sort=False).cumcount();e['event']=event.event;e['confirmed_pivot_price']=event.confirmed_pivot_price;e['ready']=state.ready;e['previous_close']=e.groupby('segment_id',sort=False).close.shift()
 v=e.volume.where(np.isfinite(e.volume)&e.volume.gt(0));e['volume_baseline']=v.groupby(e.segment_id,sort=False).transform(lambda q:q.shift().rolling(21,min_periods=21).median())
 for c in ['volume_ratio','high_effort','declined']:e[c]=state[c]
 e['decline_candidate']=False;e['candidate_lower']=np.nan;e['candidate_reclaim']=np.nan
 base,_=e0_policy(e);assert not base.pending.fillna(0).any()
 g=x[['grade','strength_ready','fresh_up','acute_down']].rename(columns={'strength_ready':'ready'});out=project(e,base,g,'G1_I')
 keep=x[['close','segment_id']].copy()
 for mode,frame in [('e0',base),('i',out)]:
  for c in ['target','floor']:keep[mode+'_'+c]=frame[c]
 keep['i_buy']=out.buy_event
 for c in ['grade','fresh_up','acute_down','ready']:keep['g_'+c]=g[c]
 keep['e0_ready']=base.ready;keep['factor']=signal.adjustment_factor.reindex(keep.index);keep['raw_close']=signal.raw_close.reindex(keep.index);keep=keep[COLS]
 return keep,dict(sid=sid,status='derived',warm_from=str(keep.index.min().date()),warm_rows=len(keep),rows=len(keep.loc[BEGIN:]),i_events=int(keep.loc[BEGIN:,'i_buy'].sum()),unknown_grade=int(keep.loc[BEGIN:,'g_grade'].isna().sum()),IX_target_difference=int((out.target.astype(float)!=x.ix_target.astype(float)).sum()),seconds=time.monotonic()-start,input_sha={str(p):sha(p) for p in list(paths.values())+[ip]})
def raw_reference(sid,cut=END):
 sys.path.insert(0,str(R/'innovative-drug-sfw3-20261028/code'));import drug_common as DC
 rec=next(r for r in read(NEW/'manifest.json')['series'] if r['series_id']==sid);assert sha(rec['raw']['path'])==rec['raw']['sha256'];raw=DC.C.read_raw(rec['raw']['path'],rec).loc[:cut];ev,_=DC.C.read_actions(rec,Path(rec['raw']['path']).parent);ev=[e for e in ev if e['effective_date']<=cut];parts=[]
 for j,part in enumerate(DC.C.source_segments(raw,rec)):
  f=DC.C.prepare_signal(raw.loc[part['start']:part['end']],rec,ev,cutoff=cut);f['segment_id']=j;parts.append(f)
 return prepare_facts(pd.concat(parts))[COLS]
def pilot():
 start=time.monotonic();ids=['000002.SZ','000001.SZ','000009.SZ'];rows=[];(O/'pilot').mkdir(exist_ok=False)
 for sid in ids:
  fast,receipt=derive(sid);reference_start=time.monotonic();ref=raw_reference(sid);reference_seconds=time.monotonic()-reference_start
  pd.testing.assert_frame_equal(fast,ref,check_exact=True,check_dtype=False,check_freq=False)
  short,_=derive(sid,'2026-06-30');pd.testing.assert_frame_equal(short,fast.loc[:'2026-06-30'],check_exact=True,check_dtype=False,check_freq=False)
  # Raw same-version full history also confirms cache G1 event/state semantics.
  receipt.update(reference_seconds=reference_seconds,all_fields_exact_to_L0_reference=True,physical_prefix_exact=True,protection_and_I_events_exact=True);fast.loc[BEGIN:END].to_parquet(O/'pilot'/f'{sid}.parquet');rows.append(receipt);print('PILOT',sid,receipt['seconds'],reference_seconds,'PASS',flush=True)
 direct=sum(r['seconds'] for r in rows)/3;estimate=direct*1709/6*1.35+15
 save(O/'PILOT_GATE.json',dict(passed=True,receipts=rows,mean_fast_seconds=direct,estimated_6worker_all1709_seconds=estimate,estimate_basis='pilot observed per-security time/6 +35% contention allowance +15s metadata/write audit',seconds=time.monotonic()-start,full_allowed=estimate<=180));print('ESTIMATE',estimate,flush=True)
def job(args):
 sid,deadline=args
 if time.monotonic()>=deadline:return dict(sid=sid,status='deferred_180s_budget',rows=None)
 f,r=derive(sid);path=O/'facts'/f'{sid}.parquet';f.loc[BEGIN:END].to_parquet(path);r['output_sha256']=sha(path);save(O/'receipts'/f'{sid}.json',r);return r
def full():
 from concurrent.futures import ProcessPoolExecutor
 gate=read(O/'PILOT_GATE.json');assert gate['passed'] and gate['full_allowed'];start=time.monotonic();deadline=start+180;h=np.load(NEW/'h1.npz');ids=sorted(str(s) for s in h['symbols'] if not str(s).startswith('URFI'));assert len(ids)==1709;(O/'facts').mkdir(exist_ok=False);(O/'receipts').mkdir();rows=[]
 sources=[Path(__file__),ROOT/'TradingAlarm/desk/refresh.py',R/'pv-strength-b5-20261025/code/policy.py',R/'b5-g1-20261025/code/policies_g1.py',R/'b5-g1-20261025/code/grade.py',OLD/'manifest.json',IX/'signals/manifest.json',NEW/'manifest.json',O/'PROTOCOL.txt']
 save(O/'FREEZE.json',dict(before_full_cache=True,new_economic_paths=0,stocks=ids,output_scope=[BEGIN,END],full_warm_history=True,source_sha={str(p):sha(p) for p in sources},created_at=datetime.datetime.now(datetime.timezone.utc).isoformat()))
 with ProcessPoolExecutor(max_workers=6) as pool:
  for r in pool.map(job,[(s,deadline) for s in ids]):
   rows.append(r)
   if len(rows)%200==0:print('FULL',len(rows),round(time.monotonic()-start,2),flush=True)
 deferred=[r for r in rows if r['status']=='deferred_180s_budget'];save(O/'FULL_GATE.json',dict(passed=not deferred,stocks=1709,completed=1709-len(deferred),deferred=deferred,seconds=time.monotonic()-start,records=rows,new_accounts=0,output_start=BEGIN,output_end=END,full_warm_history_preserved=True,unfiltered_native_I=True));print('FULL COMPLETE',len(rows),'deferred',len(deferred),time.monotonic()-start,flush=True)
if __name__=='__main__':
 try:pilot() if sys.argv[1]=='pilot' else full()
 except BaseException as e:save(O/(sys.argv[1]+'_ERROR.json'),dict(error=repr(e),traceback=traceback.format_exc()));raise
