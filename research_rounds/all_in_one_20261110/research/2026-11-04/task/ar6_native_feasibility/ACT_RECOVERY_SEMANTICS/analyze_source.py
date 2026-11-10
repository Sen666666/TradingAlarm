"""Frozen ACT-source clause timelines only; no account/model execution."""
from pathlib import Path
from decimal import Decimal as D
import ast,gzip,hashlib,json,time
import pandas as pd

O=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
M=Path('/Users/bytedance/Documents/ChatGPT/money')
RUN=O.parent/'NEW_CYCLE_READINESS/2024_full/cycle2024'
REC=W/'mainline-absolute-Q4-20261031/recovery.csv'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):
 (O/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
def main():
 t=time.monotonic()
 sources=[Path(__file__),REC,M/'TradingAlarm/desk/refresh.py',
  M/'research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py',
  M/'research_rounds/actual-risk-recovery-20261027/code/risk_policy.py',
  W/'mainline-I-quarter-2025Q3-20261031/adapter.py',W/'mainline-absolute-Q4-20261031/experiment.py',
  W/'case-stage-ledger-20261031/v3/launch_v3.py',W/'case-stage-ledger-20261031/v3/joint_v3.py',
  M/'research_rounds/actual-risk-recovery-20261027/PROTOCOL.md',
  M/'research_rounds/actual-risk-recovery-20261027/CONCLUSION.md',
  M/'research_rounds/recovery-only-20261027/PROTOCOL.md',M/'research_rounds/recovery-only-20261027/code/prepare.py',
  M/'research_rounds/recovery-only-20261027/CONCLUSION.md',
  W/'market-proof-lifecycle-readonly-20261101/CORE_READOUT.txt',W/'market-proof-lifecycle-readonly-20261101/CONTRACT.txt']
 frozen={str(p):sha(p)for p in sources};save('SOURCE_FREEZE.json',dict(account_events=0,source_hashes=frozen))
 src=M/'TradingAlarm/desk/refresh.py';node=next(n for n in ast.parse(src.read_text()).body if isinstance(n,ast.FunctionDef)and n.name=='compute_recovery')
 (O/'ORIGINAL_COMPUTE_RECOVERY.py').write_text(ast.get_source_segment(src.read_text(),node)+'\n')
 r=pd.read_csv(REC,index_col=0,parse_dates=True);r['up']=r.market.diff().gt(0)
 r['inclusive_SMA63']=r.market.rolling(63,min_periods=63).mean()
 r['prior63_mean']=r.market.shift().rolling(63,min_periods=63).mean()
 r['A_inclusive63_input']=r.market.gt(r.inclusive_SMA63)&r.up&r.breadth.gt(.6)
 r['A_prior63mean_input']=r.market.gt(r.prior63_mean)&r.up&r.breadth.gt(.6)
 assert r.breakout.equals(r.market.gt(r.prior_high63)&r.up&r.breadth.gt(.6))
 assert r.fast_on.equals(r.breadth.gt(.6))
 output=[]
 for policy in ['original','no60']:
  p=RUN/policy/'run-2024/pair/B.json.gz'
  with gzip.open(p,'rt')as f:b=json.load(f)
  audit=[x for x in b['audit']if x['kind']=='risk_checkpoint'];by={x['at'][:10]:x for x in audit}
  events=[]
  for x in audit:
   if not x.get('event'):continue
   day=x['at'][:10];after=[a for a in audit if a['at']>x['at']]
   firstflat=next((a['at']for a in after if a['flat']),None)if x['event']=='pause'else None
   buys=[a for a in b['trades']if a['side']=='buy'and a['at']>x['at']]
   firstbuy=buys[0]['at']if buys and x['event']=='resume'else None
   events.append({k:x[k]for k in ['at','nav','event','flat','fast','breakout','episode','peak']}|dict(first_subsequent_flat_checkpoint=firstflat,first_subsequent_actual_buy=firstbuy))
  periods=[]
  for label,start,end in [('L02_context','2022-04-27','2022-07-04'),('2024_Feb_Apr_delay','2024-02-01','2024-05-06')]:
   rr=[]
   for at,z in r.loc[start:end].iterrows():
    day=str(at.date());x=by[day];assert x['fast']==bool(z.fast_on)and x['breakout']==bool(z.breakout)
    rr.append(dict(day=day,market=float(z.market),prior_high63=float(z.prior_high63),inclusive_SMA63=float(z.inclusive_SMA63),prior63_mean=float(z.prior63_mean),breadth=float(z.breadth),up=bool(z.up),fast=bool(z.fast_on),
      old_breakout=bool(z.breakout),A_inclusive63_input=bool(z.A_inclusive63_input),A_prior63mean_input=bool(z.A_prior63mean_input),
      actual_flat=x['flat'],actual_on=x['on'],actual_event=x.get('event'),actual_NAV=x['nav']))
   first=lambda key:next((x['day']for x in rr if x[key]),None)
   eligible=lambda key:next((x['day']for x in rr if x[key]and x['actual_flat']and not x['actual_on']),None)
   periods.append(dict(label=label,start=start,end=end,first_fast_input=first('fast'),first_old_breakout_input=first('old_breakout'),
    first_A_inclusive63_input=first('A_inclusive63_input'),first_A_prior63mean_input=first('A_prior63mean_input'),
    first_A_inclusive_under_observed_old_paused_flat=eligible('A_inclusive63_input'),first_A_prior63mean_under_observed_old_paused_flat=eligible('A_prior63mean_input'),
    old_paused_flat_positive_fast_old_high_failed_days=sum(not x['actual_on']and x['actual_flat']and x['fast']and x['up']and not x['old_breakout']for x in rr),rows=rr,
    interpretation='A columns are source-clause alternatives on unchanged observed old state; no new account recovery, fill or profit is simulated.'))
  output.append(dict(policy=policy,actual_events=events,periods=periods,source_book=str(p),source_book_sha256=sha(p)))
 save('ACT_CLOCK_AND_CLAUSES.json',dict(account_events=0,original_recovery_source=frozen[str(REC)],records=output,seconds=time.monotonic()-t))
 assert all(sha(p)==h for p,h in frozen.items())
 print(json.dumps([dict(policy=x['policy'],events=x['actual_events'],periods=[{k:v for k,v in p.items()if k not in ['rows','interpretation']}for p in x['periods']])for x in output],ensure_ascii=False))
if __name__=='__main__':main()
