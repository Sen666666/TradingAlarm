"""One long-only unlevered continuous-price proxy. No contract/margin claim."""
import numpy as np,pandas as pd
SCENARIOS={'base':dict(fee=.0002,slip=.04,delay=1),'cost2':dict(fee=.0004,slip=.08,delay=1),'delay1':dict(fee=.0002,slip=.04,delay=2)}

def run(bars,signals,buy_kinds,exit_mode,scenario,benchmark=False):
    cash=1.;qty=0.;floor=np.nan;pending=None;leg=None;daily=[];trades=[];fills=[];orders=[];fee_total=slip_total=0.
    fee,slip,delay=scenario['fee'],scenario['slip'],scenario['delay'];idx=bars.index
    if benchmark:pending=dict(side='buy',due=0,signal_date='preset_window_start',support=-np.inf,kind='buy_hold',endpoint='')
    for i,(dt,bar) in enumerate(bars.iterrows()):
        sig=signals.loc[dt];held=qty>0;exited_today=False;dayfee=dayslip=0.;activity=[]
        if pending is not None and pending['due']<=i and bar.volume>0:
            order=pending;pending=None;op=float(bar.open)
            if order['side']=='buy' and op<=order['support']:
                orders.append(dict(date=str(dt.date()),action='cancel_gap_below_support',**order));activity.append('gap_cancel')
            elif order['side']=='buy' and qty==0:
                before=cash;px=op+slip;qty=cash/(px*(1+fee));paid=qty*px*fee;slipcost=qty*slip;cash-=qty*px+paid
                if abs(cash)<1e-12:cash=0.
                floor=order['support'];held=True
                leg=dict(entry_date=str(dt.date()),entry_signal=order['signal_date'],endpoint=order['endpoint'],buy_kind=order['kind'],entry_price=px,entry_raw_open=op,quantity=qty,capital_before=before,entry_fee=paid,entry_slippage=slipcost,initial_support=floor)
                fills.append(dict(date=str(dt.date()),side='buy',quantity=qty,raw_price=op,price=px,fee=paid,slippage=slipcost,signal_date=order['signal_date'],reason=order['kind']))
                dayfee+=paid;dayslip+=slipcost;activity.append('buy')
            elif order['side']=='sell' and qty>0:
                px=op-slip;paid=qty*px*fee;slipcost=qty*slip;cash+=qty*px-paid
                trades.append(dict(leg,exit_date=str(dt.date()),exit_signal=order['signal_date'],exit_price=px,exit_fee=paid,exit_slippage=slipcost,exit_reason=order['kind'],capital_after=cash,net_return=cash/leg['capital_before']-1,net_pnl=cash-leg['capital_before'],terminal=False))
                fills.append(dict(date=str(dt.date()),side='sell',quantity=qty,raw_price=op,price=px,fee=paid,slippage=slipcost,signal_date=order['signal_date'],reason=order['kind']))
                qty=0.;floor=np.nan;leg=None;exited_today=True;dayfee+=paid;dayslip+=slipcost;activity.append('sell')
        if not benchmark:
            # Existing support is judged at this close, never filled at an
            # earlier intraday touch inferred from the same complete bar.
            broken=qty>0 and bar.low<floor
            seller=qty>0 and exit_mode=='M' and bool(sig.new_sell)
            if qty>0 and (broken or seller) and pending is None:
                pending=dict(side='sell',due=i+delay,signal_date=str(dt.date()),support=floor,kind='support_broken' if broken else 'confirmed_sell',endpoint=str(sig.bi_end))
                orders.append(dict(date=str(dt.date()),action='submit',**pending))
            if qty>0 and pending is None and sig.new_buy and bar.low>=sig.bi_low:
                floor=max(floor,float(sig.bi_low))
            if pending is not None and pending['side']=='buy' and bar.low<pending['support']:
                orders.append(dict(date=str(dt.date()),action='cancel_known_support_break',**pending));pending=None
            if qty==0 and pending is None and not exited_today and not sig.new_sell:
                eligible=[k for k in buy_kinds if bool(sig[k])]
                if eligible and bar.low>=sig.bi_low and bar.close>sig.bi_low:
                    pending=dict(side='buy',due=i+delay,signal_date=str(dt.date()),support=float(sig.bi_low),kind='+'.join(eligible),endpoint=str(sig.bi_end))
                    orders.append(dict(date=str(dt.date()),action='submit',**pending))
        # Predeclared end-of-window liquidation is an administrative close,
        # not a Chan sell signal. No observation after the window is consumed.
        if i==len(bars)-1:
            if pending is not None:orders.append(dict(date=str(dt.date()),action='unfilled_window_end',**pending));pending=None
            if qty>0:
                px=float(bar.close)-slip;paid=qty*px*fee;slipcost=qty*slip;cash+=qty*px-paid
                trades.append(dict(leg,exit_date=str(dt.date()),exit_signal='preset_window_end',exit_price=px,exit_fee=paid,exit_slippage=slipcost,exit_reason='window_end',capital_after=cash,net_return=cash/leg['capital_before']-1,net_pnl=cash-leg['capital_before'],terminal=True))
                fills.append(dict(date=str(dt.date()),side='sell',quantity=qty,raw_price=float(bar.close),price=px,fee=paid,slippage=slipcost,signal_date='preset_window_end',reason='window_end'))
                qty=0.;floor=np.nan;leg=None;dayfee+=paid;dayslip+=slipcost;activity.append('terminal_close')
        fee_total+=dayfee;slip_total+=dayslip;nav=cash+qty*bar.close
        assert cash>=-1e-10 and qty>=0 and nav>0
        daily.append(dict(date=dt,cash=cash,quantity=qty,close=float(bar.close),nav=nav,floor=floor,held=int(held or qty>0),fee=dayfee,slippage=dayslip,pending='' if pending is None else pending['side'],activity='+'.join(activity)))
    daily=pd.DataFrame(daily).set_index('date');peak=np.maximum.accumulate(np.r_[1.,daily.nav.to_numpy()])[1:];daily['drawdown']=daily.nav/peak-1
    trades=pd.DataFrame(trades);fills=pd.DataFrame(fills);orders=pd.DataFrame(orders)
    returns=trades.net_return.to_numpy() if len(trades) else np.array([])
    # Cash/position, closed-leg and fee ledger reconciliation.
    np.testing.assert_allclose(daily.nav,daily.cash+daily.quantity*daily.close,atol=1e-12,rtol=1e-12)
    np.testing.assert_allclose(np.prod(1+returns),daily.nav.iloc[-1],atol=1e-12,rtol=1e-12)
    if len(trades):np.testing.assert_allclose(trades.net_pnl.sum(),daily.nav.iloc[-1]-1,atol=1e-12,rtol=1e-12)
    summary=dict(net_return=float(daily.nav.iloc[-1]-1),max_drawdown=float(-daily.drawdown.min()),trades=len(trades),win_rate=float(np.mean(returns>0)) if len(returns) else None,
        best_trade=float(returns.max()) if len(returns) else None,worst_trade=float(returns.min()) if len(returns) else None,terminal_trades=int(trades.terminal.sum()) if len(trades) else 0,
        exposure_days=int(daily.held.sum()),exposure_fraction=float(daily.held.mean()),fees=fee_total,slippage=slip_total,ending_nav=float(daily.nav.iloc[-1]),cancelled_orders=int(orders.action.str.startswith('cancel').sum()) if len(orders) else 0)
    return summary,daily,trades,fills,orders
