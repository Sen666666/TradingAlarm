"""Reconcile daily attribution and audit causal entry context, without excluding losers."""
import json,itertools
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from stock_shadow_portfolio import ROOT,simulate
from stock_shadow_market_gate import gated_schedule
from build_stock_features import grouped
OUT=ROOT/'results/stock-shadow-loss-audit'
def main():
 OUT.mkdir(exist_ok=True)
 selected=pd.read_parquet(ROOT/'results/stock-walkforward-rank/selected.parquet');selected=selected[selected.strategy.eq('ridge')];wanted=set(selected.symbol)
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values();nextdate=dict(zip(cal[:-1],cal[1:]));dates=cal[cal>=nextdate[selected.date.min()]]
 prices={};active={};contexts=[]
 for symbol,f in itertools.chain.from_iterable(grouped(pq.ParquetFile(ROOT/'data/stock-features'/p),['symbol','date','signal_close','sma200','entry_signal','observed_bar','positive_volume']) for p in ['local-features.parquet','ths-retired-features.parquet']):
  if symbol not in wanted:continue
  f=f.set_index('date').reindex(cal);prices[symbol]=f.signal_close.reindex(dates);active[symbol]=(f.observed_bar.fillna(False)&f.positive_volume.fillna(False)).reindex(dates)
  context=pd.DataFrame({'prior_above_sma':f.signal_close.gt(f.sma200).shift(),'prior_entry_signal':f.entry_signal.shift(),'symbol':symbol},index=cal);context.index.name='date';contexts.append(context.reset_index())
 prices=pd.DataFrame(prices);active=pd.DataFrame(active);context=pd.concat(contexts).set_index(['date','symbol']);base={nextdate[dt]:sorted(f.symbol) for dt,f in selected.groupby('date') if dt in nextdate}
 breadth=pd.read_csv(ROOT/'results/stock-breadth-v1/daily-breadth.csv',index_col=0,parse_dates=True).fraction_above_sma200.reindex(cal);gated,_=gated_schedule(dates,base,breadth)
 report=[]
 for name,schedule,file in [('base',base,ROOT/'results/stock-shadow-portfolio/ridge-20-path.csv'),('gate',gated,ROOT/'results/stock-shadow-market-gate/ridge-lag1-cost20-path.csv')]:
  audit=[];m,p=simulate(prices,active,schedule,20,audit=audit);old=pd.read_csv(file,index_col=0,parse_dates=True);np.testing.assert_allclose(p.nav,old.nav,atol=1e-12)
  a=pd.DataFrame(audit);a['net_pnl']=a.pnl-a.fee;daily=a.groupby('date').net_pnl.sum().reindex(p.index,fill_value=0);np.testing.assert_allclose(1+daily.cumsum()/1e6,p.nav,atol=1e-10)
  a.to_parquet(OUT/f'{name}-ledger.parquet',index=False)
  buys=a[a.kind.eq('buy')&a.new_position].merge(context.reset_index(),on=['date','symbol'],how='left',validate='many_to_one');buys['monthly_execution']=buys.date.isin(base);buys.to_csv(OUT/f'{name}-entry-context.csv',index=False)
  dd=p.nav/p.nav.cummax().clip(lower=1)-1;trough=dd.idxmin();peak=p.loc[:trough].nav.idxmax();window=a[a.date.gt(peak)&a.date.le(trough)]
  losses=window.groupby('symbol').net_pnl.sum().sort_values();losses.to_csv(OUT/f'{name}-drawdown-contributions.csv')
  report.append(dict(variant=name,reconciled=True,new_entries=len(buys),entries_below_sma=int(buys.prior_above_sma.eq(False).sum()),entries_without_fresh_breakout=int(buys.prior_entry_signal.eq(False).sum()),nonmonthly_entries=int((~buys.monthly_execution).sum()),peak=str(peak.date()),trough=str(trough.date()),drawdown_cash_loss=float(window.net_pnl.sum()),losing_stocks=int(losses.lt(0).sum()),winning_stocks=int(losses.gt(0).sum()),top10_losses=float(losses[losses.lt(0)].head(10).sum()),all_losses=float(losses[losses.lt(0)].sum()),fees_during_drawdown=float(window.fee.sum())))
 (OUT/'summary.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
if __name__=='__main__':main()
