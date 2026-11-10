"""Zero-account availability check; independent calendar from saved native gold."""
from pathlib import Path
import gzip,json,hashlib,pickle
import pandas as pd
from market_info import MarketInfo as V1
from market_info_v2 import MarketInfo as V2
O=Path(__file__).resolve().parent;T=O.parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n,x):(O/n).write_text(json.dumps(x,indent=2,default=str)+'\n')
def rows(p):
 with gzip.open(p,'rt')as f:return[json.loads(x)for x in f]
CASES={'long':('small-long-v1',['legacy9','fresh_DOWN_technical6'],T/'capacity_cost_guard_v1/runs/long-v1/arms/B/pair/daily.jsonl.gz',T/'benchmark_2022_2023/continuation2024/inputs/510300_history.csv',['2021-12-30','2021-12-31']), 'strong':('small-strong-v1',['strong9'],T/'capacity_cost_guard_v1/runs/strong-v1/arms/B/pair/daily.jsonl.gz',T/'capacity_cost_guard_analysis_v1/benchmark_B_2025_26/inputs/510300_history.csv',['2025-06-27','2025-06-30'])}
def normalize(v):
 if isinstance(v,dict):return{k:(pd.Timestamp(x).isoformat()if k in('at','available_at','expected_completed_CLOSE')and x is not None else normalize(x))for k,x in v.items()}
 if isinstance(v,list):return[normalize(x)for x in v]
 return json.loads(json.dumps(v,default=str))
def main():
 out={};sources={str(Path(__file__).resolve()):sha(__file__),str(O/'market_info_v2.py'):sha(O/'market_info_v2.py'),str(O/'market_info.py'):sha(O/'market_info.py')}
 for win,(run,cases,calendar,history,warm)in CASES.items():
  dates=[r['at']for r in rows(calendar)];expected=[pd.Timestamp(d+'T15:10:00+08:00')for d in warm]+[pd.Timestamp(d)for d in dates]
  v1=V1(history);v2=V2(history,expected);restored=pickle.loads(pickle.dumps(v2));checks=[];actual=0;scheduled=0;prefixes={}
  sources.update({str(calendar):sha(calendar),str(history):sha(history)})
  for case in cases:
   dest=O/run/case;assert(dest/'SMALL_RESULT.json').exists(),('await committed case',case)
   events=rows(dest/'pair/gross-admission-events.jsonl.gz');clocks=read(dest/'MARKET_INFO_CLOCK_CHECKS.json')['rows'];sources[str(dest/'MARKET_INFO_CLOCK_CHECKS.json')]=sha(dest/'MARKET_INFO_CLOCK_CHECKS.json');sources[str(dest/'pair/gross-admission-events.jsonl.gz')]=sha(dest/'pair/gross-admission-events.jsonl.gz')
   for label,rr in [('actual_callback',events),('scheduled_OPEN_CLOSE',clocks)]:
    for r in rr:
     at=r['at'];a=normalize(v1.state(at));b=normalize(v2.state(at));assert a==b==normalize(restored.state(at)),('actualscope provider difference',case,at)
     recorded=normalize(r['info']if label=='actual_callback'else{k:v for k,v in r.items()if k!='at'});assert recorded==a,('saved actual info differs',case,at)
     cut=str(at)[:10]
     if cut not in prefixes:prefixes[cut]=v2.prefix(cut)
     assert b==normalize(prefixes[cut].state(at))
     actual+=label=='actual_callback';scheduled+=label=='scheduled_OPEN_CLOSE'
   checks.append(dict(case=case,actual_callback_rows=len(events),scheduled_OPEN_CLOSE_rows=len(clocks),all_v1_v2_and_pickle_actualscope_exact=True))
  out[win]=dict(cases=checks,actual_callback_rows=actual,scheduled_OPEN_CLOSE_rows=scheduled,expected_calendar_source=str(calendar),warm_dates=warm)
  if win=='long':
   old=v1.prefix('2022-01-07');cut=v2.prefix('2022-01-07')
   t0='2022-01-10T09:30:00+08:00';t1='2022-01-10T15:10:00+08:00';t2='2022-01-11T09:30:00+08:00'
   assert cut.state(t0)['state']!='UNKNOWN'and cut.state(t0)['day']=='2022-01-07'
   assert old.state(t1)['state']!='UNKNOWN'and old.state(t2)['state']!='UNKNOWN'
   assert cut.state(t1)['state']==cut.state(t2)['state']=='UNKNOWN'
   save('PROVIDER_V1_DOMAIN_FAILURE.json',dict(status='EXPECTED_NEGATIVE_BOUNDARY_FAIL_PRESERVED',old_cut='2022-01-07',old_stale_CLOSE=normalize(old.state(t1)),old_stale_next_OPEN=normalize(old.state(t2)),native_accounts_run=0))
   out['negative_domain']=dict(Jan10_OPEN_legally_uses_Jan7=normalize(cut.state(t0)),Jan10_CLOSE_missing_UNKNOWN=normalize(cut.state(t1)),Jan11_OPEN_missing_Jan10_UNKNOWN=normalize(cut.state(t2)),outside_full_domain_UNKNOWN=v2.state('2027-01-05T15:10:00+08:00')['state']=='UNKNOWN')
 assert all(sha(p)==s for p,s in sources.items());save('PROVIDER_V2_CHECKS.json',dict(status='PASS_PRODUCER_ZERO_ACCOUNT_PROVIDER_ONLY',results=out,sources=sources,new_native_accounts=0,no_small_financial_replay=True,native_historical_restart_proof_claimed=False))
 print('PROVIDER_V2_PASS',[(k,v.get('actual_callback_rows'),v.get('scheduled_OPEN_CLOSE_rows'))for k,v in out.items()])
if __name__=='__main__':main()
