"""One frozen breadth risk overlay with delayed execution sensitivity."""
import json,itertools
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from stock_shadow_portfolio import ROOT,simulate
from build_stock_features import grouped
OUT=ROOT/'results/stock-shadow-market-gate'

def gated_schedule(dates,base,breadth,lag=1):
 #Shift on full market calendar before truncating portfolio period.
 gate=breadth.gt(.5).where(breadth.notna()).shift(lag).reindex(dates)
 if gate.isna().any():raise ValueError('missing lagged market state')
 result={};latest=[];previous=False
 for dt in dates:
  if dt in base:latest=base[dt]
  on=bool(gate.loc[dt])
  if not on:result[dt]=[] #Keep attempting liquidation when quotes resume.
  elif not previous or dt in base:result[dt]=list(latest)
  previous=on
 return result,gate

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'rule':'More than50% of eligible observed stocks above own SMA200; otherwise cash','lag_sessions':[1,2],'trade':'Next-close proxy after lag; lag2 is sensitivity, not a tuned variant','selection':'Original frozen monthly ridge/lowATR selections maintained; reopening uses latest available monthly list, no new stock ranking','blocked_sales':'During risk-off, repeat liquidation attempts daily; suspended/unobserved quotes never fund buys','cost_bps_per_side':[20,40],'limitations':['Same adjusted-price shadow model and incomplete universe; no raw shares/cash actions/dated limits','Breadth itself uses surviving-stock dominated historical coverage','Binary gate may whipsaw; no threshold or hysteresis search','Risk-on reopening can use an old monthly selection; not fresh breakout confirmation','Not a market-wide validated80%/20% strategy']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 selected=pd.read_parquet(ROOT/'results/stock-walkforward-rank/selected.parquet');selected=selected[selected.strategy.isin(['ridge','low_atr'])];wanted=set(selected.symbol)
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values();nextdate=dict(zip(cal[:-1],cal[1:]));dates=cal[cal>=nextdate[selected.date.min()]]
 breadth=pd.read_csv(ROOT/'results/stock-breadth-v1/daily-breadth.csv',index_col=0,parse_dates=True).fraction_above_sma200.reindex(cal)
 prices={};active={}
 for symbol,f in itertools.chain.from_iterable(grouped(pq.ParquetFile(ROOT/'data/stock-features'/p),['symbol','date','signal_close','observed_bar','positive_volume']) for p in ['local-features.parquet','ths-retired-features.parquet']):
  if symbol not in wanted:continue
  f=f.set_index('date');prices[symbol]=f.signal_close.reindex(dates);active[symbol]=(f.observed_bar&f.positive_volume).reindex(dates,fill_value=False)
 if set(prices)!=wanted:raise AssertionError('missing symbols')
 prices=pd.DataFrame(prices);active=pd.DataFrame(active);results=[]
 for strategy,g in selected.groupby('strategy'):
  base={nextdate[dt]:sorted(f.symbol) for dt,f in g.groupby('date') if dt in nextdate}
  for lag in [1,2]:
   schedule,gate=gated_schedule(dates,base,breadth,lag)
   for cost in [20,40]:
    m,p=simulate(prices,active,schedule,cost);m.update(strategy=strategy,lag=lag,cost_bps=cost,risk_on_fraction=float(gate.astype(bool).mean()));results.append(m);p.to_csv(OUT/f'{strategy}-lag{lag}-cost{cost}-path.csv')
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print(pd.DataFrame(results)[['strategy','lag','cost_bps','cagr','max_drawdown','best252','orders','days_with_stale','risk_on_fraction']].to_string(index=False))
if __name__=='__main__':main()
