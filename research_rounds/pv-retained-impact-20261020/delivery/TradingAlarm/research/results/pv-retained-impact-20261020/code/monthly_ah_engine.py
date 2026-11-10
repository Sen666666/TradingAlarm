"""Monthly trend account for CNY/HKD inventory and optional segregated claims."""
import math
from collections import defaultdict
import pandas as pd
from portfolio_data import fx_series
from campaign_engine import dividend_local_value
from multihorizon_engine import trend_scores


def allocation_weights(assets,allocation):
    cap=.9/len(assets)
    if allocation=='equal_capital':return {s:pd.Series(cap,index=a['signal'].index) for s,a in assets.items()}
    if allocation!='atr_risk_cap':raise ValueError('Unknown allocation')
    weights={}
    for s,a in assets.items():
        f=a['signal'];previous=f.close.shift()
        tr=pd.concat([f.high-f.low,(f.high-previous).abs(),(f.low-previous).abs()],axis=1).max(axis=1)
        distance=2*tr.rolling(21).mean()/f.close
        weights[s]=((.04/len(assets))/distance).clip(upper=cap).where(distance.gt(0),0.).fillna(0.)
    return weights


def run(assets,start,end,policy='monthly',cost=15,fx_cost=10,delay=0,fx_override=None,security_claims=None,signals=None,cadence='monthly',allocation='equal_capital',selection=None,entry_fraction=None,initial_capital=1e6,participation=.01):
    if initial_capital<=0 or not 0<participation<=1:raise ValueError('Invalid capital or participation')
    assert policy in ('monthly','score_change')
    if cadence not in ('monthly','daily'):raise ValueError('Unknown decision cadence')
    if cadence=='daily' and policy!='score_change':raise ValueError('Daily mode requires score-change targets')
    assert all(a['currency'] in ('CNY','HKD') for a in assets.values())
    if any(a.get('in_kind') for a in assets.values()) and security_claims is None:raise ValueError('In-kind ledger required')
    names=sorted(assets);calendar=pd.DatetimeIndex(sorted(set().union(*(a['raw'].index for a in assets.values()))))
    if entry_fraction is not None:
        if selection is None or not 0<entry_fraction<=1:raise ValueError('Entry fraction requires selector and valid fraction')
        weights={s:pd.Series(entry_fraction,index=a['signal'].index) for s,a in assets.items()}
    else:weights=allocation_weights(assets,allocation)
    fx=fx_series(calendar) if fx_override is None else fx_override.reindex(calendar).ffill()
    scores={s:trend_scores(a['signal'].close,'single252') for s,a in assets.items()} if signals is None else signals
    if set(scores)!=set(assets):raise ValueError('Signal universe mismatch')
    for s,v in scores.items():
        if not v.index.equals(assets[s]['signal'].index) or not v.isin([0.,.5,1.]).all():raise ValueError('Signals must be dated registered exposure scores')
    adv={s:a['raw'].volume.rolling(20).mean()*a.get('volume_multiplier',1) for s,a in assets.items()}
    marks=pd.DataFrame({s:a['raw'].close.reindex(calendar).ffill() for s,a in assets.items()})
    split=defaultdict(list);div=defaultdict(list)
    for s,a in assets.items():
        for e in a['splits']:split[pd.Timestamp(e['date'])].append((s,e['ratio']))
        for e in a['dividends']:div[pd.Timestamp(e['ex_date'])].append((s,e))
    cash=nav=peak=float(initial_capital);qty={s:0. for s in names};receipts=[];pending={};month=None;decisions=[];orders=[];rows=[]
    for day in calendar[(calendar>=pd.Timestamp(start))&(calendar<=pd.Timestamp(end))]:
        prior=calendar[calendar<day][-1];fees=0.
        rates={s:float(fx.loc[day]) if a['currency']=='HKD' else 1. for s,a in assets.items()}
        for s,ratio in split[day]:
            qty[s]*=ratio
            if s in pending:pending[s]['target']*=ratio
        for s,e in div[day]:
            if qty[s]:receipts.append((s,qty[s],e))
        unpaid=[];due=0.
        for s,q,e in receipts:
            amount=q*dividend_local_value(assets[s],e,day)*rates[s]
            if pd.Timestamp(e['pay_date'])<=day:
                fee=amount*fx_cost/10000 if assets[s]['currency']=='HKD' else 0.
                if e.get('currency',assets[s]['currency'])!=assets[s]['currency'] and not(e.get('settlement') and day>pd.Timestamp(e['settlement']['fixing'])):fee+=amount*e.get('conversion_bps',10)/10000
                cash+=amount-fee;fees+=fee
            else:unpaid.append((s,q,e));due+=amount
        receipts=unpaid
        claim_value=claim_due=0.
        if security_claims is not None:
            paid,claim_fees=security_claims.step(day,qty,float(fx.loc[day]),fx_cost)
            cash+=paid;fees+=claim_fees
            claim_values,claim_due=security_claims.values(day,float(fx.loc[day]))
            claim_value=sum(claim_values.values())
        if cadence=='daily' or month!=day.to_period('M'):
            month=day.to_period('M');score={s:float(scores[s].loc[:prior].iloc[-1]) if len(scores[s].loc[:prior]) else 0. for s in names};targets={}
            if selection is not None:
                selected=selection(prior,dict(score),dict(qty),{s:dict(o) for s,o in pending.items()})
                if set(selected)!=set(score) or any(v not in (0.,.5,1.) or v>score[s] for s,v in selected.items()):raise ValueError('Selector can only restrict original exposures')
                score=selected
            for s in names:
                a=assets[s];lot=a['lot'];rate=float(fx.loc[prior]) if a['currency']=='HKD' else 1.
                if not math.isfinite(marks.loc[prior,s]):
                    if qty[s] or score[s]:raise ValueError('Position or signal without a prior mark')
                    targets[s]=0.
                    continue
                # Prior close is pre-split; today's known ratio converts target to today's shares.
                ratio=math.prod(r for n,r in split[day] if n==s)
                weight=float(weights[s].loc[:prior].iloc[-1])
                target=math.floor(weight*nav*score[s]/(marks.loc[prior,s]/ratio*rate)/lot)*lot
                # A registered half-to-full promotion can add or keep shares,
                # never become an unintended trim when ATR/risk weight changes.
                if decisions and decisions[-1]['scores'][s]==.5 and score[s]==1.:
                    target=max(qty[s],target)
                # A full-to-half risk reduction cannot become a buy after NAV/price drift.
                if decisions and decisions[-1]['scores'][s]==1. and score[s]==.5:
                    target=min(qty[s],target)
                if policy=='score_change' and decisions and score[s]==decisions[-1]['scores'][s]:target=qty[s]
                targets[s]=target
            new_pending={s:dict(target=targets[s],delay=delay,signal_date=str(prior.date())) for s in names if abs(targets[s]-qty[s])>1e-8}
            if cadence=='daily' and decisions:
                for s in names:
                    if score[s]==decisions[-1]['scores'][s] and s in pending:
                        new_pending[s]=pending[s];targets[s]=pending[s]['target']
            pending=new_pending
            decisions.append(dict(date=str(day.date()),scores=score,targets=targets,prior_nav=nav))
        for s in sorted(list(pending),key=lambda s:(pending[s]['target']>=qty[s],s)):
            a=assets[s];o=pending[s]
            if day not in a['raw'].index:continue
            bar=a['raw'].loc[day]
            if bar.volume<=0 or bar.high<=bar.low:continue
            if o['delay']>0:o['delay']-=1;continue
            past_adv=adv[s].loc[:prior]
            if not len(past_adv) or not math.isfinite(float(past_adv.iloc[-1])):continue
            lot=a['lot'];limit=math.floor(float(past_adv.iloc[-1])*participation/lot)*lot
            change=o['target']-qty[s];price=float(bar.open);unit=price*rates[s]
            rate=(cost+(fx_cost if a['currency']=='HKD' else 0))/10000;minimum=18*rates[s] if a['currency']=='HKD' else 5.
            if change>0:
                delta=min(math.floor(change/lot)*lot,limit,math.floor(max(0,cash-minimum)/(unit*(1+rate))/lot)*lot)
            else:
                delta=-min(-change,limit)
            if not delta:continue
            fee=max(abs(delta)*unit*rate,minimum);cash-=delta*unit+fee;fees+=fee;qty[s]+=delta
            orders.append(dict(date=str(day.date()),symbol=s,units=delta,raw_open=price,fx=rates[s],fee=fee,signal_date=o['signal_date']))
            if abs(qty[s]-o['target'])<1e-8:del pending[s]
        assert cash>=-1e-6 and min(qty.values())>=-1e-8
        market={s:qty[s]*marks.loc[day,s]*rates[s] if qty[s] else 0. for s in names};prev=nav;nav=cash+due+sum(market.values())+claim_value+claim_due;peak=max(peak,nav)
        rows.append(dict(date=day,nav=nav/initial_capital,cash=cash,fees=fees,drawdown=nav/peak-1,return_daily=nav/prev-1,**{'w_'+s:v/nav for s,v in market.items()}))
        if security_claims is not None:rows[-1].update(security_claim_value=claim_value,claim_dividend_receivable=claim_due,claim_dividend_cash_paid=security_claims.cash_paid)
    path=pd.DataFrame(rows).set_index('date')
    metrics=dict(total_return=nav/initial_capital-1,max_drawdown=float(path.drawdown.min()),fees=float(path.fees.sum()),orders=len(orders),average_cash_weight=float((path.cash/path.nav/initial_capital).mean()),max_single_weight=float(path.filter(like='w_').max().max()))
    return metrics,path,orders,decisions
