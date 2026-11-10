"""Reusable strategy matrix: strategy plugins do not own execution/accounting."""
import json
import pandas as pd
from build_stock_features import ROOT
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from campaign_claims import CampaignClaims
from monthly_ah_engine import run
from strategy_signals import build_signals,period_metrics,HORIZONS
from monthly_claim_ledger_audit import reconcile as reconcile_claims
from campaign_completion_ledger_audit import reconcile as reconcile_cash


def main(output='trend-workbench-v1'):
    out=ROOT/'results'/output;protocol=json.loads((out/'protocol.json').read_text());allocation=protocol.get('allocation','equal_capital')
    etf,_=load_extended();hk,_=load_assets();hk={s:dict(a,lot=400 if s=='HK00005' else 100) for s,a in hk.items()}
    groups={'etf17':etf,'hk7':hk};recipients={s:hk[s] for s in ('HK09618','HK03690')};results=[];controls=0
    for group,assets in groups.items():
        old=ROOT/'results'/('monthly-ah-etf-transfer' if group=='etf17' else 'monthly-hk-stock-transfer')
        periods=json.loads((old/'protocol.json').read_text())['periods']
        for r in ([] if protocol.get('controls_reference') else json.loads((old/'results.json').read_text())):
            sc=r['scenario'];claims=CampaignClaims(assets,recipients) if group=='hk7' else None
            _,p,o,_=run(assets,*periods[r['period']],r['policy'],30 if sc=='cost2' else 15,20 if sc=='cost2' else 10,1 if sc=='delay1' else 0,security_claims=claims)
            pd.testing.assert_frame_equal(p,pd.read_parquet(old/f"{r['case']}-path.parquet"),check_exact=True)
            assert o==json.loads((old/f"{r['case']}-orders.json").read_text());controls+=1
        print(group,'controls verified',flush=True)
        end=min(a['raw'].index.max() for a in assets.values());assert end==pd.Timestamp('2026-10-16')
        for name in protocol['strategies']:
            signals=build_signals(assets,name)
            for cadence in protocol['cadences']:
                for scenario,cost,fx,delay in [('base',15,10,0),('cost2',30,20,0),('delay1',15,10,1)]:
                    case=f'{group}-{name}-{cadence}-{scenario}'
                    if allocation!='equal_capital' and (ROOT/'results'/protocol['controls_reference']/f'{case}-path.parquet').exists():
                        reference=ROOT/'results'/protocol['controls_reference']
                        control_claims=CampaignClaims(assets,recipients) if group=='hk7' else None
                        _,cp,co,_=run(assets,'2022-01-01',str(end.date()),'score_change',cost,fx,delay,security_claims=control_claims,signals=signals,cadence=cadence,allocation=protocol.get('control_allocation','equal_capital'))
                        pd.testing.assert_frame_equal(cp,pd.read_parquet(reference/f'{case}-path.parquet'),check_exact=True)
                        assert co==json.loads((reference/f'{case}-orders.json').read_text());controls+=1
                    claims=CampaignClaims(assets,recipients) if group=='hk7' else None
                    m,p,o,d=run(assets,'2022-01-01',str(end.date()),'score_change',cost,fx,delay,security_claims=claims,signals=signals,cadence=cadence,allocation=allocation)
                    check=reconcile_claims(assets,p,o,cost,fx,recipients) if claims is not None else reconcile_cash(assets,p,o,cost,fx)
                    case=f'{group}-{name}-{cadence}-{scenario}'
                    if protocol.get('controls_reference') and allocation=='equal_capital':
                        reference=ROOT/'results'/protocol['controls_reference']
                        if (reference/f'{case}-path.parquet').exists():
                            pd.testing.assert_frame_equal(p,pd.read_parquet(reference/f'{case}-path.parquet'),check_exact=True)
                            assert o==json.loads((reference/f'{case}-orders.json').read_text());controls+=1
                    p.to_parquet(out/f'{case}-path.parquet');(out/f'{case}-orders.json').write_text(json.dumps(o))
                    r=dict(case=case,group=group,strategy=name,cadence=cadence,scenario=scenario,**m,ledger=check,through2025=period_metrics(p,'2022-01-01','2025-12-31'),year2026=period_metrics(p,'2026-01-01','2026-10-16'),claim_events=len(claims.events) if claims else 0)
                    r['allocation']=allocation
                    results.append(r);(out/'results.json').write_text(json.dumps(results,indent=2));print(case,'2026',r['year2026']['return_fraction'],'full',m['total_return'],flush=True)
    expected=len(groups)*len(protocol['strategies'])*len(protocol['cadences'])*3
    assert controls>0 and len(results)==expected
    (out/'validation.json').write_text(json.dumps(dict(exact_controls=controls,new_ledgers=len(results),max_ledger_error=max(max(r['ledger'].values()) for r in results)),indent=2))

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',default='trend-workbench-v1')
    main(parser.parse_args().output)
