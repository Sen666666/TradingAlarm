import adapter as M
from pathlib import Path
import sys,time,signal,traceback,shutil
O=M.O
old=M.load('frozen_l0_identity_functions',O.parent/'lr1-cp1-add-preflight-20261031/run_stage.py')
rows,obj=old.rows,old.obj
def main():
 sec,stage=sys.argv[1:3];assert sec in ['TECH','DRUG'] and stage in ['gate','prefix','full']
 p=O/'COMPUTE_TIME.json';prior=M.read(p) if p.exists() else dict(seconds=0,stages=[]);left=300-prior['seconds'];assert left>0;t=time.monotonic();root=O/sec/stage;root.mkdir(parents=True,exist_ok=False);shutil.copyfile(M.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json');r=None;status='started'
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('L0 history total300s compute budget')));signal.setitimer(signal.ITIMER_REAL,left)
 try:
  freeze=M.read(O/'FREEZE.json');assert M.read(O/'DATA_GATE.json')['passed'] and all(M.sha(x)==h for x,h in freeze['sha256'].items())
  if stage!='gate':assert M.read(O/sec/'gate/GATE.json')['passed']
  if stage=='full':assert M.read(O/sec/'prefix/GATE.json')['passed']
  cut='2021-12-31' if stage=='prefix' else None;end='2019-03-29' if stage=='gate' else cut or '2023-12-29';policies=['L0','OFF'] if stage=='gate' else ['L0'];stresses=['base','delay1'] if stage=='prefix' else ['base','cost2','delay1']
  r=M.Pilot(sec,root,cut,stresses,policies)
  if stage=='gate':
   for a in r.accounts.values():a.verify_index=True
  if stage=='full':r.record_risk=True
  print(dict(sector=sec,stage=stage,init=time.monotonic()-t,paths=len(r.accounts),budget=left),flush=True);sim=time.monotonic();r.run(end);simulation=time.monotonic()-sim;M.dump(r,root/'results')
  if stage=='gate':checks=[old.identity(r,'OFF_'+s,root/'results','L0_'+s,end) for s in stresses]
  elif stage=='full':checks=[old.identity(r,'L0_'+s,O/sec/'prefix/results','L0_'+s,'2021-12-31') for s in ['base','delay1']]
  else:checks=[]
  assert all(not a.add_enabled and not a.ops and not a.cp_used and all(x['kind']=='core' for x in a.layers) for a in r.accounts.values())
  for a in r.accounts.values():
   assert all('2019-01-02'<=str(x['at'])[:10]<=end for x in a.trades)
  M.save(root/'GATE.json',dict(passed=True,checks=checks,rows=len(r.daily),simulation_seconds=simulation,initialization_includes_existing_cache_loading=True,ADD_disabled=True,ADD_credit_events=0,all_trade_dates_within_frozen_window=True,physical_cutoff=cut))
  if stage=='full':
   analysis=M.load('l0_history_independent_analysis',O/'analyze.py');analysis.module.main()
   lock=M.load('l0_current_lock_facts',O/'lock_audit.py');lock.audit(sec,r)
  assert all(M.sha(x)==h for x,h in freeze['sha256'].items());status='complete'
 except BaseException as e:
  status='failed';M.save(root/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()))
  if r is not None and not (root/'results').exists():M.dump(r,root/'failed-results')
  raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-t;s=M.read(p) if p.exists() else dict(seconds=0,stages=[]);s['seconds']+=elapsed;s['stages'].append(dict(sector=sec,stage=stage,status=status,seconds=elapsed));M.save(p,s);M.save(root/'TIMING.json',dict(status=status,seconds=elapsed,total_seconds=s['seconds']));print(dict(sector=sec,stage=stage,status=status,seconds=elapsed,total=s['seconds']),flush=True)
if __name__=='__main__':main()
