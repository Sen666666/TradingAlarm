"""Frozen entry/exit consistency candidate on existing raw-share A/HK samples."""
import json
import pandas as pd
from campaign_engine import run_campaign,features
from campaign_claims import CampaignClaims
from hk_extension import load_extended
from hk_in_kind_campaign import load_assets
from campaign_completion_ledger_audit import reconcile
from build_stock_features import ROOT


def main():
    out=ROOT/'results/entry-consistency-market-transfer';out.mkdir(exist_ok=True)
    (out/'protocol.json').write_text(json.dumps(dict(rule='Original noadd currentstoprisk baseline; only reject entry when prior-close twoMA200close exit is active; revalidate on fill.',
        cases='ETF17 and HK7 xbase/cost2/delay1. Reproduce allsix controls first. Keep raw shares,FX,claims,lots,fees unchanged.',
        limitation='Selected surviving ETF/HK samples; not complete historical A/HK stock universe; historical lots/taxes incomplete. A-share broad shadow remains separate. No 80percent/account or20percentMDD claim.'),indent=2))
    etf,_=load_extended();hk,_=load_assets();results=[]
    for group,assets,reference,prefix in [('etf17',etf,'campaign-asset-transfer','all'),('hk7',hk,'hk-in-kind-campaign','combined')]:
        chosen={n:dict(a,lot=400 if n=='HK00005' else 100) for n,a in assets.items()} if group=='hk7' else assets
        fs={n:features(a) for n,a in chosen.items()}
        for scenario in ('base','cost2','delay1'):
            cost=30 if scenario=='cost2' else 15;fx=20 if scenario=='cost2' else 10
            kwargs=dict(entry='breakout',exit_mode='trend',pyramid=False,ranking='low_atr',max_positions=len(chosen),
                eligible_kinds=('equity','defensive'),cost_bps=cost,fx_bps=fx,extra_delay=1 if scenario=='delay1' else 0)
            outputs=[]
            for candidate in (False,True):
                claims=CampaignClaims(chosen,{n:assets[n] for n in ['HK09618','HK03690']}) if group=='hk7' else None
                m,p,o,c,s=run_campaign(chosen,security_claims=claims,avoid_active_exit=candidate,**kwargs)
                outputs.append((m,p,o,c,s,claims))
                if not candidate:
                    ref=ROOT/'results'/reference;key=f'{prefix}-{scenario}'
                    assert o==json.loads((ref/f'{key}-orders.json').read_text())
                    assert dict(closed=c,open=s)==json.loads((ref/f'{key}-campaigns.json').read_text())
                    pd.testing.assert_frame_equal(p,pd.read_csv(ref/f'{key}-path.csv',index_col=0,parse_dates=True),check_exact=False,rtol=1e-12,atol=1e-9)
            cm,_,co,_,_,_=outputs[0];m,p,o,c,s,claims=outputs[1]
            for order in o:
                if order['units']>0:
                    q=fs[order['symbol']].loc[:pd.Timestamp(order['date'])-pd.Timedelta(days=1)].iloc[-1]
                    assert not q.trend_exit
            # Existing independent replay only covers zero in-kind claim paths.
            claim_active=claims is not None and (bool(claims.events) or any(claims.quantities().values()))
            check=None if claim_active else reconcile(chosen,p,o,cost,fx)
            case=f'{group}-{scenario}';p.to_csv(out/f'{case}-path.csv')
            (out/f'{case}-orders.json').write_text(json.dumps(o,indent=2))
            (out/f'{case}-campaigns.json').write_text(json.dumps(dict(closed=c,open=s),indent=2))
            if claims is not None:(out/f'{case}-claims.json').write_text(json.dumps(dict(events=claims.events,quantities=claims.quantities(),cash_paid=claims.cash_paid),indent=2))
            result=dict(case=case,control_exact=True,control_return=cm['total_return'],control_mdd=cm['max_drawdown'],**m,
                order_path_unchanged=o==co,ledger_errors=check,active_in_kind_claims=claim_active)
            results.append(result);(out/'results.json').write_text(json.dumps(results,indent=2));print(result,flush=True)

if __name__=='__main__':main()
