import json
import pandas as pd
from build_stock_features import ROOT
from hk_in_kind_campaign import load_assets
from hk_extension import load_extended
from campaign_claims import CampaignClaims
from monthly_ah_engine import run
from monthly_claim_ledger_audit import reconcile


def main():
    out=ROOT/'results/monthly-hk-stock-transfer';protocol=json.loads((out/'protocol.json').read_text())
    etf,_=load_extended();old=ROOT/'results/monthly-ah-etf-transfer'
    for r in json.loads((old/'results.json').read_text()):
        i=r['period'];start,end=protocol['periods'][i];sc=r['scenario'];policy=r['policy']
        m,p,o,d=run(etf,start,end,policy,30 if sc=='cost2' else 15,20 if sc=='cost2' else 10,1 if sc=='delay1' else 0)
        pd.testing.assert_frame_equal(p,pd.read_parquet(old/f"{r['case']}-path.parquet"),check_exact=True)
        assert o==json.loads((old/f"{r['case']}-orders.json").read_text())
    print('18 ETF controls exactly reproduced',flush=True)
    assets,_=load_assets();assets={s:dict(a,lot=400 if s=='HK00005' else 100) for s,a in assets.items()}
    recipients={s:assets[s] for s in ('HK09618','HK03690')};results=[]
    for i,(start,end) in enumerate(protocol['periods']):
        for scenario,cost,fx,delay in [('base',15,10,0),('cost2',30,20,0),('delay1',15,10,1)]:
            for policy in ('monthly','score_change'):
                claims=CampaignClaims(assets,recipients)
                m,p,o,d=run(assets,start,end,policy,cost,fx,delay,security_claims=claims)
                check=reconcile(assets,p,o,cost,fx,recipients)
                if policy=='score_change':
                    for order in o:
                        ds=[x for x in d if order['signal_date']<x['date']<=order['date']];assert len(ds)==1
                        j=d.index(ds[0]);s=order['symbol'];assert j==0 or d[j]['scores'][s]!=d[j-1]['scores'][s]
                case=f'{i}-{scenario}-{policy}';p.to_parquet(out/f'{case}-path.parquet')
                for suffix,data in [('orders',o),('decisions',d),('claims',dict(events=claims.events,quantities=claims.quantities(),cash_paid=claims.cash_paid))]:
                    (out/f'{case}-{suffix}.json').write_text(json.dumps(data,indent=2))
                r=dict(case=case,period=i,scenario=scenario,policy=policy,**m,ledger=check,claim_events=len(claims.events),terminal_claim_value=float(p.security_claim_value.iloc[-1]))
                results.append(r);(out/'results.json').write_text(json.dumps(results,indent=2));print(r,flush=True)

if __name__=='__main__':main()
