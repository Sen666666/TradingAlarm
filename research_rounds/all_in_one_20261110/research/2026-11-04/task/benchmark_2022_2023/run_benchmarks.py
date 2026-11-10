"""Frozen two ETF diagnostic benchmarks, raw daily execution proxy only."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D,ROUND_HALF_UP
import copy,hashlib,json,math
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent;I=O/'inputs';INITIAL=D(1000000);RATE=D('.0015');MINIMUM=D(5);LOT=100
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
def number(x):return D(str(x))
def fees(gross):return max(MINIMUM,gross*RATE) if gross else D(0)
def floorlot(q):return int(q)//LOT*LOT
def affordable(budget,price):
    q=floorlot(budget/price)
    while q and D(q)*price+fees(D(q)*price)>budget:q-=LOT
    return q
def metric(frame):
    nav=frame.NAV.astype(float);peak=np.maximum.accumulate(np.r_[1e6,nav])[1:];dd=1-nav/peak
    result=dict(initial=1e6,terminal_NAV=float(nav.iloc[-1]),return_pct=float((nav.iloc[-1]/1e6-1)*100),max_DD_pct=float(dd.max()*100),
        DD_day=str(frame.date.iloc[int(np.argmax(dd))]),fees=float(frame.fee.astype(float).sum()) if 'fee' in frame else 0,
        dividends_accrued=float(frame.dividend_accrued.astype(float).sum()) if 'dividend_accrued' in frame else 0,
        dividends_paid=float(frame.dividend_paid.astype(float).sum()) if 'dividend_paid' in frame else 0,
        mean_exposure_pct=float((frame.market_value.astype(float)/nav).mean()*100) if 'market_value' in frame else None)
    if 'same_quantity_cost_before_NAV' in frame:
        result['same_quantity_cost_before_NAV']=float(frame.same_quantity_cost_before_NAV.iloc[-1])
        result['same_quantity_cost_before_return_pct']=(result['same_quantity_cost_before_NAV']/1e6-1)*100
    return result
def simulate(history,calendar,actions,policy):
    cash=INITIAL;shares=0;lots=[];claims=[];pending=None;previous_on=False;rows=[];fills=[];orders=[];signals=[];orderid=0
    byex={e['ex_date']:e for e in actions['dividends']};dates=[str(d.date()) for d in calendar]
    previous_cash=cash;previous_shares=0;previous_claim=D(0);previous_nav=INITIAL;globalpeak=INITIAL;cumulative_fee=D(0)
    def create(side,day,nav):
        nonlocal orderid
        orderid+=1;budget=nav*(D('.90') if policy=='MA63_90' else D(1))
        value=dict(id=f'{policy}-{orderid}',side=side,signal_day=day,cash_budget=budget,
            remaining=None if side=='buy' else shares,cumulative_gross=D(0),fee_paid=D(0))
        orders.append(dict(kind='create',at=day,**value));return value
    for day in dates:
        date=pd.Timestamp(day);bar=history.loc[date];op=number(bar.open);cl=number(bar.close)
        accrued=paid=buygross=sellgross=fee=D(0);bought=sold=0;reason='';start_shares=shares
        # Ex entitlement precedes this open; an ex-day first buy has no claim.
        if day in byex:
            e=byex[day];amount=number(e['amount'])*shares
            if amount:claims.append(dict(ex=day,pay=e['pay_date'],amount=amount));accrued+=amount
        retained=[]
        for e in claims:
            if e['pay']<=day:cash+=e['amount'];paid+=e['amount']
            else:retained.append(e)
        claims=retained;claim=sum((e['amount'] for e in claims),D(0))
        capacity=floorlot(number(bar.adv20_prior_shares)*D('.01'))
        prior=history.loc[history.index<date].iloc[-1];reference=number(prior.close)-number(byex.get(day,{}).get('amount',0))
        upper=(reference*D('1.1')).quantize(D('.001'),rounding=ROUND_HALF_UP)
        lower=(reference*D('.9')).quantize(D('.001'),rounding=ROUND_HALF_UP)
        assert lower-D('.0005')<=op<=upper+D('.0005'),('open outside indicative band; stop',day,op,lower,upper)
        if pending is not None:
            assert pending['signal_day']<day,'same-close execution forbidden'
            side=pending['side'];reason='no_capacity' if not capacity else ''
            if side=='buy' and op>=upper-D('.0005'):reason='indicative_upper_queue_unknown'
            if side=='sell' and op<=lower+D('.0005'):reason='indicative_lower_queue_unknown'
            if not reason:
                if side=='buy':
                    if pending['remaining'] is None:pending['remaining']=affordable(min(cash,pending['cash_budget']),op)
                    q=min(pending['remaining'],capacity)
                    while q:
                        gross=D(q)*op;incremental=fees(pending['cumulative_gross']+gross)-pending['fee_paid']
                        if gross+incremental<=cash and pending['cumulative_gross']+gross+pending['fee_paid']+incremental<=pending['cash_budget']:break
                        q-=LOT
                    if q:
                        cash-=gross+incremental;shares+=q;buygross=gross;bought=q;fee=incremental
                        lots.append(dict(day=day,quantity=q));pending['cumulative_gross']+=gross;pending['fee_paid']+=incremental
                    else:reason='cash_or_original_budget_minimum'
                else:
                    sellable=sum(l['quantity'] for l in lots if l['day']<day)
                    q=min(pending['remaining'],capacity,sellable);q=floorlot(q)
                    if q:
                        gross=D(q)*op;incremental=fees(pending['cumulative_gross']+gross)-pending['fee_paid']
                        cash+=gross-incremental;shares-=q;sellgross=gross;sold=q;fee=incremental
                        left=q
                        for lot in lots:
                            if lot['day']>=day:continue
                            take=min(left,lot['quantity']);lot['quantity']-=take;left-=take
                        assert left==0
                        pending['cumulative_gross']+=gross;pending['fee_paid']+=incremental
                    else:reason='T1_or_capacity'
                if q:
                    assert q%100==0 and q<=capacity and cash>=0
                    pending['remaining']-=q
                    fills.append(dict(day=day,order=pending['id'],side=side,signal_day=pending['signal_day'],quantity=q,raw_open=str(op),price=str(op),gross=str(gross),fee=str(fee),capacity_shares=capacity,
                        participation_of_prior_ADV=float(D(q)/number(bar.adv20_prior_shares)),upper_distance_bps=float((upper/op-1)*10000),lower_distance_bps=float((op/lower-1)*10000),
                        limit_source='indicative_rule_proxy_not_dated_exchange_state'))
                    if pending['remaining']==0:orders.append(dict(kind='complete',at=day,**copy.deepcopy(pending)));pending=None
                elif pending['remaining']==0:orders.append(dict(kind='minimum_not_funded',at=day,**copy.deepcopy(pending)));pending=None
            if pending is not None and reason:orders.append(dict(kind='wait',at=day,reason=reason,**copy.deepcopy(pending)))
        nav=cash+D(shares)*cl+claim;globalpeak=max(globalpeak,nav);cumulative_fee+=fee
        assert cash==previous_cash+paid-buygross+sellgross-fee
        assert shares==previous_shares+bought-sold==sum(l['quantity'] for l in lots)
        assert claim==previous_claim+accrued-paid and nav==cash+D(shares)*cl+claim and cash>=0 and shares>=0
        on=bool(bar['on']);signals.append(dict(day=day,signal_close=float(bar.signal_close),MA63=float(bar.ma63),on=on,prior_on=previous_on))
        if policy=='BUY_HOLD':
            if day==dates[0]:pending=create('buy',day,nav)
        else:
            if not on:
                if pending is not None and pending['side']=='buy':orders.append(dict(kind='cancel_OFF',at=day,**copy.deepcopy(pending)));pending=None
                if shares>0 and pending is None:pending=create('sell',day,nav)
            elif not previous_on and shares==0 and pending is None:pending=create('buy',day,nav)
        rows.append(dict(date=day,NAV=str(nav),cash=str(cash),shares=shares,raw_open=str(op),raw_close=str(cl),market_value=str(D(shares)*cl),
            dividend_receivable=str(claim),dividend_accrued=str(accrued),dividend_paid=str(paid),fee=str(fee),buy_gross=str(buygross),sell_gross=str(sellgross),bought=bought,sold=sold,
            return_daily=str(nav/previous_nav-1),drawdown=str(1-nav/globalpeak),same_quantity_cost_before_NAV=str(nav+cumulative_fee),cumulative_fee=str(cumulative_fee),on=on,indicative_upper=str(upper),indicative_lower=str(lower),capacity_shares=capacity,
            pending_side=pending['side'] if pending else '',pending_quantity=pending['remaining'] if pending else 0,execution_verified=False))
        previous_on=on;previous_cash=cash;previous_shares=shares;previous_claim=claim;previous_nav=nav
    return pd.DataFrame(rows),fills,orders,signals,dict(cash=str(cash),shares=shares,receivables=claims,pending=pending,lots=lots)
def main():
    assert not(O/'RESULTS.json').exists(),'no silent rerun of completed benchmark'
    inp=json.loads((O/'INPUT_FREEZE.json').read_text())
    for p,h in dict(inp['sources'],**inp['inputs']).items():assert sha(p)==h,('input/source drift',p)
    sourcefreeze={str(Path(__file__)):sha(__file__),str(O/'INPUT_FREEZE.json'):sha(O/'INPUT_FREEZE.json'),str(O/'PROTOCOL.txt'):sha(O/'PROTOCOL.txt'),str(O/'COST_BRIDGE_ADDENDUM.txt'):sha(O/'COST_BRIDGE_ADDENDUM.txt')}
    save(O/'RUN_FREEZE.json',dict(at_UTC=datetime.now(timezone.utc).isoformat(),before_account_computation=True,sources=sourcefreeze))
    history=pd.read_csv(I/'510300_history.csv',index_col='date',parse_dates=True)
    assert history['on'].dtype==bool and history.index.is_unique
    calendar=pd.DatetimeIndex(pd.read_csv(I/'calendar.csv').date);actions=json.loads((I/'510300_actions.json').read_text())
    results={};(O/'daily').mkdir(exist_ok=True);(O/'logs').mkdir(exist_ok=True)
    for name in ('BUY_HOLD','MA63_90'):
        daily,fills,orders,signals,last=simulate(history,calendar,actions,name)
        daily.to_csv(O/'daily'/f'{name}.csv',index=False)
        save(O/'logs'/f'{name}_fills.json',fills);save(O/'logs'/f'{name}_orders.json',orders);save(O/'logs'/f'{name}_signals.json',signals);save(O/'logs'/f'{name}_terminal.json',last)
        results[name]=dict(metric(daily),fills=len(fills),execution_verified=False,execution_basis='raw open daily proxy; historical dated limit/halt state unavailable')
    index=pd.read_csv(I/'HS300_daily.csv');base=number(index.iloc[1].open);units=INITIAL/base;indexrows=[]
    for i,row in index.iterrows():
        value=INITIAL if i==0 else units*number(row.close)
        indexrows.append(dict(date=row.date,NAV=str(value),index_open=row.open,index_close=row.close,synthetic_units='0' if i==0 else str(units),cash='1000000' if i==0 else '0',market_value=str(0 if i==0 else value),fee='0',reference_only=True))
    indexpath=pd.DataFrame(indexrows);indexpath.to_csv(O/'daily/HS300_PRICE_INDEX.csv',index=False);results['HS300_PRICE_INDEX']=dict(metric(indexpath),reference_only=True)
    cash=pd.DataFrame(dict(date=index.date,NAV='1000000',cash='1000000',market_value='0',fee='0'));cash.to_csv(O/'daily/CASH.csv',index=False);results['CASH']=dict(metric(cash),reference_only=True)
    # No year reset:2023 return is measured against actual2022 terminal NAV.
    periods=[]
    for name in results:
        d=pd.read_csv(O/'daily'/f'{name}.csv');d['date']=pd.to_datetime(d.date);nav=d.NAV.astype(float)
        for freq in ('Y','Q','M'):
            labels=d.date.dt.to_period(freq)
            for label,ix in d.groupby(labels).groups.items():
                pos=list(ix);first=pos[0];basevalue=1e6 if first==0 else float(nav.iloc[first-1]);last=float(nav.iloc[pos[-1]])
                localpeak=np.maximum.accumulate(np.r_[basevalue,nav.iloc[pos]])[1:]
                periods.append(dict(benchmark=name,frequency=freq,period=str(label),start=str(d.date.iloc[first].date()),end=str(d.date.iloc[pos[-1]].date()),starting_NAV=basevalue,ending_NAV=last,return_pct=(last/basevalue-1)*100,period_DD_pct=float(np.max(1-nav.iloc[pos].to_numpy()/localpeak)*100)))
    pd.DataFrame(periods).to_csv(O/'PERIODS.csv',index=False)
    for p,h in sourcefreeze.items():assert sha(p)==h
    save(O/'RESULTS.json',dict(scope='new diagnostic benchmarks only, not No60 candidate paths',dates=['2022-01-04','2023-12-29'],daily_count=484,first_execution='2022-01-05 OPEN at earliest',initial_cash=1000000,no_annual_reset=True,results=results,independent_audit='pending'))
    print(json.dumps(results,ensure_ascii=False,indent=2),flush=True)
if __name__=='__main__':main()
