"""One F1 real-volume cold reference only. No neutral assembly or account imports."""
from pathlib import Path
from datetime import datetime,timezone
import ast,sys,json,hashlib,time,signal,traceback
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;T=O.parents[2];W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds');ROOT=Path('/Users/bytedance/Documents/ChatGPT/money');R=ROOT/'research_rounds';U=W/'universe-cp1-inputs-20261031';END='2026-06-30'
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def fail_timeout(*args):raise TimeoutError('root60s F1 cold budget exceeded')
def exact(a,b):
 aa=a.copy(deep=False);bb=b.copy(deep=False);aa.index=a.index.as_unit('ns');bb.index=b.index.as_unit('ns');pd.testing.assert_frame_equal(aa,bb,check_exact=True,check_dtype=False,check_freq=False)
def source_function(path,name,env):
 n=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)and n.name==name)
 # Exact source AST node, no transformation and no module-level refresh side effects.
 exec(compile(ast.Module(body=[n],type_ignores=[]),str(path),'exec'),env);return env[name]
def main():
 assert not(O/'DONE.json').exists(),'F1 reference already complete; no repeat'
 freeze=read(O/'PRE_RUN_FREEZE.json');assert all(sha(p)==h for p,h in freeze['sources'].items())
 assert freeze['risk_owner_confirmed_not_run_F1']is True
 signal.signal(signal.SIGALRM,fail_timeout);signal.alarm(60);started=time.monotonic();checks=[];outs=[]
 refresh=ROOT/'TradingAlarm/desk/refresh.py';prepare=source_function(refresh,'prepare_facts',dict(ROOT=ROOT,sys=sys,np=np,pd=pd))
 # Original model module is pure; exec original bytes in isolated dict, no write path.
 cp_path=R/'continuous-protection-lines-20261028/code/model.py';cp_env={'__name__':'F1_original_CP1_reference'};exec(compile(cp_path.read_text(),str(cp_path),'exec'),cp_env);calculate=cp_env['calculate']
 num_path=R/'pv-participation-response-20261020/code/numeric.py';numenv={'__name__':'F1_original_numeric_reference'};exec(compile(num_path.read_text(),str(num_path),'exec'),numenv);event_frame=numenv['event_frame_numeric']
 sm={r['symbol']:r for r in read(U/'STOCK_MANIFEST.json')};im={r['series']:r for r in read(U/'INDUSTRY_MANIFEST.json')}
 for sid,industry in [('000001.SZ',False),('URFI881155',True)]:
  r=im[sid]if industry else sm[sid];sp=next(p for p in r['source_sha256']if p.endswith('/signal.parquet'));ep=next(p for p in r['source_sha256']if p.endswith('/events.parquet'));src=pd.read_parquet(sp).loc[:END]
  t=time.monotonic();fresh=prepare(src);elapsed=time.monotonic()-t
  from data_utils import eligible_prices
  valid=eligible_prices(src);events=[]
  for _,g in valid.groupby('segment_id',sort=False):events.append(event_frame(g.close,g.volume,joint=True,event_exit=False))
  cold_events=pd.concat(events).sort_index();gold_events=pd.read_parquet(ep).reindex(cold_events.index);common=[c for c in cold_events if c in gold_events];exact(cold_events[common],gold_events[common]);checks.append(dict(series=sid,check='original numeric all common event columns exact fullwarm',columns=common,rows=len(fresh)))
  goldq=pd.read_parquet(r['refs']['CP1_input']).loc[:END];q=goldq.copy()
  for c in ['close','segment_id']:q[c]=fresh[c]
  q['e0_down']=cold_events.event.eq(-1)
  if industry:
   q['e0_valid']=fresh.e0_target.astype(bool);q['i_floor']=fresh.e0_floor
   exact(q,goldq);fields=['close','segment_id','e0_target','e0_floor']
  else:
   goldf=pd.read_parquet(r['refs']['facts']).loc[:END];exact(fresh,goldf);fields=list(fresh.columns)
   ixp=next(p for p in r['source_sha256']if '/ix-a-share-entry-'in p);ix=pd.read_parquet(ixp).loc[fresh.index]
   for a,b in {'g_grade':'grade','g_ready':'strength_ready','g_fresh_up':'fresh_up','g_acute_down':'acute_down'}.items():pd.testing.assert_series_equal(fresh[a],ix[b],check_exact=True,check_dtype=False,check_names=False,check_freq=False)
   q['i_target']=fresh.i_target;q['i_floor']=fresh.i_floor;q['e0_valid']=fresh.i_target.astype(bool);exact(q,goldq)
  coldcp=calculate(q);goldcp=pd.read_parquet(r['refs']['CP1']).loc[:END];exact(coldcp,goldcp);checks.append(dict(series=sid,check='cold NR1 facts/G1 and original CP1 all columns exact',facts_fields=fields,CP1_fields=list(coldcp.columns),rows=len(q),fullwarm_CP1_receipts=int(coldcp.receipt.sum()),prepare_seconds=elapsed))
  for name,frame in [('facts',fresh),('events',cold_events),('CP1_input',q),('CP1',coldcp)]:
   p=O/(sid+'.'+name+'.parquet');frame.to_parquet(p);outs.append(str(p))
 # Optional same F1 stock original PVR only, all frozen existing points; no neutral.
 pvrp=W/'pvr-current-v3-information-capital-20261101/original_score_function.py';env=dict(np=np,pd=pd);exec(compile(pvrp.read_text(),str(pvrp),'exec'),env)
 sid='000001.SZ';r=sm[sid];sp=next(p for p in r['source_sha256']if p.endswith('/signal.parquet'));z=env['score'](pd.read_parquet(sp).loc[:END]);legacy=W/'pvr-current-v3-information-capital-20261101/pvr-cache'/f'{sid}.parquet';g=pd.read_parquet(legacy);exact(z.reindex(g.index),g)
 p2024=T/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/scores'/f'{sid}.parquet';pnative=W/'pvr-slot1-native-readiness-20261101/scores'/f'{sid}.parquet';days=set()
 for p in [p2024,pnative]:
  g=pd.read_parquet(p);exact(z[['score']].reindex(g.index),g);days.update(g.index)
 out=O/'000001.SZ.PVR.parquet';z.to_parquet(out);outs.append(str(out));checks.append(dict(series=sid,check='cold original PVR exact all existing full8fields points and market-calendar score',legacy_full8fields_points=13,unique_existing_score_days=len(days),fullwarm_old8field_reference=False))
 modules={k:str(v.__file__)for k,v in sys.modules.items()if k in ['data_utils','api','evidence','arithmetic','policy','grade','policies_g1']}
 assert all(sha(p)==h for p,h in freeze['sources'].items()),'source modified during reference'
 signal.alarm(0);save('DONE.json',dict(status='F1_REAL_COLD_FULLWARM_EXACT',seconds=time.monotonic()-started,checks=checks,source_sha256_unchanged=True,modules=modules,outputs={p:sha(p)for p in outs},neutral_runs=0,account_runner_objects=0,source_mode_scope='same F1 only, not a fourth fixture; F2/F3 untested here',PVR_reference_scope='13old full8fields +968market score dates; rest fullwarm source/prefix only, no manufactured old reference'))
 print((O/'DONE.json').read_text())
if __name__=='__main__':
 try:main()
 except BaseException as e:signal.alarm(0);save('ERROR.json',dict(type=type(e).__name__,error=str(e),traceback=traceback.format_exc(),stop_no_source_or_cache_changes=True));raise
