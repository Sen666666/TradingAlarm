"""Fixed exit-policy diagnostic on frozen A-share entries; price labels only."""
import json,itertools
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import grouped
from stock_entry_diagnostic import ROOT
OUT=ROOT/'results/stock-risk-exit'
RULES=['trend','initial2atr','failed_breakout','trailing4atr']

def outcome(close,active,trend,entry,rule,atr,breakout):
 if rule not in RULES:raise ValueError('unknown rule')
 if not np.isfinite(atr) or atr<=0 or not np.isfinite(breakout):raise ValueError('invalid entry risk inputs')
 if entry>=len(close) or not active[entry]:return {'status':'entry_missing'}
 peak=close[entry]
 for age in range(1,127):
  j=entry+age
  if j>=len(close):return {'status':'truncated'}
  if active[j]:peak=max(peak,close[j])
  stop=(rule=='initial2atr' and close[j]<=close[entry]-2*atr) or (rule=='failed_breakout' and close[j]<breakout) or (rule=='trailing4atr' and close[j]<=peak-4*atr)
  trigger=active[j] and (trend[j] or stop)
  if trigger or age==126:
   k=j+1
   if k>=len(close) or not active[k]:return {'status':'exit_missing'}
   return {'status':'priced','return':float(close[k]/close[entry]-1),'held_sessions':age+1,'reason':'administrative126' if not trigger else ('risk' if stop else 'trend')}
 raise AssertionError('unreachable')

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'entry':'Existing monthly lowATR/RS continuous20 selections, t+1 close price proxy','trend_exit':'Existing feature: two consecutive closes below SMA200','risk_rules':'Initial stop entry minus2ATR; failed breakout below signal-day prior55high; trailing stop highest observed close minus4 entryATR. All also use baseline trend exit. ATR fixed at signal date; next-close execution, never assumed stop-price fill.','administrative_end':'Next close after day126; report separately from rule exits','limitations':['Close-price proxy, not next-open executable fills','Missing entry/exit quotes excluded and counted; no assumed fill or liquidation value','Same entries, no capital recycling, no costs or portfolio drawdown','Incomplete historical universe/actions/limits; reused sample and dependent monthly observations','Closing-price stops do not detect intraday lows; ATR thresholds frozen, no parameter search']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 selected=pd.read_parquet(ROOT/'results/stock-horizon-pairs/selected.parquet')
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values()
 selected=selected[selected.date.le(cal[-129])];wanted=set(selected.symbol);rows=[]
 bysymbol={s:g for s,g in selected.groupby('symbol')}
 cols=['symbol','date','signal_close','observed_bar','positive_volume','exit_signal','atr20','breakout55']
 for symbol,f in itertools.chain.from_iterable(grouped(pq.ParquetFile(ROOT/'data/stock-features'/p),cols) for p in ['local-features.parquet','ths-retired-features.parquet']):
  if symbol not in wanted:continue
  f=f.sort_values('date').reset_index(drop=True);lookup={dt:i for i,dt in enumerate(f.date)}
  close=f.signal_close.to_numpy();active=(f.observed_bar&f.positive_volume).to_numpy();trend=f.exit_signal.to_numpy()
  for s in bysymbol[symbol].itertuples():
   for rule in RULES:
    entry=lookup[s.date]+1
    result=outcome(close,active,trend,entry,rule,float(f.at[lookup[s.date],'atr20']),float(f.at[lookup[s.date],'breakout55']))
    if result['status']=='priced':
     result.update(entry_date=f.at[entry,'date'],exit_date=f.at[entry+result['held_sessions'],'date'])
    rows.append(dict(symbol=symbol,date=s.date,strategy=s.strategy,rule=rule,**result))
 if len(rows)!=len(selected)*len(RULES):raise AssertionError('missing selected symbol history')
 d=pd.DataFrame(rows);d.groupby(['strategy','rule','status']).size().rename('count').to_csv(OUT/'coverage.csv');d.to_parquet(OUT/'observations.parquet',index=False);results=[];annual=[]
 for (strategy,period),g in d.assign(period=np.where(d.date.dt.year<2022,'2015-2021','2022+')).groupby(['strategy','period']):
  wide=g.pivot(index=['symbol','date'],columns='rule',values='return').dropna()
  paired=g.set_index(['symbol','date']).loc[wide.index].reset_index()
  for rule,p in paired.groupby('rule'):
   dates=p.groupby('date')['return'].mean()
   delta=(wide[rule]-wide.trend).groupby(level='date').mean()
   results.append(dict(strategy=strategy,period=period,rule=rule,selected=len(g)//4,paired=len(wide),mean_return=float(dates.mean()),advantage_vs_trend=float(delta.mean()),mean_holding=float(p.held_sessions.mean()),tail80=float(p['return'].ge(.8).mean()),loss20=float(p['return'].le(-.2).mean()),return_p05=float(p['return'].quantile(.05)),administrative=int(p.reason.eq('administrative126').sum())))
   for year,v in p.groupby(p.date.dt.year):annual.append(dict(strategy=strategy,rule=rule,year=int(year),mean_return=float(v.groupby('date')['return'].mean().mean())))
 (OUT/'summary.json').write_text(json.dumps(results,indent=2));pd.DataFrame(annual).to_csv(OUT/'annual.csv',index=False)
 print(pd.DataFrame(results).to_string(index=False))
if __name__=='__main__':main()
