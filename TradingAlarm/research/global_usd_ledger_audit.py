"""Real-price USD account diagnostic; not the six-asset transfer experiment."""
import json
from collections import defaultdict
import pandas as pd
from build_stock_features import ROOT
from campaign_engine import run_campaign
from portfolio_data import total_return_frame


def load_asset(symbol):
    folder=ROOT/'data/global-transfer'
    raw=pd.read_parquet(folder/f'{symbol}-ohlcv.parquet')
    dividends=[] if symbol=='GLD' else json.loads((folder/f'{symbol}-issuer-distributions.json').read_text())
    return dict(raw=raw,signal=total_return_frame(raw,dividends,[]),dividends=dividends,splits=[],
                currency='USD',lot=1,commission_min=0.,sector=symbol,kind='equity')


def reconcile(asset,path,orders,initial=1e6,cost_bps=15):
    """Independent raw-share cash replay; no engine valuation helpers used."""
    raw=asset['raw'];cash=initial;shares=0.;claims=[];bought=sold=paid=fees_total=0.
    bydate=defaultdict(list);events=defaultdict(list);ledger=[]
    for o in orders:bydate[pd.Timestamp(o['date'])].append(o)
    for e in asset['dividends']:events[pd.Timestamp(e['ex_date'])].append(e)
    errors=dict(cash=0.,nav=0.,fee=0.,weight=0.);entitlements=0
    for date,row in path.iterrows():
        # Entitlement is based on shares owned before today's opening trades.
        for e in events[date]:
            if shares:
                claims.append((pd.Timestamp(e['pay_date']),shares*e['amount']));entitlements+=1
        payment=sum(amount for pay,amount in claims if pay<=date)
        cash+=payment;paid+=payment;claims=[(pay,amount) for pay,amount in claims if pay>date]
        fees=0.
        for o in bydate[date]:
            assert o['fx']==1 and o['raw_open']==raw.loc[date,'open']
            qty=o['units'];assert qty==int(qty)
            notional=qty*raw.loc[date,'open'];fee=max(abs(notional)*cost_bps/10000,asset['commission_min'])
            assert abs(fee-o['fee'])<1e-8
            cash-=notional+fee;shares+=qty;fees+=fee
            if qty>0:bought+=notional
            else:sold-=notional
            assert cash>=-1e-6 and shares>=0
        fees_total+=fees;due=sum(amount for _,amount in claims);market=shares*raw.loc[date,'close'];nav=cash+due+market
        errors['cash']=max(errors['cash'],abs(cash-row.cash))
        errors['nav']=max(errors['nav'],abs(nav-row.nav*initial))
        errors['fee']=max(errors['fee'],abs(fees-row.fees))
        weight_col=next(c for c in path.columns if c.startswith('w_'))
        errors['weight']=max(errors['weight'],abs(market/nav-row[weight_col]))
        assert abs(cash-(initial-bought+sold+paid-fees_total))<1e-6
        ledger.append(dict(date=str(date.date()),shares=shares,cash=cash,dividend_receivable=due,
                           dividend_cash_paid=payment,market_value=market,wealth=nav))
    assert max(errors.values())<1e-6,errors
    return dict(maximum_errors=errors,entitlement_events=entitlements,distribution_cash_received=paid,
                final_receivable=due,final_cash=cash,final_market_value=market,final_wealth=nav),ledger


def main():
    out=ROOT/'results/global-usd-ledger';out.mkdir(exist_ok=True)
    protocol=dict(purpose='Validate USD cash/inventory accounting on five available individual assets; this is not a performance-selected replacement universe or the final six-asset portfolio.',
                  symbols=['SPY','EFA','IEF','GLD','DBC'],pending='VNQ payment dates and all-six combined experiment',
                  frozen_rule='55-day breakout/4ATR initial stop/two closes below MA200; no additions; next-open fills',
                  assumptions='USD account,1m initial,whole shares,15bps per side including friction,zero separate minimum,1percent lagged20dayADV cap,existing risk/exposure/drawdown guards. Gross distributions,zero idle-cash yield,investor taxes excluded. Settlement at issuer pay date or next observed session. ETF proxy only.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2));results=[]
    for symbol in protocol['symbols']:
        asset=load_asset(symbol)
        metrics,path,orders,closed,state=run_campaign({symbol:asset},start='2007-01-01',pyramid=False,
            exit_mode='trend',ranking='low_atr',base_currency='USD',max_positions=1)
        check,ledger=reconcile(asset,path,orders)
        path.to_parquet(out/f'{symbol}-path.parquet')
        pd.DataFrame(ledger).to_parquet(out/f'{symbol}-ledger.parquet',index=False)
        for name,data in [('orders',orders),('campaigns',dict(closed=closed,open=state))]:
            (out/f'{symbol}-{name}.json').write_text(json.dumps(data,indent=2))
        result=dict(symbol=symbol,metrics=metrics,ledger=check);results.append(result)
        (out/'results.json').write_text(json.dumps(results,indent=2));print(result,flush=True)


if __name__=='__main__':main()
