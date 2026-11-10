import adapter as m
from pathlib import Path
import time,sys,signal,shutil,traceback,json,gzip
w=m.w;O=m.O
legacy=w.load('rb1_reuse_identity',O.parent/'entry-loss-budget-cost2-funnel-20261031/run_cost2.py')
def save(p,x):w.K.save(p,x)
def main():
 sec,stage=sys.argv[1:3];assert sec in ['TECH','DRUG'] and stage in ['off','prefix-open','prefix-cut','on']
 timing=O/'COMPUTE_TIME.json';prior=w.read(timing) if timing.exists() else dict(seconds=0,stages=[]);left=300-prior['seconds'];assert left>0
 t=time.monotonic();root=O/sec/stage;root.mkdir(parents=True,exist_ok=False);shutil.copyfile(w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json');status='started'
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('RB1 current ACT total300s compute budget')));signal.setitimer(signal.ITIMER_REAL,left)
 try:
  freeze=w.read(O/'FREEZE.json');assert all(w.sha(p)==h for p,h in freeze['sha256'].items());assert w.read(O.parent/'rb1-act-port-preflight-20261031/SYNTHETIC.json')['passed']
  if stage!='off':assert w.read(O/sec/'off/IDENTITY.json')['passed']
  if stage=='on':
   for s in ['TECH','DRUG']:assert w.read(O/s/'off/IDENTITY.json')['passed'] and w.read(O/s/'prefix-cut/IDENTITY.json')['passed']
  prefix=stage.startswith('prefix');cut='2025-12-31' if stage=='prefix-cut' else None;end='2025-12-31' if prefix else '2026-10-27';stresses=['base'] if prefix else ['base','cost2','delay1'];enabled=stage!='off'
  R,E,core,prep,mode=m.setup(sec,root,enabled,cut);print(dict(sector=sec,stage=stage,setup_seconds=time.monotonic()-t,remaining_seconds=left),flush=True)
  runner=R.run(root/'accounts-v2',modes=[mode],stresses=stresses,start='2023-12-29',end=end,cutoff=cut,technical=stage!='on');ids=list(runner.accounts)
  if stage=='off':
   ref=w.RR/('pvr-local-finite-capital-20261029/baseline/accounts-v2' if sec=='TECH' else 'innovative-drug-local-recovery-20261028/S0/accounts-v2');save(root/'IDENTITY.json',legacy.identity(root,ref,ids,end,True))
  if stage=='prefix-cut':save(root/'IDENTITY.json',legacy.identity(root,O/sec/'prefix-open/accounts-v2',ids,end,True))
  if stage=='on':
   save(root/'PREFIX_IDENTITY.json',legacy.identity(O/sec/'prefix-cut',root/'accounts-v2',[f'{mode}__S0_base'],'2025-12-31',False))
   AN=w.load('rb1_original_independent_analyzer',w.RR/'tech-finite-compound-20261026/code/analyze_v2.py');AN.CORE=core;AN.PREP=prep;AN.HERE=root;AN.main('full')
  assert all(w.sha(p)==h for p,h in freeze['sha256'].items());status='complete'
 except BaseException as e:
  status='failed';save(root/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-t;prior=w.read(timing) if timing.exists() else dict(seconds=0,stages=[]);prior['seconds']+=elapsed;prior['stages'].append(dict(sector=sec,stage=stage,status=status,seconds=elapsed));save(timing,prior);save(root/'TIMING.json',dict(status=status,seconds=elapsed,total_seconds=prior['seconds']));print(dict(sector=sec,stage=stage,status=status,seconds=elapsed,total=prior['seconds']),flush=True)
if __name__=='__main__':main()
