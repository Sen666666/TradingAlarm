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


def reconcile(assets,path,orders,cost_bps,fx_bps,recipients,fx_override=None,initial_capital=1e6):
    idx=path.index;fx=fx_series(idx) if fx_override is None else fx_override.reindex(idx).ffill();cash=float(initial_capital);shares={n:0. for n in assets};receipts=[]
    splits={n:{pd.Timestamp(e['date']):e['ratio'] for e in a['splits']} for n,a in assets.items()}
    div={n:defaultdict(list) for n in assets}
    for n,a in assets.items():
        for e in a['dividends']:div[n][pd.Timestamp(e['ex_date'])].append(e)
    marks={n:a['raw'].close.reindex(idx,method='ffill') for n,a in assets.items()}
    bydate=defaultdict(list)
    for o in orders:bydate[pd.Timestamp(o['date'])].append(o)
    errors=dict(cash=0.,nav=0.,fees=0.,weights=0.)
    claim_qty={s:0 for s in recipients};claim_receipts=[];claim_paid=0.
    assert all(a['currency']=='HKD' and not a['splits'] for a in recipients.values())
    errors.update(claim_value=0.,claim_due=0.,claim_paid=0.)
    for date,row in path.iterrows():
        rates={n:float(fx.loc[date]) if a['currency']=='HKD' else 1. for n,a in assets.items()};fees=0.
        for n in assets:
            shares[n]*=splits[n].get(date,1.)
            for e in div[n].get(date,[]):
                if shares[n]:receipts.append((n,shares[n],e))
        # Independent arithmetic, without importing the claim ledger implementation.
        for n,a in assets.items():
            for e in a.get('in_kind',[]):
                if pd.Timestamp(e['ex_date'])==date and shares[n]:
                    assert shares[n]==int(shares[n])
                    claim_qty[e['recipient']]+=int(shares[n])*e['numerator']//e['denominator']
        for n,a in recipients.items():
            for e in a['dividends']:
                if pd.Timestamp(e['ex_date'])==date and claim_qty[n]:claim_receipts.append((n,claim_qty[n],e))
        claim_remaining=[];claim_due=0.
        for n,q,e in claim_receipts:
            value=q*dividend_local_value(recipients[n],e,date)*float(fx.loc[date])
            if pd.Timestamp(e['pay_date'])<=date:
                fee=value*fx_bps/10000
                if e.get('currency','HKD')!='HKD' and not(e.get('settlement') and date>pd.Timestamp(e['settlement']['fixing'])):fee+=value*e.get('conversion_bps',10)/10000
                cash+=value-fee;claim_paid+=value-fee;fees+=fee
            else:claim_remaining.append((n,q,e));claim_due+=value
        claim_receipts=claim_remaining
        claim_value=sum(q*float(recipients[n]['raw'].loc[:date,'close'].iloc[-1])*float(fx.loc[date]) for n,q in claim_qty.items() if q)
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
        wealth=cash+due+claim_value+claim_due+sum(shares[n]*marks[n].loc[date]*rates[n] for n in assets)
        errors['claim_value']=max(errors['claim_value'],abs(claim_value-row.security_claim_value))
        errors['claim_due']=max(errors['claim_due'],abs(claim_due-row.claim_dividend_receivable))
        errors['claim_paid']=max(errors['claim_paid'],abs(claim_paid-row.claim_dividend_cash_paid))
        assert cash>=-1e-6
        errors['cash']=max(errors['cash'],abs(cash-row.cash))
        errors['nav']=max(errors['nav'],abs(wealth-row.nav*initial_capital))
        errors['fees']=max(errors['fees'],abs(fees-row.fees))
        for n in assets:errors['weights']=max(errors['weights'],abs(shares[n]*marks[n].loc[date]*rates[n]/wealth-row['w_'+n]))
    assert max(errors.values())<1e-6,errors
    return errors

