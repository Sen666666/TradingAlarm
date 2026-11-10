import wire as w
import sys,time,signal,shutil,traceback,json
from pathlib import Path
O=w.O
def save(p,x):Path(p).write_text(json.dumps(w.K.H.encoded(x),ensure_ascii=False,indent=2,default=str))
def ts(r):return r.get('at') or r.get('completed_at') or r.get('receipt',{}).get('at') or r.get('receivable',{}).get('ex_at') or ''
def identity(root,ref,ids,end,full):
 receipts=[]
 for aid in ids:
  a=w.read(root/'accounts-v2'/f'{aid}.json');b=w.read(ref/f'{aid}.json')
  for k in ['fills','audit_log','completed_exits']:assert a[k]==(b[k] if full else [r for r in b[k] if ts(r)[:10]<=end]),(aid,k,'identity failed')
  if full:assert a==b,(aid,'full account object')
  receipts.append(dict(account=aid,fills=len(a['fills']),audit_rows=len(a['audit_log']),exact=True))
 for stream in ['daily','decisions']:
  with w.gzip.open(root/'accounts-v2'/f'{stream}.jsonl.gz','rt') as f:a=[json.loads(x) for x in f]
  with w.gzip.open(ref/f'{stream}.jsonl.gz','rt') as f:b=[r for x in f if (r:=json.loads(x))['account'] in ids and r['at'][:10]<=end]
  assert a==b,(stream,'identity failed')
 return dict(passed=True,receipts=receipts,daily_and_decisions_exact=True)
def main():
 sector,stage=sys.argv[1:3];assert sector in ['TECH','DRUG'] and stage in ['off','on','prefix'];p=O/'COMPUTE_TIME.json';old=w.read(p) if p.exists() else dict(seconds=0,stages=[]);sectorused=sum(r['seconds'] for r in old['stages'] if r['sector']==sector);left=min(480-old['seconds'],240-sectorused);assert left>0
 timer=time.monotonic();root=O/sector/stage;root.mkdir(parents=True,exist_ok=False);shutil.copyfile(w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json');status='started';signal.signal(signal.SIGALRM,lambda *_:(_ for _ in ()).throw(TimeoutError('sector240/total480 compute budget')));signal.setitimer(signal.ITIMER_REAL,left)
 try:
  assert w.read(O/'SYNTHETIC.json')['passed'];freeze=w.read(O/'FREEZE.json');assert all(w.sha(q)==h for q,h in freeze['sha256'].items());enabled=stage!='off';cutoff='2025-06-30' if stage=='prefix' else None;end=cutoff or '2026-10-27';stresses=['base','delay1']
  if stage=='on':assert w.read(O/sector/'off/IDENTITY.json')['passed']
  R,E,core,prep,mode=w.setup(sector,root,enabled,cutoff);print(dict(sector=sector,stage=stage,setup_seconds=time.monotonic()-timer,remaining_budget=left),flush=True);runner=R.run(root/'accounts-v2',modes=[mode],stresses=stresses,start='2023-12-29',end=end,cutoff=cutoff,technical=stage!='on');ids=list(runner.accounts)
  if stage=='off':
   ref=w.RR/('pvr-local-finite-capital-20261029/baseline/accounts-v2' if sector=='TECH' else 'innovative-drug-local-recovery-20261028/S0/accounts-v2');save(root/'IDENTITY.json',identity(root,ref,ids,end,True))
  if stage=='prefix':save(root/'IDENTITY.json',identity(root,O/sector/'on/accounts-v2',ids,end,False))
  if stage=='on':
   checks=[]
   for aid,a in runner.accounts.items():
    marks=a.market.marks(a.risk_last_at if hasattr(a,'risk_last_at') else runner.end,a.positions) if False else a.market.marks(runner.end,a.positions)
    endbal=a.balance(runner.end,marks);closed=sum((g['net'] for g in a.loss_groups.values()),w.Z);open_net=sum((w.D(a.quantity(s))*marks[s].cny_price(runner.end)+c['div']+c['sales']-c['K'] for s,c in a.loss_states.items()),w.Z);assert closed+open_net==endbal['nav']-w.D(1000000),(aid,closed,open_net,endbal['nav']);checks.append(dict(account=aid,structure_closed=closed,structure_open=open_net,nav_profit=endbal['nav']-w.D(1000000),residual=w.Z));save(root/f'{aid}-structure-final.json',dict(groups=a.loss_groups,open=[dict(symbol=s,**{k:v for k,v in c.items() if k!='controller'}) for s,c in a.loss_states.items()]))
   save(root/'STRUCTURE_GATE.json',dict(passed=True,checks=checks));AN=w.load('budget_full_original_analyzer',w.RR/'tech-finite-compound-20261026/code/analyze_v2.py');AN.CORE=core;AN.PREP=prep;AN.HERE=root;AN.main('full')
  assert all(w.sha(q)==h for q,h in freeze['sha256'].items());status='complete'
 except BaseException as e:status='failed';save(root/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc()));raise
 finally:
  signal.setitimer(signal.ITIMER_REAL,0);elapsed=time.monotonic()-timer;record=w.read(p) if p.exists() else dict(seconds=0,stages=[]);record['seconds']+=elapsed;record['stages'].append(dict(sector=sector,stage=stage,status=status,seconds=elapsed));save(p,record);save(root/'TIMING.json',dict(status=status,seconds=elapsed,sector_seconds=sectorused+elapsed,total_seconds=record['seconds']));print(dict(sector=sector,stage=stage,status=status,seconds=elapsed,sector_seconds=sectorused+elapsed,total=record['seconds']),flush=True)
if __name__=='__main__':main()
