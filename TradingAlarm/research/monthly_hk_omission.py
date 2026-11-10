"""All-single-name and explicit joint-winner omission stress, no subset selection."""
import json
import pandas as pd
from build_stock_features import ROOT
from hk_in_kind_campaign import load_assets
from campaign_claims import CampaignClaims
from monthly_ah_engine import run
from monthly_claim_ledger_audit import reconcile


def main():
    out=ROOT/'results/monthly-hk-omission';assert (out/'protocol.json').exists()
    old=ROOT/'results/monthly-hk-stock-transfer';periods=json.loads((old/'protocol.json').read_text())['periods']
    original,_=load_assets();original={s:dict(a,lot=400 if s=='HK00005' else 100) for s,a in original.items()}
    recipients={s:original[s] for s in ('HK09618','HK03690')}
    for r in json.loads((old/'results.json').read_text()):
        sc=r['scenario'];claims=CampaignClaims(original,recipients)
        _,p,o,_=run(original,*periods[r['period']],r['policy'],30 if sc=='cost2' else 15,20 if sc=='cost2' else 10,1 if sc=='delay1' else 0,security_claims=claims)
        pd.testing.assert_frame_equal(p,pd.read_parquet(old/f"{r['case']}-path.parquet"),check_exact=True)
        assert o==json.loads((old/f"{r['case']}-orders.json").read_text())
    print('18 original controls exactly reproduced',flush=True)
    groups=[(s,) for s in sorted(original)]+[('HK00005','HK00883')];results=[]
    for excluded in groups:
        assets={s:dict(a) for s,a in original.items()}
        for s in excluded:
            assets[s]['signal']=assets[s]['signal'].copy();assets[s]['signal']['close']=1.
        label='+'.join(excluded)
        for i,(start,end) in enumerate(periods):
            for scenario,cost,fx,delay in [('base',15,10,0),('cost2',30,20,0),('delay1',15,10,1)]:
                for policy in ('monthly','score_change'):
                    claims=CampaignClaims(assets,recipients)
                    m,p,o,d=run(assets,start,end,policy,cost,fx,delay,security_claims=claims)
                    assert not any(x['symbol'] in excluded for x in o)
                    assert all(p['w_'+s].eq(0).all() for s in excluded)
                    check=reconcile(assets,p,o,cost,fx,recipients)
                    case=f'{label}-{i}-{scenario}-{policy}';p.to_parquet(out/f'{case}-path.parquet')
                    (out/f'{case}-orders.json').write_text(json.dumps(o))
                    (out/f'{case}-claims.json').write_text(json.dumps(dict(events=claims.events,quantities=claims.quantities())))
                    results.append(dict(case=case,excluded=list(excluded),period=i,scenario=scenario,policy=policy,**m,ledger=check,claim_events=len(claims.events)))
                a,b=results[-2:];print(dict(excluded=label,period=i,scenario=scenario,monthly=a['total_return'],drift=b['total_return'],difference=b['total_return']-a['total_return']),flush=True)
                (out/'results.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
