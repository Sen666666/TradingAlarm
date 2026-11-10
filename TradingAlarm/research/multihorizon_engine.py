"""Monthly long-only price trend comparator, actual USD inventory and receipts."""
import math
from collections import defaultdict
import numpy as np
import pandas as pd


def trend_scores(close,mode):
    if mode not in ('ensemble','single252'):raise ValueError(mode)
    signals=pd.concat({h:close.pct_change(h) for h in (21,63,252)},axis=1)
    score=signals.gt(0).mean(axis=1) if mode=='ensemble' else signals[252].gt(0).astype(float)
    return score.where(signals.notna().all(axis=1),0.)


def run(assets,start,end,mode,cost=15,delay=0,rebalance='monthly'):
    if rebalance not in ('monthly','score_change'):raise ValueError(rebalance)
    names=sorted(assets);calendar=assets[names[0]]['raw'].index
    for a in assets.values():
        assert a['currency']=='USD' and not a['splits'] and a['lot']==1
        calendar=calendar.intersection(a['raw'].index)
    score={s:trend_scores(a['signal'].close,mode) for s,a in assets.items()}
    adv={s:a['raw'].volume.shift().rolling(20).mean()*.01 for s,a in assets.items()}
    ev=defaultdict(list)
    for s,a in assets.items():
        for e in a['dividends']:ev[pd.Timestamp(e['ex_date'])].append((s,e))
    cash=1e6;qty={s:0 for s in names};receipts=[];pending=None;month=None;prev_nav=1e6;peak=1e6;cid=0
    path=[];orders=[];state={};closed=[];decisions=[]
    for day in calendar[(calendar>=pd.Timestamp(start))&(calendar<=pd.Timestamp(end))]:
        prior=calendar[calendar<day][-1];fees=0.
        for s,e in ev[day]:
            if qty[s]:
                amount=qty[s]*e['amount'];receipts.append((pd.Timestamp(e['pay_date']),amount));state[s]['dividend_claims']+=amount
        cash+=sum(amount for pay,amount in receipts if pay<=day)
        receipts=[(pay,amount) for pay,amount in receipts if pay>day];due=sum(v for _,v in receipts)
        if month!=day.to_period('M'):
            month=day.to_period('M')
            target={s:math.floor(.9/len(names)*prev_nav*float(score[s].loc[prior])/float(assets[s]['raw'].loc[prior,'close'])) for s in names}
            if rebalance=='score_change' and decisions:
                target={s:qty[s] if float(score[s].loc[prior])==decisions[-1]['scores'][s] else target[s] for s in names}
            pending=dict(target=target,remaining_delay=delay,signal_date=str(prior.date()))
            decisions.append(dict(date=str(day.date()),prior_nav=prev_nav,scores={s:float(score[s].loc[prior]) for s in names},target=target))
        if pending is not None:
            if pending['remaining_delay']>0:pending['remaining_delay']-=1
            else:
                # Sell first, deterministic symbol order; cash constraint always applies.
                ranked=sorted(names,key=lambda s:(pending['target'][s]>=qty[s],s))
                for s in ranked:
                    a=assets[s];price=float(a['raw'].loc[day,'open']);target=pending['target'][s]
                    change=target-qty[s];limit=math.floor(adv[s].loc[day])
                    delta=int(np.sign(change))*min(abs(change),limit)
                    if delta>0:delta=min(delta,math.floor(cash/(price*(1+cost/10000))))
                    if not delta:continue
                    fee=abs(delta)*price*cost/10000
                    if qty[s]==0 and delta>0:
                        cid+=1;state[s]=dict(id=cid,symbol=s,entry_date=str(day.date()),entry_nav=prev_nav,buy_cash=0.,sell_cash=0.,dividend_claims=0.)
                    cash-=delta*price+fee;fees+=fee;qty[s]+=delta
                    if delta>0:state[s]['buy_cash']+=delta*price+fee
                    else:state[s]['sell_cash']+=-delta*price-fee
                    orders.append(dict(date=str(day.date()),symbol=s,type='buy' if delta>0 else 'sell',units=float(delta),raw_open=price,fx=1.,fee=fee,campaign_id=state[s]['id'],signal_date=pending['signal_date']))
                    if qty[s]==0:
                        c=state.pop(s);c.update(exit_date=str(day.date()),pnl=c['sell_cash']+c['dividend_claims']-c['buy_cash']);closed.append(c)
                if all(qty[s]==pending['target'][s] for s in names):pending=None
        assert cash>=-1e-6 and min(qty.values())>=0
        market={s:qty[s]*float(assets[s]['raw'].loc[day,'close']) for s in names};nav=cash+due+sum(market.values());peak=max(peak,nav)
        path.append(dict(date=day,nav=nav/1e6,cash=cash,fees=fees,drawdown=nav/peak-1,return_daily=nav/prev_nav-1,**{'w_'+s:market[s]/nav for s in names}));prev_nav=nav
    frame=pd.DataFrame(path).set_index('date')
    metrics=dict(total_return=float(frame.nav.iloc[-1]-1),max_drawdown=float(frame.drawdown.min()),orders=len(orders),fees=float(frame.fees.sum()),
                 average_cash_weight=float((frame.cash/(frame.nav*1e6)).mean()),best252_return=float((frame.nav/frame.nav.shift(252)-1).max()),
                 closed_campaigns=len(closed),open_campaigns=len(state))
    return metrics,frame,orders,closed,state,decisions
