"""Causal raw-share, CNY-base research portfolio. No broker order routing.

Assumes pre-funded, fungible cash across venues and executable opens; observed
spread, price-limit queues, brokerage minima and settlement are not fully modeled.
"""
import math
import numpy as np
import pandas as pd
from portfolio_data import fx_series

def trend_gate(signal):
    c=signal.close; ma=c.rolling(200).mean(); mom=c.pct_change(63)
    entry=(c>ma)&(c.shift()>ma.shift())&(mom>0)
    leave=(c<ma)&(c.shift()<ma.shift())
    held=False; states=[]
    for buy,sell in zip(entry,leave):
        if held and sell: held=False
        elif not held and buy: held=True
        states.append(held)
    return pd.Series(states,index=c.index)

def clusters(corr,threshold=.75):
    remaining=set(corr.columns); out=[]
    while remaining:
        group={min(remaining)}; frontier=list(group); remaining-=group
        while frontier:
            current=frontier.pop()
            near={x for x in remaining if corr.loc[current,x]>=threshold}
            remaining-=near;group|=near;frontier+=sorted(near)
        out.append(sorted(group))
    return out

def allocate(returns,eligible,assets,passive=False):
    names=sorted(n for n in assets if eligible.get(n,False) or passive)
    weights=pd.Series(0.,index=sorted(assets))
    if not names or len(returns)<60: return weights,[]
    data=returns[names].tail(60)
    if data.isna().any().any(): return weights,[]
    vols=(data.std()*np.sqrt(252)).clip(lower=.05)
    initial=1/vols; initial/=initial.sum()
    weights.loc[names]=initial.clip(upper=.20)
    for group,cap in [({n for n in names if assets[n]['kind']=='equity'},.70),
                      ({n for n in names if assets[n]['currency']=='HKD'},.30)]:
        total=weights.loc[sorted(group)].sum()
        if total>cap: weights.loc[sorted(group)]*=cap/total
    corr=data.corr().fillna(0.)
    groups=clusters(corr)
    for group in groups:
        total=weights.loc[group].sum()
        if total>.35: weights.loc[group]*=.35/total
    cov=data.cov().to_numpy()*252
    cov=.5*cov+.5*np.diag(np.diag(cov))
    w=weights.loc[names].to_numpy()
    estimated=float(np.sqrt(max(0,w@cov@w)))
    if estimated>.12: weights*=.12/estimated
    return weights,groups

def run_portfolio(assets,start='2022-01-01',cost_bps=15,fx_bps=10,
                  passive=False,guard=True,extra_delay=0,initial=1_000_000):
    names=sorted(assets)
    calendar=assets[names[0]]['raw'].index
    joint=calendar
    for a in assets.values():
        calendar=calendar.union(a['raw'].index)
        joint=joint.intersection(a['raw'].index)
    calendar=calendar.sort_values(); fx=fx_series(calendar)
    close=pd.DataFrame({n:assets[n]['raw'].close.reindex(calendar).ffill() for n in names})
    gates=pd.DataFrame({n:trend_gate(assets[n]['signal']).reindex(calendar).ffill().fillna(False) for n in names})
    total=pd.DataFrame({n:assets[n]['signal'].close.reindex(joint) for n in names})
    for n in names:
        if assets[n]['currency']=='HKD': total[n]*=fx.reindex(joint)
    returns=total.pct_change(fill_method=None).dropna()
    split_map={n:{pd.Timestamp(e['date']):e['ratio'] for e in assets[n]['splits']} for n in names}
    div_map={n:{pd.Timestamp(e['ex_date']):e for e in assets[n]['dividends']} for n in names}
    cash=initial; shares=pd.Series(0.,index=names); receivables=[]
    desired=pd.Series(0.,index=names); queue={}; logs=[]; trades=[]; decisions=[]
    last_week=None; peak=initial; global_peak=initial; prev_equity=initial
    mode='normal'; cooldown=0; group_cache=[]
    for date in calendar[calendar>=pd.Timestamp(start)]:
        previous=calendar[calendar.get_loc(date)-1]
        rates=pd.Series({n:float(fx.loc[date]) if assets[n]['currency']=='HKD' else 1. for n in names})
        opens=pd.Series({n:float(assets[n]['raw'].loc[date,'open']) if date in assets[n]['raw'].index else float(close.loc[previous,n]) for n in names})
        fee_day=paid=accrued=0.
        for n in names:
            if date in split_map[n]: shares[n]*=split_map[n][date]
            if date in div_map[n]:
                e=div_map[n][date]; amount=shares[n]*e['amount']
                receivables.append((n,pd.Timestamp(e['pay_date']),amount)); accrued+=amount*rates[n]
        unpaid=[]
        for n,pay,amount in receivables:
            if pay<=date:
                value=amount*rates[n]; fee=value*fx_bps/10000 if assets[n]['currency']=='HKD' else 0
                cash+=value-fee;fee_day+=fee;paid+=value
            else: unpaid.append((n,pay,amount))
        receivables=unpaid
        due=sum(amount*rates[n] for n,_,amount in receivables)
        nav_open=cash+float((shares*opens*rates).sum())+due
        iso=date.isocalendar(); week=(iso.year,iso.week)
        weekly=date in joint and week!=last_week
        active=gates.loc[previous].to_dict()
        risk_drawdown=prev_equity/peak-1
        before_mode=mode
        if guard:
            if mode!='cash' and risk_drawdown<=-.20: mode='cash';cooldown=0
            elif mode=='normal' and risk_drawdown<=-.15: mode='half'
            elif mode=='half' and prev_equity>=peak: mode='normal'
            if mode=='cash' and date in joint:
                cooldown=cooldown+1 if (shares==0).all() else 0
                if cooldown>20 and weekly:
                    mode='normal';peak=prev_equity
        if weekly:
            last_week=week
            desired,group_cache=allocate(returns.loc[:previous],active,assets,passive)
            if mode=='half': desired*=.5
            if mode=='cash': desired*=0
            decisions.append(dict(date=str(date.date()),signal_cutoff=str(previous.date()),
                                  mode=mode,weights=desired.to_dict(),clusters=group_cache))
            for n in names: queue[n]=extra_delay
        else:
            for n in names:
                if not passive and not active[n] and (shares[n]>0 or desired[n]>0):
                    desired[n]=0.;queue[n]=min(queue.get(n,extra_delay),extra_delay)
            if mode!=before_mode:
                if mode=='cash': desired*=0
                elif mode=='half': desired*=.5
                for n in names: queue[n]=extra_delay
        orders={}
        for n in list(queue):
            if date not in assets[n]['raw'].index: continue
            if queue[n]>0: queue[n]-=1;continue
            lot=assets[n]['lot']; unit=opens[n]*rates[n]
            want=math.floor(nav_open*desired[n]/unit/lot)*lot
            orders[n]=want-shares[n];del queue[n]
        # Sales precede purchases. Cash cannot become negative; no implicit leverage.
        for n in sorted(orders,key=lambda n:(orders[n]>0,n)):
            delta=orders[n]; unit=opens[n]*rates[n]
            rate=(cost_bps+(fx_bps if assets[n]['currency']=='HKD' else 0))/10000
            if delta>0:
                lot=assets[n]['lot']
                delta=min(delta,math.floor(max(0,cash)/(unit*(1+rate)*lot))*lot)
            if not delta: continue
            fee=abs(delta)*unit*rate
            cash-=delta*unit+fee;shares[n]+=delta;fee_day+=fee
            trades.append(dict(date=str(date.date()),symbol=n,units=float(delta),local_open=float(opens[n]),fx=float(rates[n]),fee=float(fee)))
        if cash<-.001 or (shares<0).any(): raise AssertionError('Unfunded holdings')
        values=shares*close.loc[date]*rates
        equity=cash+values.sum()+due
        peak=max(peak,equity);global_peak=max(global_peak,equity)
        logs.append(dict(date=date,nav=equity/initial,return_daily=equity/prev_equity-1,
                         drawdown=equity/global_peak-1,cash=cash,receivable=due,
                         fees=fee_day,dividend_paid=paid,dividend_accrued=accrued,mode=mode,
                         **{f'w_{n}':values[n]/equity for n in names}))
        prev_equity=equity
    path=pd.DataFrame(logs).set_index('date')
    r=path.return_daily; years=(path.index[-1]-path.index[0]).days/365.25
    metrics=dict(start=str(path.index[0].date()),end=str(path.index[-1].date()),
                 cagr=float(path.nav.iloc[-1]**(1/years)-1),total_return=float(path.nav.iloc[-1]-1),
                 max_drawdown=float(path.drawdown.min()),realized_vol=float(r.std()*np.sqrt(252)),
                 sharpe=float(r.mean()/r.std()*np.sqrt(252)) if r.std() else None,
                 fees=float(path.fees.sum()),orders=len(trades),
                 average_cash_weight=float((path.cash/(path.nav*initial)).mean()),
                 total_dividend_paid=float(path.dividend_paid.sum()),
                 cost_bps=cost_bps,fx_bps=fx_bps,extra_delay=extra_delay,guard=guard,passive=passive)
    return metrics,path,trades,decisions
