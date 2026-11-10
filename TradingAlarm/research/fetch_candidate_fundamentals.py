"""Bounded anonymous growth-data collection prioritized by candidate coverage, never returns."""
import argparse,json,signal,socket,time
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
import pandas as pd
import baostock as bs
from probe_fundamental_vintage import timeout
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'data/candidate-fundamentals';REPORT=ROOT/'results/candidate-fundamentals'
def plan(candidates):
 counts=Counter()
 for row in candidates[['symbol','date']].drop_duplicates().itertuples(index=False):
  quarter=pd.Timestamp(row.date).to_period('Q')
  for offset in [1,2,3,4]:
   q=quarter-offset;counts[(row.symbol,int(q.year),int(q.quarter))]+=1
 return pd.DataFrame([dict(symbol=s,year=y,quarter=q,candidate_uses=n) for (s,y,q),n in counts.items()]).sort_values(['candidate_uses','symbol','year','quarter'],ascending=[False,True,True,True]).reset_index(drop=True)
def main():
 parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=200);parser.add_argument('--plan',type=Path);parser.add_argument('--budget-seconds',type=int,default=150);args=parser.parse_args();assert 0<args.limit<=10000 and 0<args.budget_seconds<=1800
 OUT.mkdir(exist_ok=True);REPORT.mkdir(exist_ok=True)
 raw=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet',columns=['symbol','date','active20']);raw=raw[raw.active20.eq(20)];tasks=plan(raw) if args.plan is None else pd.read_csv(args.plan);
 if not {'symbol','year','quarter'}.issubset(tasks.columns) or tasks.duplicated(['symbol','year','quarter']).any():raise ValueError('invalid collection plan')
 if args.plan is None:tasks.to_csv(REPORT/'collection-plan.csv',index=False)
 (REPORT/('protocol.json' if args.plan is None else 'custom-plan-last-run.json')).write_text(json.dumps(dict(selection=('All active20==20 historical breakout candidates; preceding4completedquarters perdate; prioritybycandidateusecount then symbol/year/quarter; no forwardreturns read' if args.plan is None else 'Explicit supplied frozen plan: '+str(args.plan)+'; row order preserved; no forwardreturns read'),query='query_growth_data',vintage_status='Unverified vendor snapshots; dates alone do not certify firstpublished values',financial_status='Fourquarterlookback is boundedavailabilityprobe,notcertifiedlatestfiling completeness',total_requests=len(tasks)),indent=2))
 signal.signal(signal.SIGALRM,timeout);socket.setdefaulttimeout(20);signal.alarm(25);r=bs.login();signal.alarm(0)
 if r.error_code!='0':raise RuntimeError(r.error_msg)
 fetched=0;errors=0;start=time.monotonic()
 try:
  for t in tasks.itertuples(index=False):
   if fetched>=args.limit or time.monotonic()-start>args.budget_seconds:break
   path=OUT/f'{t.symbol}-{t.year}Q{t.quarter}.json'
   if path.exists():continue
   code=t.symbol[7:].lower()+'.'+t.symbol[:6];record=dict(symbol=t.symbol,code=code,year=t.year,quarter=t.quarter,retrieved_at=datetime.now(timezone.utc).isoformat(),vintage_verified=False)
   try:
    signal.alarm(20);rs=bs.query_growth_data(code,t.year,t.quarter);record.update(error_code=rs.error_code,error_msg=rs.error_msg,fields=rs.fields);rows=[]
    while rs.error_code=='0' and rs.next():rows.append(dict(zip(rs.fields,rs.get_row_data())))
    record['rows']=rows
   except Exception as e:record['exception']=type(e).__name__+':'+str(e)
   finally:signal.alarm(0)
   temp=path.with_suffix('.tmp');temp.write_text(json.dumps(record,ensure_ascii=False,indent=2));temp.replace(path);fetched+=1;errors+=bool(record.get('exception') or record.get('error_code')!='0')
   if fetched%25==0:print('fetched',fetched,'errors',errors,flush=True)
   if errors>=3:break
 finally:
  signal.alarm(10)
  try:bs.logout()
  finally:signal.alarm(0)
 (REPORT/'last-job.json').write_text(json.dumps(dict(status='completed',fetched=fetched,errors=errors,elapsed_seconds=time.monotonic()-start),indent=2));print('completed',fetched,errors)
if __name__=='__main__':main()
