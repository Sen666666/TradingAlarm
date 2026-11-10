"""Bounded annual public daily-state windows, avoiding provider full-history pagination."""
import argparse,json,signal,socket,time
from datetime import datetime
from pathlib import Path
import pandas as pd
import baostock as bs
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'data/stock-state-windows'
FIELDS='date,code,open,high,low,close,preclose,volume,amount,adjustflag,tradestatus,pctChg,isST'
def validate(rows,symbol,year):
    if not rows:raise ValueError('empty annual window')
    dates=[r['date'] for r in rows]
    if dates!=sorted(set(dates)):raise ValueError('duplicate or unordered dates')
    if any(not d.startswith(str(year)+'-') for d in dates):raise ValueError('outside requested year')
    code=symbol[-2:].lower()+'.'+symbol[:6]
    for r in rows:
        if r['code']!=code or r['adjustflag']!='3':raise ValueError('wrong instrument or adjustment')
        if r['tradestatus'] not in ('0','1') or r['isST'] not in ('0','1'):raise ValueError('unknown trading/ST state')
    if len(rows)>366:raise ValueError('not daily window')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--limit',type=int,default=3);parser.add_argument('--years',nargs='+',type=int,default=[2015,2024]);parser.add_argument('--budget-seconds',type=int,default=240);parser.add_argument('--priority-windows',type=int,default=0);parser.add_argument('--priority-file',type=Path,default=ROOT/'results/stock-data-audit/state-window-priority.csv');args=parser.parse_args()
    candidates=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet',columns=['symbol'])
    symbols=sorted(candidates.symbol.unique())[:args.limit]
    windows=[(symbol,year) for symbol in symbols for year in args.years]
    if args.priority_windows:
        priority=pd.read_csv(args.priority_file)
        priority=priority[~priority.window_already_cached]
        windows=[(r.symbol,int(r.year)) for r in priority.head(args.priority_windows).itertuples()]
        symbols=sorted({s for s,y in windows})
    OUT.mkdir(exist_ok=True);summary=[];started=time.monotonic();socket.setdefaulttimeout(20)
    signal.signal(signal.SIGALRM,lambda *_: (_ for _ in ()).throw(TimeoutError('batch budget')));signal.alarm(args.budget_seconds)
    try:
        login=bs.login()
        if login.error_code!='0':raise RuntimeError('public login failed')
        for symbol,year in windows:
            p=OUT/f'{symbol}-{year}.json'
            if p.exists():
                data=json.loads(p.read_text());validate(data['rows'],symbol,year);summary.append(dict(symbol=symbol,year=year,status='cached',rows=len(data['rows'])));continue
            rs=bs.query_history_k_data_plus(symbol[-2:].lower()+'.'+symbol[:6],FIELDS,start_date=f'{year}-01-01',end_date=f'{year}-12-31',frequency='d',adjustflag='3')
            if rs.error_code!='0':raise RuntimeError('query failed:'+rs.error_code)
            rows=[]
            while rs.next():rows.append(dict(zip(rs.fields,rs.get_row_data())))
            if rs.error_code!='0':raise RuntimeError('page failed:'+rs.error_code)
            validate(rows,symbol,year)
            data=dict(symbol=symbol,year=year,rows=rows,source='BaoStock annual raw daily state,adjustflag3',fetched_at=datetime.now().astimezone().isoformat(),limitation='Calendar completeness and exact limit prices not yet certified; preclose may be exchange ex-reference rather than prior raw close')
            temp=p.with_suffix('.tmp');temp.write_text(json.dumps(data,ensure_ascii=False,indent=2));temp.replace(p)
            item=dict(symbol=symbol,year=year,status='downloaded',rows=len(rows),suspended=sum(r['tradestatus']=='0' for r in rows),st=sum(r['isST']=='1' for r in rows));summary.append(item);print(item,flush=True)
    except Exception as exc:summary.append(dict(status='error',error_type=type(exc).__name__))
    finally:
        signal.alarm(0)
        try:bs.logout()
        except Exception:pass
        (ROOT/'results/stock-data-audit/stock-state-window-collection.json').write_text(json.dumps(dict(symbols=symbols,requested_windows=windows,years=args.years,elapsed=time.monotonic()-started,records=summary),indent=2))
if __name__=='__main__':main()
