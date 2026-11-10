import integrated as I
import sys,time,signal,shutil,traceback,json
from pathlib import Path
O=I.O
def save(p,x):Path(p).write_text(json.dumps(I.M.E.native.encoded(x),ensure_ascii=False,indent=2,default=str))
def stamp(r):return r.get('at') or r.get('completed_at') or r.get('receipt',{}).get('at') or r.get('receivable',{}).get('ex_at') or ''
def identity(root,ref,ids,end,full):
 receipts=[]
 for aid in ids:
  a=I.W.read(root/'accounts-v2'/f'{aid}.json');b=I.W.read(ref/f'{aid}.json')
  for k in ['fills','audit_log','completed_exits']:assert a[k]==(b[k] if full else [r for r in b[k] if stamp(r)[:10]<=end]),(aid,k,'identity mismatch')
  if full:assert a==b,(aid,'complete account object')
  receipts.append(dict(account=aid,fills=len(a['fills']),audit=len(a['audit_log']),exact=True))
 for stream in ['daily','decisions']:
  a=I.W.rows(root/'accounts-v2'/f'{stream}.jsonl.gz');b=[r for r in I.W.rows(ref/f'{stream}.jsonl.gz') if r['account'] in ids and r['at'][:10]<=end];assert a==b,(stream,'identity mismatch')
 return dict(passed=True,receipts=receipts,daily_and_decisions_exact=True)
def main():
 sector,stage=sys.argv[1:3];p=O/'COMPUTE_TIME.json';old=I.W.read(p) if p.exists() else dict(seconds=0,stages=[]);remaining=480-old['seconds'];assert remaining>0;start=time.monotonic();root=O/sector/stage;root.mkdir(parents=True,exist_ok=False);shutil.copyfile(I.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json');status='started'
 def timeout(*_):raise TimeoutError('480-second total compute budget exhausted')
 signal.signal(signal.SIGALRM,timeout);signal.setitimer(signal.ITIMER_REAL,remaining)
 try:
  policies=['A'] if stage=='off' else ['B','L'];end='2024-03-29' if stage=='short' else '2025-12-31' if stage=='prefix' else '2026-10-27';cutoff=end if stage in ['short','prefix'] else None;stresses=['base'] if stage in ['short','prefix'] else ['base','cost2','delay1']
  if stage=='on':assert I.W.read(O/'GATES.json')['passed'];assert (O/'ECONOMIC_FREEZE.json').exists()
  R,E,feed,core,prep,mode=I.setup(sector,root,policies,cutoff);runner=R.run(root/'accounts-v2',modes=[mode],stresses=stresses,start='2023-12-29',end=end,cutoff=cutoff,technical=stage!='on');ids=list(runner.accounts)
  if stage=='off':
   ref=I.RR/('pvr-local-finite-capital-20261029/baseline/accounts-v2' if sector=='TECH' else 'innovative-drug-local-recovery-20261028/S0/accounts-v2');save(root/'IDENTITY.json',identity(root,ref,ids,end,True))
  if stage=='prefix':save(root/'IDENTITY.json',identity(root,O/sector/'on/accounts-v2',ids,end,False))
  receipts=[]
  for aid,a in runner.accounts.items():
   a.check_roles();restore_orders={r['order_id'] for r in a.audit_log if r['kind']=='reserve' and r['purpose']=='risk_restore'};restore_fills=[r for r in a.audit_log if r['kind']=='fill' and r['order_id'] in restore_orders];cashpoints=[r for r in a.audit_log if r['kind']=='fixed_cash_checkpoint'];receipts.append(dict(account=aid,policy=a.policy_tag,risk_trim_requests=sum(r['kind']=='risk_trim_request' for r in a.role_events),restore_orders=len(restore_orders),restore_fills=len(restore_fills),restore_shares=sum(r['receipt'].shares for r in restore_fills),minimum_real_cash=str(min([r['available'] for r in cashpoints] or [a.available])),role_state_exact=True));save(root/f'{aid}-role-final.json',dict(roles={s:{k:v for k,v in r.items() if k!='controller'} for s,r in a.roles.items()},group_cash=a.group_cash,group_dividend=a.group_dividend))
  save(root/'EXECUTION_GATE.json',dict(passed=True,receipts=receipts,sigma_prefix_checks=feed.sigma_checks if feed else [],conditional_unknown=True))
  if stage=='on':
   A=I.W.load('partial_accounts_analyzer',I.RR/'tech-finite-compound-20261026/code/analyze_v2.py');A.CORE=core;A.PREP=prep;A.HERE=root;A.main('full')
  status='complete'
 except BaseException as ex:status='failed';save(root/'ERROR.json',dict(error=repr(ex),traceback=traceback.format_exc()));raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);seconds=time.monotonic()-start;old['seconds']+=seconds;old['stages'].append(dict(sector=sector,stage=stage,status=status,seconds=seconds));save(p,old);save(root/'TIMING.json',dict(status=status,seconds=seconds,total_seconds=old['seconds']));print(dict(sector=sector,stage=stage,status=status,seconds=seconds,total=old['seconds']),flush=True)
if __name__=='__main__':main()
