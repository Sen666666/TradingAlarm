"""Actual HK account daily PNL split by retrospective opportunity windows.
All outside dates remain outside, including incomplete-label late-year dates;
outside is NOT synonymous with false opportunities.
"""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from monthly_hk_episode_audit import audit
from hk_in_kind_campaign import load_assets

OUT=Path('results/trend-event-account-attribution')
SOURCES={'markov_volume_map':'strength-markov-map','adaptive_geometry_price_volume_split_units':'strength-volume-units'}


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'protocol.json').write_text(json.dumps(dict(status='Frozen before outcomes',scope='HK7 actual base/cost2/delay1 accounts, Markov and adaptive frozen models',allocation='Daily incremental episode PNL assigned to parent stock; retained in-kind claims stay with parent, including after parent sale.',windows='Per-symbol retrospective event interval, start<day<=end. Start close signals cannot earn start-day move.',reconciliation='Daily per-symbol PNL must equal daily NAV difference, fees equal account fees, and reference Markov episode objects unchanged.',limits='Hindsight attribution only. Outside includes late-year and other unlabeled opportunities, not proof of bad entries. Does not show counterfactual holding improvement. delay1 includes cancellation.'),indent=2))
    assets,_=load_assets();windows=pd.read_csv('results/trend-opportunity-events/events.csv');windows=windows.loc[windows.group.eq('hk7')];results=[]
    for model,source in SOURCES.items():
        for scenario in ['base','cost2','delay1']:
            case=f'hk7-{model}-daily-{scenario}';root=Path('results')/source
            path=pd.read_parquet(root/f'{case}-path.parquet');orders=json.loads((root/f'{case}-orders.json').read_text());daily=[]
            episodes,error=audit(assets,path,orders,20 if scenario=='cost2' else 10,allow_claims=True,daily_output=daily)
            reference=root/f'{case}-episodes.json'
            exact=False
            if reference.exists():assert episodes==json.loads(reference.read_text());exact=True
            f=pd.DataFrame(daily);f['date']=pd.to_datetime(f.date);f['inside']=False
            for w in windows.itertuples():f.loc[f.symbol.eq(w.symbol)&f.date.gt(pd.Timestamp(w.start))&f.date.le(pd.Timestamp(w.end)),'inside']=True
            total=f.groupby('date')[['pnl','fees']].sum();expected=path.nav.diff().fillna(path.nav.iloc[0]-1)*1e6
            daily_error=float((total.pnl-expected).abs().max());fee_error=float((total.fees-path.fees).abs().max())
            assert daily_error<1e-6 and fee_error<1e-6
            f['gross_before_fees']=f.pnl+f.fees;f['year']=f.date.dt.year
            f.to_parquet(OUT/f'{case}-daily.parquet',index=False)
            grouped=f.groupby(['year','inside'])[['pnl','fees','gross_before_fees']].sum().reset_index();grouped.to_csv(OUT/f'{case}-yearly.csv',index=False)
            amounts=f.groupby('inside')[['pnl','fees','gross_before_fees']].sum()
            result=dict(case=case,reference_episodes_exact=exact,ledger_error=error,daily_error=daily_error,fee_error=fee_error,inside=amounts.loc[True].to_dict(),outside=amounts.loc[False].to_dict(),total_pnl=float(f.pnl.sum()))
            results.append(result);print(json.dumps(result),flush=True)
    (OUT/'summary.json').write_text(json.dumps(results,indent=2))


if __name__=='__main__':main()
