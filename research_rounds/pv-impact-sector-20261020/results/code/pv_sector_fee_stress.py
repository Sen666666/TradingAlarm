"""Post-result fee-asymmetry stress, not an exact historical tax model."""
import argparse
from pv_impact_sector import *

def main(out):
    out.mkdir(exist_ok=False)
    write(out/'protocol.json',dict(status='post-result sensitivity, base results already seen',stock_cost_bps=[25,28],base_cost_bps=15,fx_bps=10,changed='stock execution cost only; gate, picks and engine unchanged',interpretation='Additional 10/13 bps per side; not exact historical stamp duty, rounding or actual brokerage. Generic base fee may already overlap tax.'))
    etfs,_=load_extended();hk,_=load_assets();stocks={s:hk[s] for s in ['HK00700','HK03690','HK09618']};recipients={s:hk[s] for s in ['HK09618','HK03690']};rows=[]
    for kind in ['all3','top2']:
        gate,signals,events,_=make_targets(etfs['HK03033'],stocks,True,kind)
        for cost in [25,28]:
            case=f'{kind}-cost{cost}';kwargs=dict(selection=lambda d,s,q,p:s,entry_fraction=.45) if kind=='top2' else {}
            m,path,orders,decisions=run(stocks,'2022-01-01','2026-10-16','score_change',cost,10,0,signals=signals,cadence='daily',security_claims=CampaignClaims(stocks,recipients),**kwargs)
            check=reconcile_claims(stocks,path,orders,cost,10,recipients);ep,daily,shape=audit_episodes(stocks,path,orders,10)
            assert max(check.values())<1e-6 and shape['max_daily_error']<1e-6
            assert all(o['signal_date']<o['date'] for o in orders)
            path.to_parquet(out/f'{case}-path.parquet');write(out/f'{case}-orders.json',orders);write(out/f'{case}-episodes.json',ep);write(out/f'{case}-decisions.json',decisions)
            pd.DataFrame(daily).to_csv(out/f'{case}-daily-episodes.csv',index=False)
            rows.append(dict(case=case,**m,ledger=check,episodes=shape));print(case,m['total_return'],flush=True)
    write(out/'accounts.json',rows)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
