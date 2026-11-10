"""Control correction: preserve the same observed-price clock when lagging volume."""
import argparse
from pathlib import Path
import pandas as pd,numpy as np
from run_competing_state import assets,volume,write,run,competing_frame,exposure,CampaignClaims,cash_check,claims_check,audit_episodes,manifest

def main(out):
    out.mkdir(exist_ok=False);write(out/'protocol.json',dict(status='post-result control correction, original lag rows preserved',reason='Raw shifted volume relocated zero-volume exclusions, changing observed price clock on6-8dates in HK assets in account period.',method='Fix positive price/volume observed sessions first. Shift volume21 on that clock, fill first21 using first observed volume (causally available). Model warmup63 means initial filler is outside volume-reference window when first model update occurs. Reindex output to original clock; model parameters unchanged.',scope='Only lag-control ETF17/HK7 base rerun; new results independent directory. Main PV/price unaffected.'))
    groups,_=assets();rows=[];checks=[]
    for group,items in groups.items():
        signals={}
        for s,a in items.items():
            c=a['signal'].close;v=volume(a);valid=c.gt(0)&v.gt(0)&np.isfinite(c)&np.isfinite(v);cc=c.loc[valid];vv=v.loc[valid];lag=vv.shift(21).fillna(vv.iloc[0]);f=competing_frame(cc,lag);cut=len(cc)//2;pd.testing.assert_frame_equal(competing_frame(cc.iloc[:cut],lag.iloc[:cut]),f.iloc[:cut]);assert len(f)==int(valid.sum());sig=exposure(f.reindex(c.index).strength);signals[s]=sig;f.reindex(c.index).assign(target=sig).to_csv(out/f'{s}-signals.csv',index_label='date');checks.append(dict(symbol=s,observed_rows=len(f),prefix=True))
        cost,fx=15,10;recipients={s:groups['hk7'][s] for s in ['HK09618','HK03690']};claims=CampaignClaims(items,recipients) if group=='hk7' else None;m,path,orders,decisions=run(items,'2022-01-01','2026-10-16','score_change',cost,fx,0,signals=signals,cadence='daily',security_claims=claims);check=claims_check(items,path,orders,cost,fx,recipients) if claims else cash_check(items,path,orders,cost,fx);ep,daily,shape=audit_episodes(items,path,orders,fx);assert max(check.values())<1e-6 and shape['max_daily_error']<1e-6;assert all(o['signal_date']<o['date'] for o in orders)
        case=group+'-lag-observed-clock';path.to_parquet(out/f'{case}-path.parquet');write(out/f'{case}-orders.json',orders);write(out/f'{case}-decisions.json',decisions);write(out/f'{case}-episodes.json',ep);pd.DataFrame(daily).to_csv(out/f'{case}-daily-episodes.csv',index=False);rows.append(dict(case=case,**m,ledger=check,episodes=shape));print(case,m['total_return'],flush=True)
    write(out/'accounts.json',rows);write(out/'validation.json',dict(assets=checks));
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);main(p.parse_args().output)
