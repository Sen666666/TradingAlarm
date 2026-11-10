"""Checkpointed read-only THS history repair using search-confirmed identifiers."""
import argparse,json,signal,sys,time
from pathlib import Path
import pandas as pd
from fetch_history import fetch,APP
sys.path.insert(0,str(APP))
from search import SearchClient
from sessions import SessionManager,DEFAULT_PREFERENCES
ROOT=Path(__file__).resolve().parent

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=20);parser.add_argument('--budget-seconds',type=int,default=1200);args=parser.parse_args()
 target=ROOT/'results/stock-data-audit/ths-retired-collection.json'
 records=json.loads(target.read_text()).get('records',{}) if target.exists() else {}
 master=pd.read_csv(ROOT/'results/stock-data-audit/missing-retired-symbols.csv',dtype=str)
 selected=master[pd.to_datetime(master.outDate)>=pd.Timestamp('2015-01-01')].sort_values('symbol').head(args.limit)
 manager=SessionManager(APP.parent/'artifacts/ths-analysis-20261016/deep/handshake/stream-9-client.bin',preferences_path=DEFAULT_PREFERENCES)
 client=SearchClient(manager)
 signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('batch time budget exhausted')));signal.alarm(args.budget_seconds)
 started=time.monotonic()
 def save():
  temp=target.with_suffix('.tmp');temp.write_text(json.dumps(dict(records=records,source='Existing authorized THS quote and search endpoints',requested=len(selected),elapsed_seconds=round(time.monotonic()-started,1)),ensure_ascii=False,indent=2));temp.replace(target)
 try:
  for row in selected.to_dict('records'):
   symbol=row['symbol'];previous=records.get(symbol,{})
   if previous.get('status')=='downloaded':
    file=ROOT/'data/ths-raw'/(previous['ths_symbol']+'.json')
    if file.exists():
     saved=json.loads(file.read_text())
     if saved.get('bars') and not saved.get('page_budget_exhausted',True) and not saved.get('overlap_conflicts'):continue
   try:
    code=symbol.split('.')[0]
    matches=[x for x in client.search(code) if x.get('code')==code and x.get('market') in ('USZD','USHD')]
    if len(matches)!=1:
     records[symbol]={'status':'unresolved_identifier','matches':[{k:x.get(k) for k in ['symbol','market','name']} for x in matches]};save();continue
    ths=matches[0]['symbol'];result=fetch(ths,'20261016','2010-01-01',8,'raw');bars=result['bars']
    records[symbol]=dict(status='downloaded' if bars and not result['page_budget_exhausted'] and not result['overlap_conflicts'] else 'requires_review',ths_symbol=ths,rows=len(bars),first=bars[0]['date'] if bars else None,last=bars[-1]['date'] if bars else None,master_out_date=row['outDate'],corporate_actions_verified=False)
    print(symbol,records[symbol]['status'],len(bars),flush=True);save();time.sleep(.3)
   except TimeoutError:
    records[symbol]={'status':'timeout'};save()
    if time.monotonic()-started>=args.budget_seconds-1:break
   except Exception as exc:
    records[symbol]={'status':'error','error_type':type(exc).__name__};save();print(symbol,type(exc).__name__,flush=True)
 finally:
  signal.alarm(0);save()

if __name__=='__main__':main()
