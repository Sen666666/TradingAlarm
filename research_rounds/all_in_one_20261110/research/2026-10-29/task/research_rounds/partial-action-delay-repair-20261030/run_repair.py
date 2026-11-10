import time
START=time.monotonic()
import delay_patch as P
from pathlib import Path
import json,sys,signal,traceback,shutil
P.install();I=P.I;O=Path(__file__).resolve().parent
import run_stage as OLD
save=OLD.save

def main():
 sector,stage=sys.argv[1:3];budget=O/'COMPUTE_TIME.json';b=I.W.read(budget) if budget.exists() else dict(seconds=5.0,initial_synthetic_allowance_seconds=5,stages=[]);remaining=180-b['seconds']-(time.monotonic()-START)
 if remaining<=0:raise TimeoutError('Repair 180 seconds consumed')
 signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('Repair total 180 seconds exhausted')));signal.setitimer(signal.ITIMER_REAL,remaining)
 root=O/sector/stage;root.mkdir(parents=True,exist_ok=False);shutil.copyfile(I.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json');status='started'
 try:
  assert I.W.read(O/'TEST_RESULTS.json')['passed'];assert (O/'REPAIR_FREEZE.json').exists()
  if stage=='full':assert I.W.read(O/'TECH/short2/GATE.json')['passed']
  end='2024-10-18' if stage=='short' else '2024-10-30' if stage=='short2' else '2025-12-31' if stage=='prefix' else '2026-10-27';cutoff=end if stage!='full' else None
  R,E,feed,core,prep,mode=I.setup(sector,root,['B'],cutoff)
  runner=R.run(root/'accounts-v2',modes=[mode],stresses=['delay1'],start='2023-12-29',end=end,cutoff=cutoff,technical=stage!='full');aid=next(iter(runner.accounts));a=runner.accounts[aid];a.check_roles();orders={r['order_id'] for r in a.audit_log if r['kind']=='reserve' and r['purpose']=='risk_restore'};fills=[r for r in a.audit_log if r['kind']=='fill' and r['order_id'] in orders]
  if stage in ['short','short2']:assert fills,'Fixed short window has no real delayed restore; stop economic paths'
  if stage=='prefix':save(root/'IDENTITY.json',OLD.identity(root,O/sector/'full/accounts-v2',[aid],end,False))
  analyzer=I.W.load('repair_account_analyzer',I.RR/'tech-finite-compound-20261026/code/analyze_v2.py');analyzer.CORE=core;analyzer.PREP=prep;analyzer.HERE=root;analyzer.main('full');assert I.W.read(root/'analysis/accounting.json')['passed'] and I.W.read(root/'analysis/funding.json')['passed']
  save(root/'GATE.json',dict(passed=True,account=aid,restore_orders=len(orders),restore_fills=len(fills),restore_shares=sum(r['receipt'].shares for r in fills),credit_created=sum(r['kind']=='role_delay_credit_created' for r in a.audit_log),credit_consumed=sum(r['kind']=='role_delay_credit_consumed' for r in a.audit_log),fills=[r for r in a.audit_log if r['kind']=='fill' and r['order_id'] in orders][:3],sigma_prefix_checks=feed.sigma_checks,accounting=True))
  save(root/'role-final.json',dict(group_cash=a.group_cash,group_dividend=a.group_dividend,roles={s:{k:v for k,v in r.items() if k!='controller'} for s,r in a.roles.items()}));status='complete'
 except BaseException as ex:status='failed';save(root/'ERROR.json',dict(error=repr(ex),traceback=traceback.format_exc()));raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-START;b['seconds']+=elapsed;b['stages'].append(dict(sector=sector,stage=stage,status=status,seconds=elapsed));save(budget,b);save(root/'TIMING.json',dict(status=status,seconds=elapsed,total_seconds=b['seconds']));print(dict(sector=sector,stage=stage,status=status,seconds=elapsed,total_seconds=b['seconds']),flush=True)
if __name__=='__main__':main()
