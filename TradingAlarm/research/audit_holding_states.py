"""State coverage over complete research holding paths; priority independent of returns."""
import json
from collections import Counter
import pandas as pd
from stock_entry_diagnostic import ROOT
OUT=ROOT/'results/stock-data-audit'
def main():
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values()
 states={};windows=set()
 for p in (ROOT/'data/stock-state-windows').glob('*.json'):
  d=json.loads(p.read_text());windows.add((d['symbol'],d['year']))
  for r in d['rows']:states[(d['symbol'],pd.Timestamp(r['date']))]=r
 obs=pd.read_parquet(ROOT/'results/stock-risk-exit/observations.parquet');rows=[]
 for r in obs[obs.status.eq('priced')].itertuples():
  dates=cal[(cal>=r.entry_date)&(cal<=r.exit_date)];values=[states.get((r.symbol,dt)) for dt in dates];known=[v for v in values if v is not None]
  rows.append(dict(symbol=r.symbol,signal_date=r.date,strategy=r.strategy,rule=r.rule,expected=len(dates),covered=len(known),complete=len(known)==len(dates),suspension_days=sum(v['tradestatus']=='0' for v in known),st_days=sum(v['isST']=='1' for v in known),entry_known=values[0] is not None,exit_known=values[-1] is not None,entry_suspended=values[0] is not None and values[0]['tradestatus']=='0',exit_suspended=values[-1] is not None and values[-1]['tradestatus']=='0'))
 table=pd.DataFrame(rows);table.to_parquet(OUT/'holding-state-coverage.parquet',index=False)
 summary=table.groupby(['strategy','rule']).agg(priced_observations=('complete','size'),fully_covered=('complete','sum'),entry_known=('entry_known','sum'),exit_known=('exit_known','sum'),entry_suspended=('entry_suspended','sum'),exit_suspended=('exit_suspended','sum'),paths_with_known_suspension=('suspension_days',lambda x:int(x.gt(0).sum())),paths_with_known_st=('st_days',lambda x:int(x.gt(0).sum()))).reset_index()
 summary.to_csv(OUT/'holding-state-summary.csv',index=False)
 #All selected entries use identical fixed127session horizon; no exit outcome or return prioritization.
 counter=Counter()
 for r in obs[['symbol','date']].drop_duplicates().itertuples():
  i=cal.get_loc(r.date);dates=cal[i+1:i+129]
  missing={dt.year for dt in dates if (r.symbol,dt) not in states}
  for year in missing:counter[(r.symbol,year)]+=1
 priority=pd.DataFrame([dict(symbol=s,year=y,signal_count=n,window_already_cached=(s,y) in windows) for (s,y),n in counter.items()]).sort_values(['signal_count','symbol','year'],ascending=[False,True,True]);priority.to_csv(OUT/'holding-state-priority.csv',index=False)
 (OUT/'holding-state-protocol.json').write_text(json.dumps({'coverage':'Provider state coverage only, not exchange-certified execution. Counts repeated across rules and overlapping entries; do not sum as unique stocks.','priority':'Unique symbol/signal-date, fixed next128 market dates; count missing symbol-year once per entry, independent of returns and chosen exit. Cached incomplete windows retained for repair, not redownloaded automatically.','limitations':['Fully covered does not verify price limits, cash settlements or delisting proceeds','Suspension within holding path need not invalidate entry/exit; actual stop timing requires reconciliation']},indent=2))
 print(summary.to_string(index=False));print('missing annual windows',len(priority))
if __name__=='__main__':main()
