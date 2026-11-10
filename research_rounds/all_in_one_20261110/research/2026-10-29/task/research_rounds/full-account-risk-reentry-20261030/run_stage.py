"""Original executor stages with elapsed-time budget; no new trading engine."""
import wire as w
import sys,time,signal,shutil,traceback
from datetime import datetime,timezone
O=w.O
def save(p,x):p.write_text(w.json.dumps(x,ensure_ascii=False,indent=2,default=str))
def event_time(r):return r.get('at',r.get('completed_at',r.get('receipt',{}).get('at',r.get('receivable',{}).get('ex_at',''))))
def identity(root,ref,mode,stresses,end,full):
 receipts=[]
 for stress in stresses:
  aid=f'{mode}__S0_{stress}';a=w.read(root/'accounts-v2'/f'{aid}.json');b=w.read(ref/f'{aid}.json')
  for k in ['fills','audit_log','completed_exits']:
   expected=b[k] if full else [r for r in b[k] if event_time(r)[:10]<=end]
   assert a[k]==expected,(aid,k,'identity mismatch')
  if full:assert a==b,(aid,'final account objects')
  receipts.append(dict(account=aid,fills=len(a['fills']),audit_rows=len(a['audit_log']),exact=True))
 for stream in ['daily','decisions']:
  a=w.rows(root/'accounts-v2'/f'{stream}.jsonl.gz');b=[r for r in w.rows(ref/f'{stream}.jsonl.gz') if r['account'] in {f'{mode}__S0_{s}' for s in stresses} and r['at'][:10]<=end];assert a==b,(stream,'identity mismatch')
 return dict(passed=True,receipts=receipts,daily_decisions_exact=True)
def main():
 sector,stage=sys.argv[1:3];budgetfile=O/'COMPUTE_TIME.json';used=w.read(budgetfile).get('seconds',0) if budgetfile.exists() else 0;left=300-used;assert left>0,('budget exhausted',used)
 timer=time.monotonic();status='started';root=O/sector/stage;root.mkdir(parents=True,exist_ok=False);shutil.copyfile(w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json')
 def timeout(*_):raise TimeoutError('Cumulative 300s computation budget exhausted')
 signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,left)
 try:
  enabled=stage in ['on','prefix'];cutoff='2025-12-31' if stage=='prefix' else None;end='2024-03-13' if stage=='short' else cutoff or '2026-10-27';stresses=['base'] if stage in ['short','prefix'] else ['base','cost2','delay1'];R,E,feed,core,prep,mode=w.setup(sector,root,enabled,cutoff)
  if stage=='on':assert w.read(O/'TECH/off/IDENTITY.json')['passed'] and w.read(O/'DRUG/off/IDENTITY.json')['passed'];assert w.read(O/'SYNTHETIC.json')['passed']
  runner=R.run(root/'accounts-v2',modes=[mode],stresses=stresses,start='2023-12-29',end=end,cutoff=cutoff,technical=stage!='on')
  ref=w.RR/('pvr-local-finite-capital-20261029/baseline/accounts-v2' if sector=='TECH' else 'innovative-drug-local-recovery-20261028/S0/accounts-v2')
  if stage in ['short','off']:save(root/'IDENTITY.json',identity(root,ref,mode,stresses,end,stage=='off'))
  if stage=='prefix':save(root/'IDENTITY.json',identity(root,O/sector/'on/accounts-v2',mode,stresses,end,False))
  if feed:save(root/'FEED_CHECKS.json',dict(sigma_checks=feed.sigma_checks,unknown_states=[dict(account=aid,symbol=s,issues=c.issues) for aid,a in runner.accounts.items() for s,c in a.rb_states.items() if c.issues],frames=len(feed.frames)))
  if stage=='on':
   A=w.load('full_rb_analysis',w.RR/'tech-finite-compound-20261026/code/analyze_v2.py');A.CORE=core;A.PREP=prep;A.HERE=root;A.main('full')
  status='complete'
 except BaseException as e:status='failed';save(root/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-timer;record=w.read(budgetfile) if budgetfile.exists() else dict(seconds=0,stages=[]);record['seconds']+=elapsed;record['stages'].append(dict(sector=sector,stage=stage,seconds=elapsed,status=status));save(budgetfile,record);save(root/'TIMING.json',dict(status=status,seconds=elapsed,cumulative_seconds=record['seconds']));print(dict(sector=sector,stage=stage,status=status,seconds=elapsed,cumulative=record['seconds']),flush=True)
if __name__=='__main__':main()
