"""Inventory-aware long-only trend campaigns. Research, never broker routing.
Causal additive dividend/split-adjusted prices drive signals; actual raw shares,
CNY (default) or explicitly configured USD cash and dividend receivables drive equity. Stops execute next open,
not at hypothetical stop prices. No leverage, no fixed profit-taking.
"""
import math
import numpy as np
import pandas as pd
from portfolio_data import fx_series

def dividend_local_value(asset,event,date):
 date=pd.Timestamp(date);currency=event.get('currency',asset['currency'])
 if currency==asset['currency']:return event['amount']
 if currency!='USD' or asset['currency']!='HKD':raise ValueError('Unsupported dividend currency')
 settlement=event.get('settlement')
 if settlement and date>pd.Timestamp(settlement['fixing']):return float(settlement['hkd_per_share'])
 history=asset['dividend_fx'].loc[:date]
 if history.empty or not np.isfinite(history.iloc[-1]) or history.iloc[-1]<=0:raise ValueError('Missing dividend FX')
 return event['amount']*float(history.iloc[-1])

def features(a):
 raw=a['raw'];factor=pd.Series(1.,index=raw.index);cash=pd.Series(0.,index=raw.index)
 for e in a['splits']:factor.loc[e['date']]*=e['ratio']
 factor=factor.cumprod()
 for e in a['dividends']:cash.loc[e['ex_date']]+=dividend_local_value(a,e,e['ex_date'])*factor.loc[e['ex_date']]
 for e in a.get('in_kind',[]):cash.loc[e['ex_date']]+=e['signal_reference_value']*factor.loc[e['ex_date']]
 cash=cash.cumsum();p=raw[['open','high','low','close']].mul(factor,axis=0).add(cash,axis=0)
 tr=pd.concat([p.high-p.low,(p.high-p.close.shift()).abs(),(p.low-p.close.shift()).abs()],axis=1).max(axis=1)
 p['atr']=tr.rolling(20).mean();p['upper']=p.high.shift().rolling(55).max();p['ma']=p.close.rolling(200).mean()
 p['trend_exit']=(p.close<p.ma)&(p.close.shift()<p.ma.shift())
 p['strength']=a['signal'].close.pct_change(126);p['factor']=factor;p['cash_adjustment']=cash
 return p

def order_priority(name,order,q,ranking):
 # Normalize ATR by split-adjusted raw close; accumulated cash dividends must
 # not mechanically reduce the measured volatility of a high-yield asset.
 if ranking=='strength':score=-float(q.strength) if pd.notna(q.strength) else 0.
 else:
  denominator=float(q.close-q.cash_adjustment)
  score=float(q.atr)/denominator if denominator>0 and pd.notna(q.atr) else float('inf')
 return (order['type']!='exit',score,name)

def dual_risk_capacity(current_risks,original_risks,nav,unit_risk,initial_cap=.04):
 # The second ceiling is frozen at the existing10percent risk-reduction level.
 # Both are buying constraints, not promises about future gap/drawdown losses.
 if nav<=0 or unit_risk<=0:raise ValueError('Positive NAV/unit risk required')
 if set(current_risks)!=set(original_risks):raise ValueError('Risk positions mismatch')
 current=sum(current_risks.values())
 initial=sum(min(v,original_risks[k]) for k,v in current_risks.items())
 quantity=max(0.,min((initial_cap*nav-initial)/unit_risk,(.10*nav-current)/unit_risk))
 return quantity,initial,current


def run_campaign(assets,start='2022-01-01',pyramid=True,risk_fraction=.005,entry='breakout',
                 cost_bps=15,fx_bps=10,extra_delay=0,initial=1_000_000,exit_mode='atr',planned_risk_cap=.04,ranking='strength',decision_audit=None,stop_mode='shared',max_positions=4,eligible_kinds=('equity',),security_claims=None,complete_initial=False,base_currency='CNY',settlement_scenario=False,buying_risk_mode='current_stop',avoid_active_exit=False):
 if avoid_active_exit and exit_mode!='trend':raise ValueError('Entry consistency requires trend exit')
 if buying_risk_mode not in ('current_stop','dual'):raise ValueError('Unknown buying risk mode')
 if buying_risk_mode=='dual' and (pyramid or complete_initial or stop_mode!='shared' or exit_mode!='trend' or security_claims is not None):raise ValueError('Dual risk experiment requires noadd/shared/trend and no security claims')
 if base_currency not in ('CNY','USD'):raise ValueError('Unsupported account currency')
 if complete_initial and (pyramid or stop_mode!='shared' or exit_mode!='trend' or entry!='breakout'):
  raise ValueError('Initial completion requires breakout/trend/shared stops and no pyramiding')
 if not isinstance(max_positions,int) or isinstance(max_positions,bool) or max_positions<1:raise ValueError('max_positions must be a positive integer')
 if stop_mode not in ['shared','layers']:raise ValueError(stop_mode)
 if stop_mode=='layers' and exit_mode!='trend':raise ValueError('Layer stops require trend exit')
 if ranking not in ['strength','low_atr']:raise ValueError(ranking)
 if exit_mode not in ['atr','trend']:raise ValueError(exit_mode)
 names=sorted(n for n in assets if assets[n]['kind'] in eligible_kinds);assets={n:assets[n] for n in names}
 if not names:raise ValueError('No eligible assets')
 if base_currency=='USD':
  if security_claims is not None:raise ValueError('USD security claims are not implemented')
  for a in assets.values():
   if a['currency']!='USD':raise ValueError('USD account requires USD assets')
   if not np.isfinite(a.get('commission_min',float('nan'))) or a['commission_min']<0:raise ValueError('Explicit USD commission minimum required')
   for e in a['dividends']:
    if e.get('currency','USD')!='USD':raise ValueError('USD account requires USD distributions')
    if pd.Timestamp(e['ex_date'])>=pd.Timestamp(start):
     if not (e.get('settlement_verified') or (settlement_scenario and e.get('settlement_scenario'))) or not e.get('pay_date') or pd.Timestamp(e['pay_date'])<pd.Timestamp(e['ex_date']):raise ValueError('Unverified USD distribution settlement')
 else:
  if any(a['currency'] not in ('CNY','HKD') for a in assets.values()):raise ValueError('CNY account supports only CNY/HKD assets')
 calendar=pd.DatetimeIndex(sorted(set().union(*(a['raw'].index for a in assets.values()))))
 fx=pd.Series(1.,index=calendar) if base_currency=='USD' else fx_series(calendar);fs={n:features(a) for n,a in assets.items()}
 closes=pd.DataFrame({n:a['raw'].close.reindex(calendar).ffill() for n,a in assets.items()})
 adv={n:a['raw'].volume.rolling(20).mean()*a.get('volume_multiplier',1) for n,a in assets.items()}
 split={n:{pd.Timestamp(e['date']):e['ratio'] for e in a['splits']} for n,a in assets.items()}
 div={n:{} for n in names}
 for n,a in assets.items():
  for e in a['dividends']:div[n].setdefault(pd.Timestamp(e['ex_date']),[]).append(e)
 shares={n:0. for n in names};state={};pending={};receipts=[];cash=initial;peak=initial;risk_peak=initial;prev_nav=initial
 logs=[];orders=[];completed=[];cid=0;cooldown=0
 for date in calendar[calendar>=pd.Timestamp(start)]:
  prev=calendar[calendar.get_loc(date)-1];fees=0.
  rates={n:float(fx.loc[date]) if assets[n]['currency']=='HKD' else 1. for n in names}
  for n in names:
   shares[n]*=split[n].get(date,1)
   if stop_mode=='layers' and n in state:
    for layer in state[n]['inventory']:layer['units']*=split[n].get(date,1)
   if date in div[n] and shares[n]:
    for e in div[n][date]:
     amount=shares[n]*dividend_local_value(assets[n],e,date);receipts.append((n,pd.Timestamp(e['pay_date']),shares[n],e,state[n]['id']))
     state[n]['dividend_claims']+=amount*rates[n]
  unpaid=[]
  for n,pay,quantity,e,campaign_id in receipts:
   amount=quantity*dividend_local_value(assets[n],e,date)
   if pay<=date:
    fee=amount*rates[n]*fx_bps/10000 if assets[n]['currency']=='HKD' else 0
    foreign=e.get('currency',assets[n]['currency'])!=assets[n]['currency']
    fixed=e.get('settlement') and date>pd.Timestamp(e['settlement']['fixing'])
    if foreign and not fixed:fee+=amount*rates[n]*e.get('conversion_bps',10)/10000
    cash+=amount*rates[n]-fee;fees+=fee
   else:unpaid.append((n,pay,quantity,e,campaign_id))
  receipts=unpaid
  due=sum(quantity*dividend_local_value(assets[n],e,date)*rates[n] for n,_,quantity,e,_ in receipts)
  claim_open={};claim_close={};claim_due=0.
  if security_claims is not None:
   paid,claim_fees=security_claims.step(date,shares,float(fx.loc[date]),fx_bps);cash+=paid;fees+=claim_fees
   claim_open,claim_due=security_claims.values(date,float(fx.loc[date]),'open')
   claim_close,_=security_claims.values(date,float(fx.loc[date]),'close')
   due+=claim_due
  # Signals strictly through previous union close, asset-specific latest bar.
  past={n:fs[n].loc[:prev].iloc[-1] for n in names}
  dd=prev_nav/risk_peak-1
  if cooldown==0 and dd<=-.16:cooldown=20
  halted=cooldown>0
  if halted and not any(shares.values()) and not any(claim_open.values()):
   cooldown-=1
   if cooldown==0:risk_peak=prev_nav
  for n in names:
   q=past[n];s=state.get(n)
   if decision_audit is not None and s is None:
    decision_audit.append(dict(date=str(date.date()),symbol=n,event='flat_signal',
     ma=bool(q.close>q.ma and q.strength>0),breakout=bool(q.close>q.upper),halted=halted,
     occupied=sum(shares[k]>0 for k in names),drawdown=float(dd)))
   if s:
    s['high']=max(s['high'],q.close)
    if exit_mode=='atr':s['stop']=max(s['stop'],s['high']-4*q.atr)
    layer_hits=[v['id'] for v in s.get('inventory',[]) if v['units']>0 and q.close<v['stop']]
    if stop_mode=='layers' and (halted or q.trend_exit or layer_hits):
     s['stop_triggered']=True
     existing=pending.get(n,{})
     if existing.get('type')!='exit':
      pending[n]={'type':'exit','delay':extra_delay,'signal_date':str(prev.date()),'layer_ids':layer_hits}
     else:
      pending[n]['layer_ids']=sorted(set(existing.get('layer_ids',[])+layer_hits))
     if halted or q.trend_exit or existing.get('exit_all',False):pending[n]['exit_all']=True
    elif stop_mode=='shared' and (halted or q.close<s['stop'] or (exit_mode=='trend' and q.trend_exit)):
     if decision_audit is not None:decision_audit.append(dict(date=str(date.date()),symbol=n,event='exit_trigger',campaign_id=s['id'],halted=halted,below_stop=bool(q.close<s['stop']),below_trend=bool(exit_mode=='trend' and q.trend_exit),signal_close=float(q.close),stop=float(s['stop'])))
     if pending.get(n,{}).get('type')!='exit':pending[n]={'type':'exit','delay':extra_delay,'signal_date':str(prev.date())}
    elif complete_initial and s['completion_budget']>s['committed_risk']+1e-8 and q.close>q.upper and n not in pending and dd>-.10:
     pending[n]={'type':'complete','delay':extra_delay,'signal_date':str(prev.date())}
    elif pyramid and not s.get('stop_triggered',False) and s['layers']<3 and q.close>=s['last_add']+2*s['entry_atr'] and n not in pending and dd>-.10:
     pending[n]={'type':'add','delay':extra_delay,'signal_date':str(prev.date()),'atr':float(q.atr)}
   elif n not in pending and not halted and pd.notna(q.atr) and q.atr>0:
    enter=q.close>q.upper if entry=='breakout' else q.close>q.ma and q.strength>0
    if avoid_active_exit and q.trend_exit:enter=False
    if enter:pending[n]={'type':'entry','delay':extra_delay,'signal_date':str(prev.date()),'atr':float(q.atr)}
  opens={n:float(assets[n]['raw'].loc[date,'open']) if date in assets[n]['raw'].index else float(closes.loc[prev,n]) for n in names}
  navopen=cash+due+sum(shares[n]*opens[n]*rates[n] for n in names)+sum(claim_open.values())
  ranked=sorted(pending,key=lambda n:order_priority(n,pending[n],past[n],ranking))
  for n in ranked:
   order=pending[n];a=assets[n]
   if date not in a['raw'].index or a['raw'].loc[date,'volume']<=0:continue
   if order['delay']>0:order['delay']-=1;continue
   typ=order['type'];lot=a['lot'];price=opens[n];unit=price*rates[n]
   f=fs[n].loc[date,'factor'];offset=fs[n].loc[date,'cash_adjustment'];adjopen=price*f+offset
   s=state.get(n)
   allowed=math.floor(float(adv[n].loc[:prev].iloc[-1])*.01/lot)*lot
   rate=(cost_bps+(fx_bps if a['currency']=='HKD' else 0))/10000
   minimum=a['commission_min'] if base_currency=='USD' else (18*rates[n] if a['currency']=='HKD' else 5.)
   if typ=='exit':
    target_shares=shares[n]
    if stop_mode=='layers' and not order.get('exit_all',False):
     target_shares=sum(v['units'] for v in s['inventory'] if v['id'] in order['layer_ids'])
    delta=-min(target_shares,allowed)
   else:
    # Conditions revalidated after delay. Never add below prior actual fill.
    q=past[n]
    valid=(q.close>q.upper if entry=='breakout' else q.close>q.ma and q.strength>0) if typ=='entry' else (s is not None and adjopen>s['last_add'] and q.close>=s['last_add']+2*s['entry_atr'])
    if avoid_active_exit and typ=='entry' and q.trend_exit:valid=False
    if typ=='complete':valid=s is not None and q.close>q.upper and adjopen>=s['last_add'] and adjopen>s['stop']
    if not valid or halted or (typ in ('add','complete') and dd<=-.10):
     if decision_audit is not None:decision_audit.append(dict(date=str(date.date()),symbol=n,event='rejected',order_type=typ,reason='revalidation_or_halt',valid=bool(valid),halted=halted,drawdown=float(dd)))
     del pending[n];continue
    if typ=='entry' and sum(shares[k]>0 for k in names)>=max_positions:
     if decision_audit is not None:decision_audit.append(dict(date=str(date.date()),symbol=n,event='rejected',order_type=typ,reason='position_slots',limit=max_positions,holders=[k for k in names if shares[k]>0]))
     del pending[n];continue
    distance=(adjopen-s['stop'])/f if typ=='complete' else 4*order['atr']/f
    new_risk=risk_fraction*(.5 if dd<=-.10 else 1.)
    quantity=math.floor(prev_nav*new_risk/(distance*rates[n])/lot)*lot
    if typ=='complete':quantity=math.floor(max(0,s['completion_budget']-s['committed_risk'])/(distance*rates[n])/lot)*lot
    exposure=sum(shares[k]*opens[k]*rates[k] for k in names)+sum(claim_open.values())
    sector=sum(shares[k]*opens[k]*rates[k] for k in names if assets[k]['sector']==a['sector'])+sum(v for k,v in claim_open.items() if security_claims.assets[k]['sector']==a['sector'])
    hk=sum(shares[k]*opens[k]*rates[k] for k in names if assets[k]['currency']=='HKD')+sum(claim_open.values())
    # Exposure caps limit new buying; winners may drift higher until an exit.
    room=min(.9*navopen-exposure,.35*navopen-shares[n]*unit-claim_open.get(n,0),.45*navopen-sector)
    if a['currency']=='HKD':room=min(room,.5*navopen-hk)
    # Sum distance to current stops is a planned-loss estimate, not gap protection.
    risk=sum(max(0,opens[k]*fs[k].loc[:date,'factor'].iloc[-1]+fs[k].loc[:date,'cash_adjustment'].iloc[-1]-state[k]['stop'])/fs[k].loc[:date,'factor'].iloc[-1]*shares[k]*rates[k] for k in state)
    if stop_mode=='layers':
     risk=sum(max(0,opens[k]*fs[k].loc[:date,'factor'].iloc[-1]+fs[k].loc[:date,'cash_adjustment'].iloc[-1]-v['stop'])/fs[k].loc[:date,'factor'].iloc[-1]*v['units']*rates[k] for k in state for v in state[k]['inventory'])
    risk+=sum(claim_open.values()) # Unliquidatable claims reserve their full value, not a fictitious stop.
    roomqty=max(0,(planned_risk_cap*prev_nav-risk)/(distance*rates[n]))
    if buying_risk_mode=='dual':
     current_risks={k:max(0,opens[k]*fs[k].loc[:date,'factor'].iloc[-1]+fs[k].loc[:date,'cash_adjustment'].iloc[-1]-state[k]['stop'])/fs[k].loc[:date,'factor'].iloc[-1]*shares[k]*rates[k] for k in state}
     original_risks={k:4*state[k]['entry_atr']/fs[k].loc[:date,'factor'].iloc[-1]*shares[k]*rates[k] for k in state}
     roomqty,initial_budget_risk,current_budget_risk=dual_risk_capacity(current_risks,original_risks,prev_nav,distance*rates[n],planned_risk_cap)

    delta=min(quantity,allowed,math.floor(max(0,room)/unit/lot)*lot,math.floor(roomqty/lot)*lot,
              math.floor(max(0,cash-minimum)/(unit*(1+rate))/lot)*lot)
    if decision_audit is not None:
     decision_audit.append(dict(date=str(date.date()),symbol=n,event='sizing',order_type=typ,
      units=float(delta),target_units=quantity,adv_units=allowed,exposure_units=math.floor(max(0,room)/unit/lot)*lot,
      risk_units=math.floor(roomqty/lot)*lot,cash_units=math.floor(max(0,cash-minimum)/(unit*(1+rate))/lot)*lot,
      planned_risk_before=float(risk),planned_risk_added=float(delta*distance*rates[n]),planned_risk_limit=float(planned_risk_cap*prev_nav),
      shared_stop_risk_by_symbol={k:float(max(0,opens[k]*fs[k].loc[:date,'factor'].iloc[-1]+fs[k].loc[:date,'cash_adjustment'].iloc[-1]-state[k]['stop'])/fs[k].loc[:date,'factor'].iloc[-1]*shares[k]*rates[k]) for k in state} if stop_mode=='shared' else {},
      original_atr_risk_by_symbol={k:float(4*state[k]['entry_atr']/fs[k].loc[:date,'factor'].iloc[-1]*shares[k]*rates[k]) for k in state},
      gross_room=float(.9*navopen-exposure),single_room=float(.35*navopen-shares[n]*unit),
      sector_room=float(.45*navopen-sector),hk_room=float(.5*navopen-hk),drawdown=float(dd)))
    if decision_audit is not None and buying_risk_mode=='dual':decision_audit[-1].update(initial_budget_risk_before=float(initial_budget_risk),current_stop_risk_before=float(current_budget_risk),current_stop_risk_limit=float(.10*prev_nav))
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
     if complete_initial:state[n].update(completion_budget=float(quantity*distance*rates[n]),committed_risk=0.)
    s=state[n];s['layers']+=1;s['last_add']=adjopen;s['buy_cash']+=delta*unit+fee
    if typ!='complete':s['stop']=max(s['stop'],adjopen-4*order['atr'])
    if complete_initial:
     s['committed_risk']+=delta*distance*rates[n]
     assert s['committed_risk']<=s['completion_budget']+1e-6
    if stop_mode=='layers':s.setdefault('inventory',[]).append(dict(id=s['layers'],units=float(delta),stop=float(adjopen-4*order['atr'])))
   else:
    state[n]['sell_cash']+=-delta*unit-fee
    if stop_mode=='layers':
     remaining=-delta
     for v in state[n]['inventory']:
      if order.get('exit_all',False) or v['id'] in order['layer_ids']:
       sold=min(remaining,v['units']);v['units']-=sold;remaining-=sold
     assert abs(remaining)<1e-8
   orders.append({'date':str(date.date()),'signal_date':order['signal_date'],'symbol':n,'type':typ,'units':float(delta),'raw_open':price,'fx':rates[n],'fee':fee,'campaign_id':state[n]['id']})
   if complete_initial and delta>0:
    orders[-1].update(completion_budget=state[n]['completion_budget'],committed_risk=state[n]['committed_risk'],
     adjusted_open=float(adjopen),stop=float(state[n]['stop']),factor=float(f))
   if shares[n]==0:
    s=state.pop(n);s.update(symbol=n,exit_date=str(date.date()),pnl=s['sell_cash']+s['dividend_claims']-s['buy_cash'])
    completed.append(s)
   layer_exit_done=stop_mode=='layers' and typ=='exit' and shares[n]>0 and not order.get('exit_all',False) and all(v['units']==0 for v in state[n]['inventory'] if v['id'] in order['layer_ids'])
   if typ!='exit' or shares[n]==0 or layer_exit_done:del pending[n]
  if stop_mode=='layers':
   for n,s in state.items():assert abs(sum(v['units'] for v in s['inventory'])-shares[n])<1e-8
  if cash<-.001 or min(shares.values())<0:raise AssertionError('Unfunded position')
  nav=cash+due+sum(shares[n]*float(closes.loc[date,n])*rates[n] for n in names)+sum(claim_close.values())
  peak=max(peak,nav);risk_peak=max(risk_peak,nav)
  logs.append({'date':date,'nav':nav/initial,'return_daily':nav/prev_nav-1,'drawdown':nav/peak-1,'cash':cash,'fees':fees,
               **{'w_'+n:shares[n]*float(closes.loc[date,n])*rates[n]/nav for n in names}})
  if security_claims is not None:logs[-1].update(security_claim_value=sum(claim_close.values()),claim_dividend_receivable=claim_due,claim_dividend_cash_paid=security_claims.cash_paid)
  prev_nav=nav
 path=pd.DataFrame(logs).set_index('date');r=path.return_daily;years=(path.index[-1]-path.index[0]).days/365.25
 metrics={'cagr':float(path.nav.iloc[-1]**(1/years)-1),'total_return':float(path.nav.iloc[-1]-1),'max_drawdown':float(path.drawdown.min()),
          'fees':float(path.fees.sum()),'orders':len(orders),'closed_campaigns':len(completed),'open_campaigns':len(state),
          'best252_return':float(((1+r).rolling(252).apply(np.prod,raw=True)-1).max()),
          'average_cash_weight':float((path.cash/(path.nav*initial)).mean())}
 return metrics,path,orders,completed,state
