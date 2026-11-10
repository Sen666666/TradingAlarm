"""Capital-constrained adjusted-price simulation; NOT a verified cash/share account."""
import json,itertools
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from stock_entry_diagnostic import ROOT
from build_stock_features import grouped
OUT=ROOT/'results/stock-shadow-portfolio'

def simulate(prices,active,schedule,cost_bps,audit=None,buy_allowed=None,sell_signals=None,target_weights=None,retain_positions=False):
 if buy_allowed is not None and (not buy_allowed.index.equals(prices.index) or not buy_allowed.columns.equals(prices.columns) or buy_allowed.isna().any().any()):raise ValueError('invalid buy eligibility matrix')
 if sell_signals is not None and (not sell_signals.index.equals(prices.index) or not sell_signals.columns.equals(prices.columns) or sell_signals.isna().any().any()):raise ValueError('invalid sell signal matrix')
 if target_weights is not None and (not target_weights.index.equals(prices.index) or not target_weights.columns.equals(prices.columns) or not np.isfinite(target_weights.to_numpy()).all() or not target_weights.ge(0).all().all() or not target_weights.le(1).all().all()):raise ValueError('invalid target weights')
 pending=set();forced_sales=0;pending_days=0
 cash=1e6;held={};lastmarks={};rows=[];orders=0;totalfee=0.;maxstale=0;age={}
 for dt,quote in prices.iterrows():
  valid=active.loc[dt];stale=0
  for s in held:
   if valid[s] and np.isfinite(quote[s]):
    if audit is not None:audit.append(dict(date=dt,symbol=s,kind='mark',pnl=held[s]*(float(quote[s])-lastmarks[s]),fee=0.,value=held[s]*float(quote[s]),new_position=False))
    lastmarks[s]=float(quote[s]);age[s]=0
   else:age[s]=age.get(s,0)+1;stale+=1;maxstale=max(maxstale,age[s])
  sold_today=set()
  if sell_signals is not None:
   pending.update(s for s in held if sell_signals.at[dt,s])
   for s in sorted(pending.copy()):
    if s not in held:pending.remove(s);continue
    if not valid[s] or not np.isfinite(quote[s]):continue
    value=held[s]*float(quote[s]);fee=value*cost_bps/10000;cash+=value-fee;orders+=1;totalfee+=fee;forced_sales+=1
    if audit is not None:audit.append(dict(date=dt,symbol=s,kind='sell',pnl=0.,fee=fee,value=value,new_position=False,reason='daily_trend_exit'))
    del held[s];age.pop(s,None);pending.remove(s);sold_today.add(s)
   pending_days+=bool(pending)
  nav=cash+sum(q*lastmarks[s] for s,q in held.items())
  if dt in schedule:
   selected=schedule[dt];weights={s:(.1 if target_weights is None else float(target_weights.at[dt,s])) for s in selected}
   if sum(weights.values())>1+1e-10:raise ValueError('target leverage')
   desired={s:nav*w for s,w in weights.items()}
   if retain_positions and selected:desired.update({s:q*lastmarks[s] for s,q in held.items()})
   #Sell before buying; unknown prices cannot fund purchases.
   for s in list(held):
    if not valid[s] or not np.isfinite(quote[s]):continue
    price=float(quote[s]);value=held[s]*price;excess=value-desired.get(s,0.)
    if excess>1e-8:
     fee=excess*cost_bps/10000;cash+=excess-fee;held[s]-=excess/price;orders+=1;totalfee+=fee
     if audit is not None:audit.append(dict(date=dt,symbol=s,kind='sell',pnl=0.,fee=fee,value=excess,new_position=False))
     if held[s]<1e-8:del held[s];age.pop(s,None)
   for s in selected:
    if retain_positions and s in held:continue
    if s in pending or s in sold_today:continue
    if s not in held and buy_allowed is not None and not buy_allowed.at[dt,s]:continue
    if not valid[s] or not np.isfinite(quote[s]) or (s not in held and len(held)>=10):continue
    price=float(quote[s]);need=max(0,desired[s]-held.get(s,0)*price);value=min(need,cash/(1+cost_bps/10000))
    if value>1e-8:
     if audit is not None:audit.append(dict(date=dt,symbol=s,kind='buy',pnl=0.,fee=value*cost_bps/10000,value=value,new_position=s not in held))
     fee=value*cost_bps/10000;cash-=value+fee;held[s]=held.get(s,0)+value/price;lastmarks[s]=price;age.setdefault(s,0);orders+=1;totalfee+=fee
  if cash<-.001 or len(held)>10:raise AssertionError('capital constraint')
  nav=cash+sum(q*lastmarks[s] for s,q in held.items());stalevalue=sum(q*lastmarks[s] for s,q in held.items() if not valid[s])
  rows.append(dict(date=dt,nav=nav/1e6,cash=cash,positions=len(held),stale_positions=stale,stale_value=stalevalue,max_position_weight=max((q*lastmarks[s]/nav for s,q in held.items()),default=0.)))
 p=pd.DataFrame(rows).set_index('date');years=(p.index[-1]-p.index[0]).days/365.25;dd=p.nav/p.nav.cummax().clip(lower=1)-1
 return dict(cagr=float(p.nav.iloc[-1]**(1/years)-1),max_drawdown=float(dd.min()),best252=float(p.nav.pct_change(252).max()),total_return=float(p.nav.iloc[-1]-1),orders=orders,fees=totalfee,max_position_weight=float(p.max_position_weight.max()),forced_trend_sales=forced_sales,pending_exit_days=pending_days,days_with_stale=int(p.stale_positions.gt(0).sum()),max_stale_sessions=maxstale,terminal_stale_value=float(p.stale_value.iloc[-1]),terminal_return_if_stale_marked_zero=float(p.nav.iloc[-1]-p.stale_value.iloc[-1]/1e6-1)),p

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'status':'IDEALIZED PRICE SIMULATION, NOT VERIFIED ACCOUNT PERFORMANCE','capital':1000000,'selection':'Frozen ridge and lowATR top10 monthly selections; next observed market date close','constraints':'Up to10 positions, each rebalance target10% NAV, no borrowing, sell beforebuy, leftovercash; failed order not retried until next monthly rebalance','cost_bps_per_side':[0,20,40],'price_units':'Fractional synthetic units of adjusted signal price, not raw shares or reinvestable corporate-action cash','limitations':['Historical limits, boardlots, settlement, taxes and company-action cash/shares not modeled','Unobserved quotes block trades and retain last mark; stale valuation explicitly reported','Includes available retired histories but incomplete universe/terminal proceeds','No stop optimization or concentration tuning; reused history; not a true performance upper bound']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 selected=pd.read_parquet(ROOT/'results/stock-walkforward-rank/selected.parquet');selected=selected[selected.strategy.isin(['ridge','low_atr'])];wanted=set(selected.symbol)
 calendar=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values();nextdate=dict(zip(calendar[:-1],calendar[1:]));dates=calendar[calendar>=nextdate[selected.date.min()]]
 prices={};active={}
 for symbol,f in itertools.chain.from_iterable(grouped(pq.ParquetFile(ROOT/'data/stock-features'/p),['symbol','date','signal_close','observed_bar','positive_volume']) for p in ['local-features.parquet','ths-retired-features.parquet']):
  if symbol not in wanted:continue
  f=f.set_index('date');prices[symbol]=f.signal_close.reindex(dates);active[symbol]=(f.observed_bar&f.positive_volume).reindex(dates,fill_value=False)
 if set(prices)!=wanted:raise AssertionError('missing symbol data')
 prices=pd.DataFrame(prices);active=pd.DataFrame(active);results=[]
 for strategy,g in selected.groupby('strategy'):
  schedule={nextdate[dt]:sorted(f.symbol) for dt,f in g.groupby('date') if dt in nextdate}
  for cost in protocol['cost_bps_per_side']:
   m,p=simulate(prices,active,schedule,cost);m.update(strategy=strategy,cost_bps=cost);results.append(m);p.to_csv(OUT/f'{strategy}-{cost}-path.csv')
 (OUT/'results.json').write_text(json.dumps(results,indent=2));print(pd.DataFrame(results).to_string(index=False))
if __name__=='__main__':main()
