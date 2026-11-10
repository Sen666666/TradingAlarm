"""Shared normalized long/cash execution; state and execution are separate."""
import math
import numpy as np,pandas as pd
SCENARIOS={'base':dict(cost=1,delay=1),'cost2':dict(cost=2,delay=1),'delay1':dict(cost=1,delay=2)}

def backtest(d,s,initial,symbol,scenario,benchmark=False,matched_to=None,policy='E0',features=None):
    cost,delay=scenario['cost'],scenario['delay'];fee=(.0002 if symbol=='AU0' else .0005)*cost
    slip_abs=.04*cost if symbol=='AU0' else 0.;slip_rel=0. if symbol=='AU0' else .0005*cost
    cash=1.;qty=0.;pending=None;leg=None;trades=[];fills=[];orders=[];ledger=[];sid=0
    locked=None if matched_to is None else {x['entry_date']:x for x in matched_to.to_dict('records')}
    matched_leg=None;peak=stop=math.nan
    if locked is None and (initial['active'] or benchmark):pending=dict(side='buy',due=0,signal_date='preset_start',floor=initial['floor'] if not benchmark else -np.inf,reason='carry' if not benchmark else 'hold',signal_id=0)
    for i,(dt,bar) in enumerate(d.iterrows()):
        row=s.loc[dt];activity=[];held=qty>0
        if locked is not None:
            if matched_leg is not None and qty>0 and matched_leg['exit_date']==str(dt.date()) and not matched_leg['terminal'] and (pending is None or pending['due']>i):
                pending=dict(side='sell',due=i,signal_date=matched_leg['exit_signal'],floor=float(row.floor),reason='E0_boundary',signal_id=int(matched_leg['signal_id']))
            if str(dt.date()) in locked:
                assert qty==0 and pending is None
                matched_leg=locked[str(dt.date())]
                pending=dict(side='buy',due=i,signal_date=matched_leg['entry_signal'],floor=float(matched_leg['initial_floor']),reason='matched_E0_entry',signal_id=int(matched_leg['signal_id']))
        if pending is not None and pending['side']=='buy' and locked is None and not benchmark and i>0 and not bool(s.target.iloc[i-1]):
            orders.append(dict(date=str(dt.date()),action='cancel_stale_state',**pending));pending=None
        if pending is not None and pending['due']<=i:
            order=pending;pending=None;raw=float(bar.open);slip=slip_abs+raw*slip_rel
            if order['side']=='buy' and raw<=order['floor']:
                orders.append(dict(date=str(dt.date()),action='cancel_gap',**order))
            elif order['side']=='buy' and qty==0:
                px=raw+slip;capital=cash;qty=cash/(px*(1+fee));paid=qty*px*fee;cash=0.;held=True
                if locked is not None:
                    peak=math.log(raw);stop=peak-int(policy[1:])*float(features.loc[dt,'atr']) if policy in ['E2','E3'] else -math.inf
                leg=dict(entry_date=str(dt.date()),entry_signal=order['signal_date'],entry_price=px,capital_before=capital,quantity=qty,entry_fee=paid,entry_slippage=qty*slip,initial_floor=order['floor'],signal_id=order['signal_id'])
                fills.append(dict(date=str(dt.date()),side='buy',quantity=qty,raw_price=raw,price=px,fee=paid,slippage=qty*slip,signal_date=order['signal_date'],reason=order['reason']));activity.append('buy')
            elif order['side']=='sell' and qty>0:
                px=raw-slip;paid=qty*px*fee;cash+=qty*px-paid
                trades.append(dict(leg,exit_date=str(dt.date()),exit_signal=order['signal_date'],exit_price=px,exit_fee=paid,exit_slippage=qty*slip,exit_reason=order['reason'],capital_after=cash,net_return=cash/leg['capital_before']-1,net_pnl=cash-leg['capital_before'],terminal=False))
                fills.append(dict(date=str(dt.date()),side='sell',quantity=qty,raw_price=raw,price=px,fee=paid,slippage=qty*slip,signal_date=order['signal_date'],reason=order['reason']));qty=0.;leg=None;activity.append('sell')
        if locked is not None:
            if qty>0:
                peak=max(peak,math.log(float(bar.close)))
                if policy in ['E2','E3']:stop=max(stop,peak-int(policy[1:])*float(features.loc[dt,'atr']))
                extra=(policy in ['E2','E3'] and math.log(float(bar.close))<=stop) or (policy=='ED' and int(row.event)==-1)
                if extra and pending is None:
                    pending=dict(side='sell',due=i+delay,signal_date=str(dt.date()),floor=float(row.floor),reason='matched_'+policy,signal_id=int(matched_leg['signal_id']));orders.append(dict(date=str(dt.date()),action='submit',**pending))
        elif not benchmark:
            if row.entered:sid+=1
            if qty>0 and not row.target and pending is None:
                pending=dict(side='sell',due=i+delay,signal_date=str(dt.date()),floor=float(row.floor),reason=str(row.exit_reason) or 'inactive',signal_id=sid);orders.append(dict(date=str(dt.date()),action='submit',**pending))
            elif qty==0 and row.target and pending is None:
                pending=dict(side='buy',due=i+delay,signal_date=str(dt.date()),floor=float(row.floor),reason=str(row.entry_kind) or 'eligible_after_exit',signal_id=sid);orders.append(dict(date=str(dt.date()),action='submit',**pending))
            elif pending is not None and pending['side']=='buy' and not row.target:
                orders.append(dict(date=str(dt.date()),action='cancel_close_invalid',**pending));pending=None
        if i==len(d)-1:
            if pending is not None:orders.append(dict(date=str(dt.date()),action='unfilled_end',**pending));pending=None
            if qty>0:
                raw=float(bar.close);slip=slip_abs+raw*slip_rel;px=raw-slip;paid=qty*px*fee;cash+=qty*px-paid
                trades.append(dict(leg,exit_date=str(dt.date()),exit_signal='preset_end',exit_price=px,exit_fee=paid,exit_slippage=qty*slip,exit_reason='window_end',capital_after=cash,net_return=cash/leg['capital_before']-1,net_pnl=cash-leg['capital_before'],terminal=True))
                fills.append(dict(date=str(dt.date()),side='sell',quantity=qty,raw_price=raw,price=px,fee=paid,slippage=qty*slip,signal_date='preset_end',reason='window_end'));qty=0.;leg=None;activity.append('terminal_close')
        assert cash>=-1e-12 and qty>=0
        ledger.append(dict(date=dt,cash=cash,quantity=qty,close=float(bar.close),nav=cash+qty*bar.close,held=int(held or qty>0),target=int(row.target),floor=float(row.floor),exit_line=float(row.exit_line),activity='+'.join(activity)))
    ledger=pd.DataFrame(ledger).set_index('date');ledger['drawdown']=ledger.nav/np.maximum.accumulate(np.r_[1.,ledger.nav.to_numpy()])[1:]-1
    tc=['entry_date','entry_signal','entry_price','capital_before','quantity','entry_fee','entry_slippage','initial_floor','signal_id','exit_date','exit_signal','exit_price','exit_fee','exit_slippage','exit_reason','capital_after','net_return','net_pnl','terminal']
    fc=['date','side','quantity','raw_price','price','fee','slippage','signal_date','reason']
    trades=pd.DataFrame(trades,columns=tc);fills=pd.DataFrame(fills,columns=fc);orders=pd.DataFrame(orders)
    rr=trades.net_return.to_numpy(dtype=float);tail=trades.net_return.ge(.30);natural=trades.loc[~trades.terminal.astype(bool)]
    np.testing.assert_allclose(ledger.nav,ledger.cash+ledger.quantity*ledger.close,rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(np.prod(1+rr),ledger.nav.iloc[-1],rtol=1e-12,atol=1e-12)
    np.testing.assert_allclose(trades.net_pnl.sum(),ledger.nav.iloc[-1]-1,rtol=1e-12,atol=1e-12)
    summary=dict(net_return=float(ledger.nav.iloc[-1]-1),max_drawdown=float(-ledger.drawdown.min()),trades=len(trades),wins=int((rr>0).sum()),win_rate=float((rr>0).mean()) if len(rr) else None,
        natural_trades=len(natural),natural_win_rate=float(natural.net_return.gt(0).mean()) if len(natural) else None,terminal_trades=int(trades.terminal.sum()),tail_trades=int(tail.sum()),tail_pnl=float(trades.loc[tail,'net_pnl'].sum()),ordinary_pnl=float(trades.loc[~tail,'net_pnl'].sum()),
        avg_win=float(rr[rr>0].mean()) if (rr>0).any() else None,avg_loss=float(rr[rr<=0].mean()) if (rr<=0).any() else None,exposure_days=int(ledger.held.sum()),exposure_fraction=float(ledger.held.mean()),fees=float(fills.fee.sum()),slippage=float(fills.slippage.sum()),cancelled_orders=int(orders.action.str.startswith('cancel').sum()) if len(orders) else 0)
    return summary,ledger,trades,fills,orders
