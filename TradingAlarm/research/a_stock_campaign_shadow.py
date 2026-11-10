"""Finite-capital synthetic-price campaign simulation, NOT a raw-share account."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import ROOT, SOURCE, grouped
from ths_signal_adjustment import signal_frame

OUT=ROOT/'results/a-stock-campaign-shadow'


def build_bundle():
    """Same frozen source/feature parity as independent campaign experiments."""
    paths=ROOT/'data/stock-features'
    coverage=json.loads((ROOT/'results/a-stock-zero-range-stress/coverage.json').read_text())
    names=sorted(r['symbol'] for r in coverage['records'])
    assert len(names)==len(set(names))
    columns=['symbol','date','signal_close','observed_bar','positive_volume','atr20',
             'breakout55','sma200','exit_signal','momentum126_21']
    pf=pq.ParquetFile(paths/'local-features.parquet')
    dates=set()
    for batch in pf.iter_batches(columns=['date']):
        dates.update(pd.to_datetime(batch.column(0).to_pandas()))
    dates=pd.DatetimeIndex(sorted(dates))
    dates=dates[(dates>=pd.Timestamp('2021-12-31')) & (dates<=pd.Timestamp(coverage['cutoff']))]
    shape=(len(dates),len(names)); nameindex={n:i for i,n in enumerate(names)}
    bundle={k:np.full(shape,np.nan,dtype=np.float64) for k in ('close','open','atr','momentum')}
    bundle.update({k:np.zeros(shape,dtype=bool) for k in ('active','execute','exit','entry','gate')})
    ranked=pd.read_parquet(ROOT/'results/a-stock-opportunity-ranking/all-candidates.parquet')
    gates={s:pd.Series(g.atr_fraction_quintile.eq(1).fillna(False).to_numpy(dtype=bool),
                       index=pd.DatetimeIndex(g.date)) for s,g in ranked.groupby('symbol')}

    def install(symbol,f,raw,opens):
        j=nameindex[symbol];loc=dates.get_indexer(pd.DatetimeIndex(f.date));keep=loc>=0
        f=f.loc[keep].copy();ix=loc[keep];fd=pd.DatetimeIndex(f.date)
        bundle['close'][ix,j]=f.signal_close.to_numpy()
        bundle['open'][ix,j]=opens.reindex(fd).to_numpy()
        bundle['atr'][ix,j]=f.atr20.to_numpy()
        bundle['momentum'][ix,j]=f.momentum126_21.to_numpy()
        active=(f.observed_bar & f.positive_volume).to_numpy()
        bundle['active'][ix,j]=active
        observed=raw.reindex(fd)
        bundle['execute'][ix,j]=active & ~np.isclose(observed.high,observed.low,rtol=1e-10,atol=1e-10) & np.isfinite(bundle['open'][ix,j]) & (bundle['open'][ix,j]>0)
        bundle['exit'][ix,j]=f.exit_signal.to_numpy(dtype=bool)
        bundle['entry'][ix,j]=(f.signal_close.gt(f.breakout55)&np.isfinite(f.sma200)&np.isfinite(f.atr20)&f.atr20.gt(0)).to_numpy()
        gate=gates.get(symbol,pd.Series(dtype=bool))
        bundle['gate'][ix,j]=gate.reindex(fd,fill_value=False).to_numpy(dtype=bool)

    it=iter(grouped(pq.ParquetFile(SOURCE),['symbol','trade_date','open','high','low','close','reference_adjustment_factor']))
    current_symbol,current=next(it);count=0
    for symbol,f in grouped(pf,columns):
        while current_symbol<symbol:current_symbol,current=next(it)
        assert current_symbol==symbol
        raw=current.set_index('trade_date')
        check=(raw.close*raw.reference_adjustment_factor).reindex(pd.DatetimeIndex(f.date)).to_numpy()
        obs=f.observed_bar.to_numpy()
        assert np.allclose(check[obs],f.signal_close.to_numpy()[obs],rtol=1e-10,atol=1e-8)
        install(symbol,f,raw,raw.open*raw.reference_adjustment_factor);count+=1
        if count%1000==0:print('bundle symbols',count,flush=True)
    for symbol,f in grouped(pq.ParquetFile(paths/'ths-retired-features.parquet'),columns):
        code,market=symbol.split('.');name=('USHD' if market=='SH' else 'USZD')+code+'.json'
        raw=signal_frame(json.loads((ROOT/'data/ths-raw'/name).read_text()),json.loads((ROOT/'data/ths-rights'/name).read_text()))
        obs=f.observed_bar.to_numpy()
        check=raw.signal_close.reindex(pd.DatetimeIndex(f.date)).to_numpy()
        assert np.allclose(check[obs],f.signal_close.to_numpy()[obs],rtol=1e-10,atol=1e-8)
        install(symbol,f,raw,raw.signal_open);count+=1
    assert count==len(names)
    bundle['dates']=dates.to_numpy();bundle['names']=np.array(names)
    return bundle


def simulate(b,ranking='lowvol',gate=False,cost_bps=15,initial=1_000_000.,max_positions=8,guard=True,full_entry_risk=False,decision_trace=None,trace_symbols=None,trace_dates=None,complete_initial=False):
    """Use prior close for decisions; opens only for fills and exposure sizing."""
    if complete_initial and full_entry_risk:raise ValueError('Completion requires the partial-entry control')
    dates=pd.DatetimeIndex(b['dates']);names=b['names'];cash=float(initial)
    held={};marks=np.full(len(names),np.nan);markdates=np.full(len(names),-1,dtype=int)
    orders=[];completed=[];path=[];prev_nav=initial;risk_peak=initial;global_peak=initial;cooldown=0
    skipped=dict(slots=0,execution=0,capital_or_risk=0);fees=0.
    def trace(i,j,event,**details):
        if decision_trace is None:return
        date=str(dates[i].date());symbol=str(names[j])
        if trace_symbols is not None and symbol not in trace_symbols:return
        if trace_dates is not None and date not in trace_dates:return
        decision_trace.append(dict(date=date,symbol=symbol,event=event,**details))
    for i in range(len(dates)):
        observed=b['active'][i] & np.isfinite(b['close'][i])
        if i==0:
            marks[observed]=b['close'][i,observed];markdates[observed]=i
            continue
        dd=prev_nav/risk_peak-1
        if guard and cooldown==0 and dd<=-.16:cooldown=20
        halted=cooldown>0
        if halted and not held:
            cooldown-=1
            if cooldown==0:risk_peak=prev_nav
        # Last observed close persists for stale securities; never creates cash.
        openmarks=marks.copy()
        validopen=b['active'][i] & np.isfinite(b['open'][i]) & (b['open'][i]>0)
        openmarks[validopen]=b['open'][i,validopen]
        sold=set()
        for j,p in list(held.items()):
            if halted or marks[j]<p['stop'] or b['exit'][i-1,j]:p['pending']=True
            if not p['pending'] or not b['execute'][i,j]:continue
            price=b['open'][i,j];value=p['quantity']*price;fee=value*cost_bps/10000
            cash+=value-fee;fees+=fee
            completed.append(dict(symbol=str(names[j]),entry_date=p['entry_date'],exit_date=str(dates[i].date()),
                pnl=value-fee-p['entry_value']-p['entry_fee'],initial_risk=p['committed_risk']))
            orders.append(dict(date=str(dates[i].date()),symbol=str(names[j]),side='sell',quantity=p['quantity'],price=float(price),fee=float(fee)))
            del held[j];sold.add(j)
        navopen=cash+sum(p['quantity']*openmarks[j] for j,p in held.items())
        if not halted:
            eligible=b['entry'][i-1].copy()
            if gate:eligible &= b['gate'][i-1]
            candidates=np.flatnonzero(eligible)
            if ranking=='lowvol':
                candidates=sorted(candidates,key=lambda j:(b['atr'][i-1,j]/b['close'][i-1,j],str(names[j])))
            elif ranking=='strength':
                candidates=sorted(candidates,key=lambda j:(-b['momentum'][i-1,j] if np.isfinite(b['momentum'][i-1,j]) else np.inf,str(names[j])))
            else:raise ValueError('unknown ranking')
            for j in candidates:
                adding=j in held and complete_initial
                if j in sold or (j in held and not adding):
                    trace(i,j,'already_held_or_sold',quantity=held[j]['quantity'] if j in held else 0.)
                    continue
                if adding and (held[j]['pending'] or (guard and dd<=-.10)):continue
                if not adding and len(held)>=max_positions:
                    trace(i,j,'position_slots',holders=[str(names[k]) for k in held]);skipped['slots']+=1;continue
                if not b['execute'][i,j]:
                    trace(i,j,'execution_blocked');skipped['execution']+=1;continue
                price=float(b['open'][i,j]);distance=float(4*b['atr'][i-1,j])
                if adding:
                    p=held[j]
                    if price<p['last_fill_price']:continue
                    distance=price-p['stop']
                    if distance<=0:continue
                exposure=sum(p['quantity']*openmarks[k] for k,p in held.items())
                risk=sum(p['quantity']*max(0,openmarks[k]-p['stop']) for k,p in held.items())
                target=.005*prev_nav*(.5 if guard and dd<=-.10 else 1.)/distance
                if adding:target=max(0,p['risk_budget']-p['committed_risk'])/distance
                position_value=held[j]['quantity']*openmarks[j] if adding else 0.
                room=max(0,min(.9*navopen-exposure,.35*navopen-position_value))
                qty=min(target,max(0,.04*prev_nav-risk)/distance,room/price,max(0,cash)/(price*(1+cost_bps/10000)))
                trace(i,j,'sizing',target_quantity=target,available_quantity=qty,price=price,distance=distance,
                    previous_nav=prev_nav,cash=cash,exposure=exposure,risk_before=risk,risk_cap=.04*prev_nav,
                    risk_quantity=max(0,.04*prev_nav-risk)/distance,exposure_quantity=room/price,
                    cash_quantity=max(0,cash)/(price*(1+cost_bps/10000)),
                    partial_rejected=bool(full_entry_risk and qty<target*(1-1e-10)),
                    holders=[str(names[k]) for k in held])
                if full_entry_risk and qty<target*(1-1e-10):skipped['capital_or_risk']+=1;continue
                if qty*price<1.:skipped['capital_or_risk']+=1;continue
                value=qty*price;fee=value*cost_bps/10000;cash-=value+fee;fees+=fee
                assert risk+qty*distance<=.04*prev_nav+1e-6
                assert exposure+value<=.9*navopen+1e-6 and position_value+value<=.35*navopen+1e-6
                if adding:
                    p['quantity']+=qty;p['entry_value']+=value;p['entry_fee']+=fee
                    p['committed_risk']+=qty*distance;p['last_fill_price']=price
                    assert p['committed_risk']<=p['risk_budget']+1e-6
                else:
                    held[j]=dict(quantity=qty,stop=price-distance,distance=distance,pending=False,
                        entry_date=str(dates[i].date()),entry_value=value,entry_fee=fee,
                        risk_budget=target*distance,committed_risk=qty*distance,last_fill_price=price)
                marks[j]=price;markdates[j]=i
                order=dict(date=str(dates[i].date()),symbol=str(names[j]),side='buy',quantity=qty,price=price,fee=fee)
                if complete_initial:
                    p=held[j]
                    order.update(kind='completion' if adding else 'initial',campaign_entry_date=p['entry_date'],
                        stop=p['stop'],risk_budget=p['risk_budget'],committed_risk=p['committed_risk'])
                orders.append(order)
        marks[observed]=b['close'][i,observed];markdates[observed]=i
        nav=cash+sum(p['quantity']*marks[j] for j,p in held.items())
        assert cash>=-1e-6 and len(held)<=max_positions and np.isfinite(nav)
        stale=sum(p['quantity']*marks[j] for j,p in held.items() if markdates[j]!=i)
        global_peak=max(global_peak,nav);risk_peak=max(risk_peak,nav)
        path.append(dict(date=str(dates[i].date()),nav=nav/initial,cash=cash,positions=len(held),
            stale_value=stale,pending_exits=sum(p['pending'] for p in held.values()),
            drawdown=nav/global_peak-1,halted=halted))
        prev_nav=nav
    open_records=[dict(symbol=str(names[j]),entry_date=p['entry_date'],mark_date=str(dates[markdates[j]].date()),
        mark_value=p['quantity']*marks[j],pnl=p['quantity']*marks[j]-p['entry_value']-p['entry_fee'],
        initial_risk=p['committed_risk'],pending_exit=p['pending']) for j,p in held.items()]
    assert abs(sum(r['pnl'] for r in completed+open_records)-(prev_nav-initial))<1e-6
    frame=pd.DataFrame(path).set_index('date')
    result=dict(total_shadow_return=float(prev_nav/initial-1),max_shadow_drawdown=float(frame.drawdown.min()),
        best252_shadow_return=float(frame.nav.pct_change(252).max()),closed=len(completed),open=len(open_records),
        fees=fees,average_cash_weight=float((frame.cash/(frame.nav*initial)).mean()),
        terminal_stale_value=float(frame.stale_value.iloc[-1]),
        terminal_return_if_stale_zero=float((prev_nav-frame.stale_value.iloc[-1])/initial-1),
        skipped=skipped,halted_sessions=int(frame.halted.sum()))
    return result,frame,orders,completed,open_records


def main(output=OUT,full_entry_risk=False,complete_initial=False):
    output.mkdir(exist_ok=True)
    protocol=dict(status='SYNTHETIC PRICE SHADOW ACCOUNT, NOT VERIFIED TRADABLE RETURNS',
        cases='strength_all,lowvol_all,lowvol_best_quintile x15/30bps;same exits/execution/capital. No parameter search.',
        capital='1m initial;fractional synthetic units;8positions;0.5percent priorNAV planned entry risk,4percent aggregate distance-to-stop risk,90percent gross and35percent single-name caps on new buys. Profit drift permitted.',
        exits='Initial4ATR or two closesbelowMA200;priorclose signals,next eligibleopen;zero-range nofill scenario;stickyexits;no same-day reentry. No pyramiding.',
        guard='At10percent risk-epoch drawdown halve newrisk;at16percent liquidate whenexecutable,20flat sessions cooldown thenreset riskepoch. Report drawdown against globalpeak. Not guaranteed loss cap.',
        limitations='No rawshares,boardlots,historicalSTlimits,taxes,ADV,sectorcaps,companyaction cash/shares or terminalpayment ledger. IncompletePITuniverse. Stalequotes persist but cannotfundbuys. Same reusedhistory;not live readiness or true upperbound.')
    if full_entry_risk:
        protocol['sizing_sensitivity']='All-or-none planned risk per new entry:skip if availablecash/exposure/riskbudget cannot fund fulltarget. Tests fractional residual orders occupying slots;not an optimized minimum ticket or raw boardlot model.'
    if complete_initial:
        protocol['completion']='Retain initial target riskbudget andstop. Oncontinued qualifyingbreakout,allowcompletion onlyatprice>=lastfill andnotpendingexit/drawdown>=10percent. Sum of everybuy quantity*(fill-originalstop) cannot exceedoriginalriskbudget. Portfolio4percent risk,gross/name/cashcaps unchanged. Same candidate ranking,not priority toholdings. No increasedbudget or stopreset.'
    (output/'protocol.json').write_text(json.dumps(protocol,indent=2))
    b=build_bundle();results=[]
    if complete_initial:
        for full in (False,True):
            control=ROOT/('results/a-stock-campaign-shadow-fullrisk' if full else 'results/a-stock-campaign-shadow')
            for label,ranking,gate in [('strength_all','strength',False),('lowvol_all','lowvol',False),('lowvol_best_quintile','lowvol',True)]:
                for cost in (15,30):
                    case=f'{label}-{cost}'
                    _,p,o,c,s=simulate(b,ranking=ranking,gate=gate,cost_bps=cost,full_entry_risk=full)
                    assert o==json.loads((control/f'{case}-orders.json').read_text())
                    assert dict(closed=c,open=s)==json.loads((control/f'{case}-campaigns.json').read_text())
                    pd.testing.assert_frame_equal(p,pd.read_csv(control/f'{case}-path.csv',index_col=0),check_exact=False,rtol=1e-12,atol=1e-9)
        print('All12 original control paths,orders andcampaigns reproduced.',flush=True)
    for label,ranking,gate in [('strength_all','strength',False),('lowvol_all','lowvol',False),('lowvol_best_quintile','lowvol',True)]:
        for cost in (15,30):
            name=f'{label}-{cost}';m,p,o,c,s=simulate(b,ranking=ranking,gate=gate,cost_bps=cost,full_entry_risk=full_entry_risk,complete_initial=complete_initial)
            m.update(case=name);results.append(m);p.to_csv(output/f'{name}-path.csv')
            (output/f'{name}-orders.json').write_text(json.dumps(o))
            (output/f'{name}-campaigns.json').write_text(json.dumps(dict(closed=c,open=s)))
            (output/'results.json').write_text(json.dumps(results,indent=2));print(name,json.dumps(m),flush=True)


if __name__=='__main__':main()
