"""Raw-price long/cash ledger with dividend receivables and board lots.

Signals are external and shifted one session. Cash dividends become receivables
on ex-date for pre-open holdings, and spendable only on/after payment date.
No borrowing, shorting, interest or tax advice; costs are explicit scenarios.
"""
import math
import numpy as np
import pandas as pd

def total_return_signal_frame(raw, events):
    amounts={pd.Timestamp(e['ex_date']):float(e['amount']) for e in events}
    div=pd.Series([amounts.get(d,0.) for d in raw.index],index=raw.index)
    gross=(raw.close+div)/raw.close.shift()
    total=raw.close.iloc[0]*gross.fillna(1).cumprod()
    factors=total/raw.close
    result=raw.copy()
    for col in ['open','high','low','close']:
        result[col]=raw[col]*factors
    return result

def run_ledger(raw, target, events=(), start=None, end=None, initial=1_000_000,
               lot=500, cost_bps=15, warmup=252):
    if not target.index.equals(raw.index) or target.isna().any() or not target.between(0,1).all():
        raise ValueError('Aligned finite 0..1 target required')
    if lot<=0 or initial<=0 or cost_bps<0:
        raise ValueError('Invalid account inputs')
    event_map={}
    for e in events:
        ex,pay=pd.Timestamp(e['ex_date']),pd.Timestamp(e['pay_date'])
        if ex not in raw.index or pay<ex or float(e['amount'])<0:
            raise ValueError('Invalid dividend event')
        if ex in event_map:
            raise ValueError('Duplicate ex-date: aggregate distributions explicitly')
        event_map[ex]=(pay,float(e['amount']))
    dates=raw.index[warmup:]
    if start: dates=dates[dates>=pd.Timestamp(start)]
    if end: dates=dates[dates<=pd.Timestamp(end)]
    decision=target.shift().fillna(0)
    cash,shares,last_equity=initial,0.,initial
    receivables=[]
    result=[]
    for date in dates:
        row=raw.loc[date]
        accrued=paid=0.
        if date in event_map:
            pay,amount=event_map[date]
            accrued=shares*amount
            receivables.append((pay,accrued))
        unpaid=[]
        for pay,amount in receivables:
            if pay<=date:
                paid+=amount
                cash+=amount
            else:
                unpaid.append((pay,amount))
        receivables=unpaid
        due=sum(amount for _,amount in receivables)
        equity_open=cash+shares*row.open+due
        desired=math.floor(equity_open*float(decision.loc[date])/row.open/lot)*lot
        delta=desired-shares
        rate=cost_bps/10000
        if delta>0:
            affordable=math.floor((cash+1e-9)/(row.open*(1+rate)*lot))*lot
            delta=min(delta,affordable)
        fee=abs(delta)*row.open*rate
        cash-=delta*row.open+fee
        shares+=delta
        equity=cash+shares*row.close+due
        if cash < -1e-6 or shares<0:
            raise AssertionError('Unfunded position')
        result.append({'date':date,'nav':equity/initial,'return':equity/last_equity-1,
                       'cash':cash,'shares':shares,'receivable':due,'dividend_accrued':accrued,
                       'dividend_paid':paid,'fee':fee,'delta_shares':delta,
                       'position':shares*row.close/equity,'turnover':abs(delta)*row.open/equity_open})
        last_equity=equity
    path=pd.DataFrame(result).set_index('date')
    if len(path)<2: raise ValueError('Insufficient period')
    nav=path.nav.to_numpy()
    dd=nav/np.maximum.accumulate(np.r_[1.,nav])[1:]-1
    path['drawdown']=dd
    years=max((path.index[-1]-path.index[0]).days/365.25,1/252)
    sd=path['return'].std(ddof=1)
    metrics={'start':str(path.index[0].date()),'end':str(path.index[-1].date()),
             'cagr':float(nav[-1]**(1/years)-1),'total_return':float(nav[-1]-1),
             'max_drawdown':float(dd.min()),'sharpe':float(path['return'].mean()/sd*np.sqrt(252)) if sd else None,
             'realized_vol':float(sd*np.sqrt(252)),'average_exposure':float(path.position.mean()),
             'orders':int((path.delta_shares!=0).sum()),'fees':float(path.fee.sum()),
             'dividends_accrued':float(path.dividend_accrued.sum()),'dividends_paid':float(path.dividend_paid.sum()),
             'terminal_receivable':float(path.receivable.iloc[-1]),'cost_bps_per_side':cost_bps,'initial_capital':initial,'lot':lot}
    return metrics,path
