"""One frozen breadth risk overlay with delayed execution sensitivity."""
import json,itertools
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from stock_shadow_portfolio import ROOT,simulate
from build_stock_features import grouped
OUT=ROOT/'results/stock-shadow-horizon-retention'

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

def monthly_schedule(calendar,selections,lag):
 execution={dt:calendar[i+lag] for i,dt in enumerate(calendar) if i+lag<len(calendar)}
 return {execution[dt]:sorted(f.symbol) for dt,f in selections.groupby('date') if dt in execution}

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'rule':'Original majority SMA200 market gate plus lagged individual entry signal for every new position; rejected slots stay cash','lag_sessions':[1,2],'trade':'Monthly selection execution and both market/individual signal lookbacks delayed consistently by lag1/2; next-close proxy, not tuned','selection':'Original frozen monthly ridge/lowATR selections maintained; reopening uses latest available monthly list, no new stock ranking','blocked_sales':'During risk-off, repeat liquidation attempts daily; suspended/unobserved quotes never fund buys','cost_bps_per_side':[20,40],'limitations':['Same adjusted-price shadow model and incomplete universe; no raw shares/cash actions/dated limits','Breadth itself uses surviving-stock dominated historical coverage','Binary gate may whipsaw; no threshold or hysteresis search','Latest monthly list retained, no replacement search; existing-position topups are unchanged and not new-entry gated','Not a market-wide validated80%/20% strategy']}
 protocol['retention']='During market risk-on keep existing synthetic units until fixed individual exit, regardless of monthly rank; no topups or equalweight trimming. Risk-off still exits all. New entries target10% current NAV, max10 slots and availablecash. Existing weights can drift above10%, reported explicitly.'
 protocol['daily_exit']='Existing two-consecutive-closes belowSMA200 feature, delayed by same lag; pending exits retained while quotes missing; no same-day reentry; released cash waits for schedule'
 protocol['experiment']='Frozen21/126 model selections on common dates; compare monthly replacement versus retained positions, identical daily exit and breadth gate. No refit or tuning. Original horizon models shared maturedtraining for matched comparisons.'
 protocol['evaluated_cases']=[{'lag':1,'cost_bps':20},{'lag':2,'cost_bps':40}]
 protocol['selection']='Existing stock-forecast-horizon selected.parquet: short_latest,short_matched,long_matched'
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 selected=pd.read_parquet(ROOT/'results/stock-forecast-horizon/selected.parquet');selected=selected[selected.strategy.isin(['short_latest','short_matched','long_matched'])];wanted=set(selected.symbol)
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values();nextdate=dict(zip(cal[:-1],cal[1:]));dates=cal[cal>=nextdate[selected.date.min()]]
 breadth=pd.read_csv(ROOT/'results/stock-breadth-v1/daily-breadth.csv',index_col=0,parse_dates=True).fraction_above_sma200.reindex(cal)
 prices={};active={};eligibility={};exits={}
 for symbol,f in itertools.chain.from_iterable(grouped(pq.ParquetFile(ROOT/'data/stock-features'/p),['symbol','date','signal_close','observed_bar','positive_volume','entry_signal','warmup_ready','exit_signal']) for p in ['local-features.parquet','ths-retired-features.parquet']):
  if symbol not in wanted:continue
  f=f.set_index('date');exits[symbol]=(f.exit_signal & f.observed_bar & f.positive_volume).reindex(cal,fill_value=False);eligibility[symbol]=(f.entry_signal & f.warmup_ready & f.observed_bar & f.positive_volume).reindex(cal,fill_value=False);prices[symbol]=f.signal_close.reindex(dates);active[symbol]=(f.observed_bar&f.positive_volume).reindex(dates,fill_value=False)
 if set(prices)!=wanted:raise AssertionError('missing symbols')
 prices=pd.DataFrame(prices);active=pd.DataFrame(active);results=[]
 for strategy,g in selected.groupby('strategy'):
  for lag in [1,2]:
   base=monthly_schedule(cal,g,lag)
   schedule,gate=gated_schedule(dates,base,breadth,lag)
   for retain in [False,True]:
    cost=20 if lag==1 else 40
    allowed=pd.DataFrame(eligibility).shift(lag).reindex(dates).fillna(False).astype(bool)
    sell=pd.DataFrame(exits).shift(lag).reindex(dates).fillna(False).astype(bool)
    audit=[];m,p=simulate(prices,active,schedule,cost,audit=audit,buy_allowed=allowed,sell_signals=sell,retain_positions=retain)
    buys=[x for x in audit if x['kind']=='buy' and x['new_position']]
    if not all(allowed.at[x['date'],x['symbol']] for x in buys):raise AssertionError('unqualified entry')
    print('completed',strategy,retain,lag,cost,flush=True)
    m['new_positions']=len(buys);m.update(strategy=strategy,retain_positions=retain,lag=lag,cost_bps=cost,risk_on_fraction=float(gate.astype(bool).mean()));results.append(m);p.to_csv(OUT/f'{strategy}-retain{retain}-lag{lag}-cost{cost}-path.csv')
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print(pd.DataFrame(results)[['strategy','retain_positions','lag','cost_bps','cagr','max_drawdown','best252','orders','days_with_stale','risk_on_fraction']].to_string(index=False))
if __name__=='__main__':main()
