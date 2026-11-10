"""Inventory-aware long-only trend campaigns. Research, never broker routing.
Causal additive dividend/split-adjusted prices drive signals; actual raw shares,
CNY cash and dividend receivables drive account equity. Stops execute next open,
not at hypothetical stop prices. No leverage, no fixed profit-taking.
"""
import math
import numpy as np
import pandas as pd
from portfolio_data import fx_series

def features(a):
 raw=a['raw'];factor=pd.Series(1.,index=raw.index);cash=pd.Series(0.,index=raw.index)
 for e in a['splits']:factor.loc[e['date']]*=e['ratio']
 factor=factor.cumprod()
 for e in a['dividends']:cash.loc[e['ex_date']]+=e['amount']*factor.loc[e['ex_date']]
 cash=cash.cumsum();p=raw[['open','high','low','close']].mul(factor,axis=0).add(cash,axis=0)
 tr=pd.concat([p.high-p.low,(p.high-p.close.shift()).abs(),(p.low-p.close.shift()).abs()],axis=1).max(axis=1)
 p['atr']=tr.rolling(20).mean();p['upper']=p.high.shift().rolling(55).max();p['ma']=p.close.rolling(200).mean()
 p['strength']=a['signal'].close.pct_change(126);p['factor']=factor;p['cash_adjustment']=cash
 return p

def run_campaign(assets,start='2022-01-01',pyramid=True,risk_fraction=.005,entry='breakout',
                 cost_bps=15,fx_bps=10,extra_delay=0,initial=1_000_000):
 names=sorted(n for n in assets if assets[n]['kind']=='equity');assets={n:assets[n] for n in names}
 calendar=pd.DatetimeIndex(sorted(set().union(*(a['raw'].index for a in assets.values()))))
 fx=fx_series(calendar);fs={n:features(a) for n,a in assets.items()}
 closes=pd.DataFrame({n:a['raw'].close.reindex(calendar).ffill() for n,a in assets.items()})
 adv={n:a['raw'].volume.rolling(20).mean()*a.get('volume_multiplier',1) for n,a in assets.items()}
 split={n:{pd.Timestamp(e['date']):e['ratio'] for e in a['splits']} for n,a in assets.items()}
 div={n:{pd.Timestamp(e['ex_date']):e for e in a['dividends']} for n,a in assets.items()}
 shares={n:0. for n in names};state={};pending={};receipts=[];cash=initial;peak=initial;risk_peak=initial;prev_nav=initial
 logs=[];orders=[];completed=[];cid=0;cooldown=0
 for date in calendar[calendar>=pd.Timestamp(start)]:
  prev=calendar[calendar.get_loc(date)-1];fees=0.
  rates={n:float(fx.loc[date]) if assets[n]['currency']=='HKD' else 1. for n in names}
  for n in names:
   shares[n]*=split[n].get(date,1)
   if date in div[n] and shares[n]:
    e=div[n][date];amount=shares[n]*e['amount'];receipts.append((n,pd.Timestamp(e['pay_date']),amount,state[n]['id']))
    state[n]['dividend_claims']+=amount*rates[n]
  unpaid=[]
  for n,pay,amount,campaign_id in receipts:
   if pay<=date:
    fee=amount*rates[n]*fx_bps/10000 if assets[n]['currency']=='HKD' else 0
    cash+=amount*rates[n]-fee;fees+=fee
   else:unpaid.append((n,pay,amount,campaign_id))
  receipts=unpaid
  due=sum(amount*rates[n] for n,_,amount,_ in receipts)
  # Signals strictly through previous union close, asset-specific latest bar.
  past={n:fs[n].loc[:prev].iloc[-1] for n in names}
  dd=prev_nav/risk_peak-1
  if cooldown==0 and dd<=-.16:cooldown=20
  halted=cooldown>0
  if halted and not any(shares.values()):
   cooldown-=1
   if cooldown==0:risk_peak=prev_nav
  for n in names:
   q=past[n];s=state.get(n)
   if s:
    s['high']=max(s['high'],q.close);s['stop']=max(s['stop'],s['high']-4*q.atr)
    if halted or q.close<s['stop']:
     if pending.get(n,{}).get('type')!='exit':pending[n]={'type':'exit','delay':extra_delay,'signal_date':str(prev.date())}
    elif pyramid and s['layers']<3 and q.close>=s['last_add']+2*s['entry_atr'] and n not in pending and dd>-.10:
     pending[n]={'type':'add','delay':extra_delay,'signal_date':str(prev.date()),'atr':float(q.atr)}
   elif n not in pending and not halted and pd.notna(q.atr) and q.atr>0:
    enter=q.close>q.upper if entry=='breakout' else q.close>q.ma and q.strength>0
    if enter:pending[n]={'type':'entry','delay':extra_delay,'signal_date':str(prev.date()),'atr':float(q.atr)}
  opens={n:float(assets[n]['raw'].loc[date,'open']) if date in assets[n]['raw'].index else float(closes.loc[prev,n]) for n in names}
  navopen=cash+due+sum(shares[n]*opens[n]*rates[n] for n in names)
  ranked=sorted(pending,key=lambda n:(pending[n]['type']!='exit',-float(past[n].strength) if pd.notna(past[n].strength) else 0,n))
  for n in ranked:
   order=pending[n];a=assets[n]
   if date not in a['raw'].index or a['raw'].loc[date,'volume']<=0:continue
   if order['delay']>0:order['delay']-=1;continue
   typ=order['type'];lot=a['lot'];price=opens[n];unit=price*rates[n]
   f=fs[n].loc[date,'factor'];offset=fs[n].loc[date,'cash_adjustment'];adjopen=price*f+offset
   s=state.get(n)
   allowed=math.floor(float(adv[n].loc[:prev].iloc[-1])*.01/lot)*lot
   rate=(cost_bps+(fx_bps if a['currency']=='HKD' else 0))/10000
   minimum=18*rates[n] if a['currency']=='HKD' else 5.
   if typ=='exit':delta=-min(shares[n],allowed)
   else:
    # Conditions revalidated after delay. Never add below prior actual fill.
    q=past[n]
    valid=(q.close>q.upper if entry=='breakout' else q.close>q.ma and q.strength>0) if typ=='entry' else (s is not None and adjopen>s['last_add'] and q.close>=s['last_add']+2*s['entry_atr'])
    if not valid or halted or (typ=='add' and dd<=-.10):
     del pending[n];continue
    if typ=='entry' and sum(shares[k]>0 for k in names)>=4:
     del pending[n];continue
    distance=4*order['atr']/f
    new_risk=risk_fraction*(.5 if dd<=-.10 else 1.)
    quantity=math.floor(prev_nav*new_risk/(distance*rates[n])/lot)*lot
    exposure=sum(shares[k]*opens[k]*rates[k] for k in names)
    sector=sum(shares[k]*opens[k]*rates[k] for k in names if assets[k]['sector']==a['sector'])
    hk=sum(shares[k]*opens[k]*rates[k] for k in names if assets[k]['currency']=='HKD')
    # Exposure caps limit new buying; winners may drift higher until an exit.
    room=min(.9*navopen-exposure,.35*navopen-shares[n]*unit,.45*navopen-sector)
    if a['currency']=='HKD':room=min(room,.5*navopen-hk)
    # Sum distance to current stops is a planned-loss estimate, not gap protection.
    risk=sum(max(0,opens[k]*fs[k].loc[:date,'factor'].iloc[-1]+fs[k].loc[:date,'cash_adjustment'].iloc[-1]-state[k]['stop'])/fs[k].loc[:date,'factor'].iloc[-1]*shares[k]*rates[k] for k in state)
    roomqty=max(0,(.04*prev_nav-risk)/(distance*rates[n]))
    delta=min(quantity,allowed,math.floor(max(0,room)/unit/lot)*lot,math.floor(roomqty/lot)*lot,
              math.floor(max(0,cash-minimum)/(unit*(1+rate))/lot)*lot)
   if not delta:
    if typ!='exit':del pending[n]
    continue
   fee=max(abs(delta)*unit*rate,minimum)
   if delta>0 and delta*unit+fee>cash:del pending[n];continue
   cash-=delta*unit+fee;fees+=fee;shares[n]+=delta
   if delta>0:
    if typ=='entry':
     cid+=1;state[n]={'id':cid,'entry_date':str(date.date()),'layers':0,'entry_atr':order['atr'],'high':adjopen,
                     'stop':adjopen-4*order['atr'],'buy_cash':0.,'sell_cash':0.,'dividend_claims':0.}
    s=state[n];s['layers']+=1;s['last_add']=adjopen;s['buy_cash']+=delta*unit+fee;s['stop']=max(s['stop'],adjopen-4*order['atr'])
   else:state[n]['sell_cash']+=-delta*unit-fee
   orders.append({'date':str(date.date()),'signal_date':order['signal_date'],'symbol':n,'type':typ,'units':float(delta),'raw_open':price,'fx':rates[n],'fee':fee,'campaign_id':state[n]['id']})
   if shares[n]==0:
    s=state.pop(n);s.update(symbol=n,exit_date=str(date.date()),pnl=s['sell_cash']+s['dividend_claims']-s['buy_cash'])
    completed.append(s)
   if typ!='exit' or shares[n]==0:del pending[n]
  if cash<-.001 or min(shares.values())<0:raise AssertionError('Unfunded position')
  nav=cash+due+sum(shares[n]*float(closes.loc[date,n])*rates[n] for n in names)
  peak=max(peak,nav);risk_peak=max(risk_peak,nav)
  logs.append({'date':date,'nav':nav/initial,'return_daily':nav/prev_nav-1,'drawdown':nav/peak-1,'cash':cash,'fees':fees,
               **{'w_'+n:shares[n]*float(closes.loc[date,n])*rates[n]/nav for n in names}})
  prev_nav=nav
 path=pd.DataFrame(logs).set_index('date');r=path.return_daily;years=(path.index[-1]-path.index[0]).days/365.25
 metrics={'cagr':float(path.nav.iloc[-1]**(1/years)-1),'total_return':float(path.nav.iloc[-1]-1),'max_drawdown':float(path.drawdown.min()),
          'fees':float(path.fees.sum()),'orders':len(orders),'closed_campaigns':len(completed),'open_campaigns':len(state),
          'best252_return':float(((1+r).rolling(252).apply(np.prod,raw=True)-1).max()),
          'average_cash_weight':float((path.cash/(path.nav*initial)).mean())}
 return metrics,path,orders,completed,state
