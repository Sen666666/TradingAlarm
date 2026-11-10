import adapter as m
from pathlib import Path
import sys,time,signal,shutil,json,traceback,types
w=m.w;O=m.O
legacy=w.load('rb1_history_identity',O.parent/'entry-loss-budget-cost2-funnel-20261031/run_cost2.py')
def save(p,x):w.K.save(p,x)
def main():
 sec,stage=sys.argv[1:3];assert sec in ['TECH','DRUG'] and stage in ['control-native','control-off','prefix','full'];tp=O/'COMPUTE_TIME.json';prior=w.read(tp) if tp.exists() else dict(seconds=0,stages=[]);used=sum(x['seconds'] for x in prior['stages'] if x['sector']==sec);left=min(600-prior['seconds'],300-used);assert left>0
 t=time.monotonic();root=O/sec/stage;root.mkdir(parents=True,exist_ok=False);shutil.copyfile(w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json');status='started';signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('RB1 history sector300 total600 compute budget')));signal.setitimer(signal.ITIMER_REAL,left)
 try:
  assert w.read(O/'DATA_GATE.json')['passed'];freeze=w.read(O/'FREEZE.json');assert all(w.sha(p)==h for p,h in freeze['sha256'].items())
  if stage in ['prefix','full']:assert w.read(O/sec/'control-off/IDENTITY.json')['passed']
  if stage=='full':assert w.read(O/sec/'prefix/TIMING.json')['status']=='complete'
  short=stage.startswith('control');cut='2021-12-31' if stage=='prefix' else None;end='2019-03-29' if short else cut or '2023-12-29';roles=['A'] if short else ['R'] if stage=='prefix' else ['A','R'];stresses=['base'] if stage=='prefix' else ['base','cost2','delay1']
  R,E,core,prep,mode=m.setup(sec,root,roles,stage!='control-native',cut);print(dict(sector=sec,stage=stage,setup_seconds=time.monotonic()-t,budget=left),flush=True)
  runner=R.run(root/'accounts-v2',modes=[mode],stresses=stresses,start='2018-12-28',end=end,cutoff=cut,technical=stage!='full');ids=list(runner.accounts);save(root/'QUALIFICATION_DAYS.json',runner.facts.qualification_rows)
  if stage=='control-off':save(root/'IDENTITY.json',legacy.identity(root,O/sec/'control-native/accounts-v2',ids,end,True))
  if stage=='full':
   save(root/'PREFIX_IDENTITY.json',legacy.identity(O/sec/'prefix',root/'accounts-v2',[f'{mode}__R_S0_base'],'2021-12-31',False))
   # Statistical dates only; preserve independent accounting/fees/quantity implementation.
   path=w.RR/'tech-finite-compound-20261026/code/analyze_v2.py';source=path.read_text();assert source.count("frame.date.ge('2024-01-01')")==1 and source.count("pd.Timestamp('2024-01-02')")==1
   source=source.replace("frame.date.ge('2024-01-01')","frame.date.ge('2019-01-01')").replace("pd.Timestamp('2024-01-02')","pd.Timestamp('2019-01-02')")
   AN=types.ModuleType('history_original_independent_analysis');AN.__file__=str(path);sys.modules[AN.__name__]=AN;exec(compile(source,str(path),'exec'),AN.__dict__);AN.CORE=core;AN.PREP=prep;AN.HERE=root;AN.main('full')
   save(root/'REPORTING_DATE_PATCH.json',dict(source=str(path),changes=['statistics date>=2019-01-01','CAGR origin2019-01-02'],accounting_function_unchanged=True,transaction_rule_changes=0))
  assert all(w.sha(p)==h for p,h in freeze['sha256'].items());status='complete'
 except BaseException as e:status='failed';save(root/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-t;old=w.read(tp) if tp.exists() else dict(seconds=0,stages=[]);old['seconds']+=elapsed;old['stages'].append(dict(sector=sec,stage=stage,status=status,seconds=elapsed));save(tp,old);save(root/'TIMING.json',dict(status=status,seconds=elapsed,sector_seconds=used+elapsed,total_seconds=old['seconds']));print(dict(sector=sec,stage=stage,status=status,seconds=elapsed,sector_seconds=used+elapsed,total=old['seconds']),flush=True)
if __name__=='__main__':main()
