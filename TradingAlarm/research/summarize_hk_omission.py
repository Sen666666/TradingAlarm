"""Summarize every frozen stress comparison without choosing a universe."""
import json
import pandas as pd
from build_stock_features import ROOT


def main():
    out=ROOT/'results/monthly-hk-omission';rows=json.loads((out/'results.json').read_text());assert len(rows)==144
    pairs=[]
    for a,b in zip(rows[::2],rows[1::2]):
        assert a['policy']=='monthly' and b['policy']=='score_change'
        assert (a['excluded'],a['period'],a['scenario'])==(b['excluded'],b['period'],b['scenario'])
        pairs.append(dict(excluded=a['excluded'],period=a['period'],scenario=a['scenario'],control_return=a['total_return'],candidate_return=b['total_return'],difference=b['total_return']-a['total_return'],control_drawdown=a['max_drawdown'],candidate_drawdown=b['max_drawdown']))
    single=[p for p in pairs if len(p['excluded'])==1];joint=[p for p in pairs if len(p['excluded'])==2]
    original=ROOT/'results/monthly-hk-stock-transfer'
    path=pd.read_parquet(original/'0-base-score_change-path.parquet')
    wealth=pd.concat([pd.Series([1.],index=[path.index[0]-pd.Timedelta(days=1)]),path.nav])
    drawup=wealth/wealth.cummin()-1;peak=drawup.idxmax();trough=wealth.loc[:peak].idxmin()
    d=dict(adopted=False,comparisons=pairs,single_exclusion_improved=sum(p['difference']>0 for p in single),single_exclusion_pairs=len(single),joint_exclusion=joint,
        original_full_sample_best_hindsight_drawup=dict(return_fraction=float(drawup.max()),trough=str(trough.date()),peak=str(peak.date()),meaning='Maximum possible buy-and-hold interval return on this strategy NAV,chosen with hindsight;upper-bound diagnostic within this sample,not an executable cycle definition.'),
        validation=dict(original_controls_exact=18,independent_account_ledgers=144,excluded_orders_and_weights_zero=True,claim_events=sum(r['claim_events'] for r in rows),max_ledger_error=max(max(r['ledger'].values()) for r in rows)),
        limits='Winner exclusions selected retrospectively;remaining stocks/periods are not independent out-of-sample tests. Tail dependence expected in trend strategies;removal stress measures severity,not proof of invalidity. No optimized subset or replacement signal.',
        next='Stop further small-HK-sample rule tuning. Use broader existing A-share price universe for a fixed252monthly signal episode study before attempting a constrained stock-selection portfolio. Keep synthetic adjusted-price evidence separate from actual cash-account claims;include retired/stale holdings and fixed execution stresses.')
    (out/'decision.json').write_text(json.dumps(d,indent=2))
    p=ROOT/'progress.json';v=json.loads(p.read_text());v['multihorizon_trend_comparator']['hk_stock_transfer']['omission_stress']={'path':'results/monthly-hk-omission/decision.json','cases':144,'status':'Complete;notadopted;broaderstock signal validation next'};p.write_text(json.dumps(v,indent=2))
    print(json.dumps({k:d[k] for k in ('single_exclusion_improved','single_exclusion_pairs','joint_exclusion','original_full_sample_best_hindsight_drawup')},indent=2))

if __name__=='__main__':main()
