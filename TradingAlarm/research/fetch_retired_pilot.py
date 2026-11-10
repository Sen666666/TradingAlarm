"""Bounded public-history pilot for alphabetically first3 missing2015+ retirees."""
import json,signal,socket,argparse
from datetime import datetime
from pathlib import Path
import pandas as pd
import baostock as bs
from audit_retired_readiness import inspect_history
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'data/retired-pilot';OUT.mkdir(exist_ok=True)
parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=3);parser.add_argument('--budget-seconds',type=int,default=240);args=parser.parse_args()
socket.setdefaulttimeout(60)
signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('Public-query time budget exhausted;completed files retained')));signal.alarm(args.budget_seconds)
master=pd.read_csv(ROOT/'results/stock-data-audit/missing-retired-symbols.csv',dtype=str)
selected=master[pd.to_datetime(master.outDate)>=pd.Timestamp('2015-01-01')].sort_values('symbol').head(args.limit)
fields='date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST'
try:
 login=bs.login()
 if login.error_code!='0':raise RuntimeError(login.error_msg)
 for r in selected.to_dict('records'):
  file=OUT/(r['symbol']+'.json')
  if file.exists():
   try:
    if inspect_history(json.loads(file.read_text()),r)['structurally_valid']:continue
   except (ValueError,KeyError,TypeError):pass
  rs=bs.query_history_k_data_plus(r['code'],fields,start_date=max(r['ipoDate'],'2010-01-01'),end_date=r['outDate'],frequency='d',adjustflag='3')
  if rs.error_code!='0':raise RuntimeError(rs.error_msg)
  rows=[]
  while rs.next():rows.append(dict(zip(rs.fields,rs.get_row_data())))
  if rs.error_code!='0':raise RuntimeError(rs.error_msg)
  out={'symbol':r['symbol'],'source':'BaoStock public raw daily,adjustflag3','fetched_at':datetime.now().astimezone().isoformat(),'master_record':r,'rows':rows,'limitation':'No claim that outDate is last tradable day,liquidation proceeds or conversion ratio.'}
  if not rows:raise ValueError('Empty history:'+r['symbol'])
  temp=file.with_suffix('.tmp');temp.write_text(json.dumps(out,ensure_ascii=False,indent=2));temp.replace(file)
  print(r['symbol'],len(rows),'ST rows',sum(x['isST']=='1' for x in rows),'suspended',sum(x['tradestatus']=='0' for x in rows),flush=True)
finally:
 bs.logout();signal.alarm(0)
