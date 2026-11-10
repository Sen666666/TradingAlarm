"""Replay raw inventory, dividend receipts and cash independently of decisions."""
import json
from collections import defaultdict
import pandas as pd
from campaign_engine import dividend_local_value
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from portfolio_data import fx_series
from campaign_r_audit import main as risk_audit
from build_stock_features import ROOT


def reconcile(assets,path,orders,cost_bps,fx_bps,initial_capital=1e6):
    idx=path.index;fx=fx_series(idx);cash=float(initial_capital);shares={n:0. for n in assets};receipts=[]
    splits={n:{pd.Timestamp(e['date']):e['ratio'] for e in a['splits']} for n,a in assets.items()}
    div={n:defaultdict(list) for n in assets}
    for n,a in assets.items():
        for e in a['dividends']:div[n][pd.Timestamp(e['ex_date'])].append(e)
    marks={n:a['raw'].close.reindex(idx,method='ffill') for n,a in assets.items()}
    bydate=defaultdict(list)
    for o in orders:bydate[pd.Timestamp(o['date'])].append(o)
    errors=dict(cash=0.,nav=0.,fees=0.,weights=0.)
    # These combined paths have no in-kind event; never infer this for all cases.
    for column in ['security_claim_value','claim_dividend_receivable','claim_dividend_cash_paid']:
        if column in path:assert path[column].eq(0).all()
    for date,row in path.iterrows():
        rates={n:float(fx.loc[date]) if a['currency']=='HKD' else 1. for n,a in assets.items()};fees=0.
        for n in assets:
            shares[n]*=splits[n].get(date,1.)
            for e in div[n].get(date,[]):
                if shares[n]:receipts.append((n,shares[n],e))
        remaining=[];due=0.
        for n,quantity,e in receipts:
            value=quantity*dividend_local_value(assets[n],e,date)*rates[n]
            if pd.Timestamp(e['pay_date'])<=date:
                fee=value*fx_bps/10000 if assets[n]['currency']=='HKD' else 0.
                foreign=e.get('currency',assets[n]['currency'])!=assets[n]['currency']
                fixed=e.get('settlement') and date>pd.Timestamp(e['settlement']['fixing'])
                if foreign and not fixed:fee+=value*e.get('conversion_bps',10)/10000
                cash+=value-fee;fees+=fee
            else:remaining.append((n,quantity,e));due+=value
        receipts=remaining
        for o in bydate[date]:
            n=o['symbol'];quantity=o['units'];a=assets[n]
            assert abs(o['fx']-rates[n])<1e-12
            assert abs(o['raw_open']-float(a['raw'].loc[date,'open']))<1e-12
            rate=(cost_bps+(fx_bps if a['currency']=='HKD' else 0))/10000
            fee=max(abs(quantity)*o['raw_open']*rates[n]*rate,18*rates[n] if a['currency']=='HKD' else 5.)
            assert abs(fee-o['fee'])<1e-8
            cash-=quantity*o['raw_open']*rates[n]+fee;fees+=fee;shares[n]+=quantity
            assert shares[n]>=-1e-8
        wealth=cash+due+sum(shares[n]*marks[n].loc[date]*rates[n] for n in assets)
        errors['cash']=max(errors['cash'],abs(cash-row.cash))
        errors['nav']=max(errors['nav'],abs(wealth-row.nav*initial_capital))
        errors['fees']=max(errors['fees'],abs(fees-row.fees))
        for n in assets:errors['weights']=max(errors['weights'],abs(shares[n]*marks[n].loc[date]*rates[n]/wealth-row['w_'+n]))
    assert max(errors.values())<1e-6,errors
    return errors


def main():
    out=ROOT/'results/campaign-completion-transfer';etf,_=load_extended();hk,_=load_assets();assets={**etf,**hk}
    results=json.loads((out/'results.json').read_text());checks=[];comparisons=[]
    for r in results:
        chosen=etf if r['group']=='etf17' else hk;case=r['case'];scenario=r['scenario']
        p=pd.read_csv(out/f'{case}-path.csv',index_col=0,parse_dates=True);o=json.loads((out/f'{case}-orders.json').read_text())
        error=reconcile(chosen,p,o,30 if scenario=='cost2' else 15,20 if scenario=='cost2' else 10)
        checks.append(dict(case=case,maximum_errors=error))
        reference='campaign-asset-transfer' if r['group']=='etf17' else 'hk-in-kind-campaign'
        prefix='all' if r['group']=='etf17' else 'combined'
        control=next(x for x in json.loads((ROOT/'results'/reference/'results.json').read_text()) if x['case']==f'{prefix}-{scenario}')
        comparisons.append(dict(case=case,control_return=control['total_return'],completion_return=r['total_return'],
            difference=r['total_return']-control['total_return'],control_drawdown=control['max_drawdown'],completion_drawdown=r['max_drawdown'],
            completion_orders=r['completion_orders']))
    (out/'ledger-reconciliation.json').write_text(json.dumps(checks,indent=2))
    (out/'comparison.json').write_text(json.dumps(comparisons,indent=2));print(json.dumps(comparisons,indent=2))
    risk_audit(source=out,out=out,assets_override=assets)


if __name__=='__main__':main()
