"""All-six frozen-rule portfolio experiment with explicit provisional VNQ settlement."""
import json
from collections import defaultdict
import pandas as pd
from build_stock_features import ROOT
from campaign_engine import run_campaign
from global_usd_ledger_audit import load_asset
from portfolio_data import total_return_frame


def load_all(payment_delay=0):
    assets={s:load_asset(s) for s in ('SPY','EFA','IEF','GLD','DBC')}
    raw=pd.read_parquet(ROOT/'data/global-transfer/VNQ-ohlcv.parquet')
    div=json.loads((ROOT/'data/global-transfer/VNQ-provisional-distributions.json').read_text())
    for e in div:
        if payment_delay:
            i=raw.index.searchsorted(pd.Timestamp(e['pay_date']))+payment_delay
            e['pay_date']=str(raw.index[i].date()) if i<len(raw) else '2026-12-31'
    assets['VNQ']=dict(raw=raw,signal=total_return_frame(raw,div,[]),dividends=div,splits=[],currency='USD',lot=1,commission_min=0.,sector='realestate',kind='equity')
    assets['SPY']['sector']=assets['EFA']['sector']='equities'
    return assets


def reconcile(assets,path,orders,cost):
    cash=1e6;qty={s:0. for s in assets};claims=[];bydate=defaultdict(list);events=defaultdict(list)
    for o in orders:bydate[pd.Timestamp(o['date'])].append(o)
    for s,a in assets.items():
        for e in a['dividends']:events[pd.Timestamp(e['ex_date'])].append((s,e))
    errors=dict(cash=0.,wealth=0.,fees=0.,weight=0.);paid=0.;ledger=[]
    for day,row in path.iterrows():
        for s,e in events[day]:
            if qty[s]:claims.append((pd.Timestamp(e['pay_date']),qty[s]*e['amount']))
        payment=sum(v for date,v in claims if date<=day);cash+=payment;paid+=payment
        claims=[(date,v) for date,v in claims if date>day];fee_day=0.
        for o in bydate[day]:
            s=o['symbol'];price=float(assets[s]['raw'].loc[day,'open']);units=o['units']
            assert o['fx']==1 and o['raw_open']==price and units==int(units)
            fee=max(abs(units)*price*cost/10000,assets[s]['commission_min'])
            assert abs(fee-o['fee'])<1e-8
            cash-=units*price+fee;qty[s]+=units;fee_day+=fee
            assert cash>=-1e-6 and qty[s]>=0
        due=sum(v for _,v in claims);market={s:qty[s]*float(a['raw'].loc[:day,'close'].iloc[-1]) for s,a in assets.items()}
        wealth=cash+due+sum(market.values())
        errors['cash']=max(errors['cash'],abs(cash-row.cash));errors['wealth']=max(errors['wealth'],abs(wealth-row.nav*1e6))
        errors['fees']=max(errors['fees'],abs(fee_day-row.fees))
        for s in assets:errors['weight']=max(errors['weight'],abs(market[s]/wealth-row['w_'+s]))
        ledger.append(dict(date=str(day.date()),cash=cash,receivable=due,wealth=wealth,**{'value_'+s:v for s,v in market.items()}))
    assert max(errors.values())<1e-6,errors
    return dict(errors=errors,dividend_cash_paid=paid,final_receivable=due),ledger


def main():
    out=ROOT/'results/global-combined-provisional';out.mkdir(exist_ok=True)
    protocol=dict(universe=['SPY','EFA','IEF','GLD','VNQ','DBC'],start='2007-01-01',end='2025-12-31',
        rules='Existing55daybreakout/4ATRstop/twoMA200closes exit;lowATRpriority;noadd vs fixedinitialriskcompletion;no alpha tuning.',
        account='USD1m,0.5percententryrisk,4percentopenstopriskcap,6slots,90percentgross/35percentname/45percentsector buying caps. SPY/EFA share equities sector. Existing10/16percentrisk-epoch guards. No leverage. Winner weights can drift beyond buying caps.',
        settlement='VNQ third-party dates with frozen vendor gross amounts,explicit provisional scenario. All other payment facts as audited. Compare VNQ+10observed-sessionpayment delay; beyond sample remains unpaid.',
        cases='Each noadd/completion:15bpsbase,30bpscost2,one-session execution delay,10-session VNQ payment delay. No parameters selected from outcomes.',
        limitations='Current-vintage selected ETF survivors; no tax/idle-cash interest/trade settlement lag; next-open friction assumption; not direct futures/property or verified net investor outcome. Fixed blocks still pending.')
    (out/'protocol.json').write_text(json.dumps(protocol,indent=2));results=[]
    for completion in (False,True):
        for scenario,cost,delay,paydelay in [('base',15,0,0),('cost2',30,0,0),('delay1',15,1,0),('paydelay10',15,0,10)]:
            case=('completion' if completion else 'noadd')+'-'+scenario;assets=load_all(paydelay)
            metrics,path,orders,closed,state=run_campaign(assets,start='2007-01-01',pyramid=False,exit_mode='trend',
                ranking='low_atr',base_currency='USD',settlement_scenario=True,max_positions=6,
                cost_bps=cost,extra_delay=delay,complete_initial=completion)
            check,ledger=reconcile(assets,path,orders,cost)
            path.to_parquet(out/f'{case}-path.parquet');pd.DataFrame(ledger).to_parquet(out/f'{case}-ledger.parquet',index=False)
            (out/f'{case}-orders.json').write_text(json.dumps(orders,indent=2))
            (out/f'{case}-campaigns.json').write_text(json.dumps(dict(closed=closed,open=state),indent=2))
            r=dict(case=case,**metrics,completion_orders=sum(o['type']=='complete' for o in orders),ledger=check);results.append(r)
            (out/'results.json').write_text(json.dumps(results,indent=2));print(r,flush=True)

if __name__=='__main__':main()
