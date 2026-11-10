"""No-search stability checks for the already inspected continuous-activity entry case."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/stock-entry-v1'

def bootstrap_year_means(series,seed=431,n=5000):
    groups=[g.to_numpy() for _,g in series.groupby(series.index.year)]
    rng=np.random.default_rng(seed)
    draws=[np.concatenate([groups[i] for i in rng.integers(0,len(groups),len(groups))]).mean() for _ in range(n)]
    return dict(year_blocks=len(groups),low=float(np.quantile(draws,.025)),high=float(np.quantile(draws,.975)))

def main():
    d=pd.read_csv(OUT/'activity-sensitivity-by-date.csv',parse_dates=['date']);d=d[d.activity.eq('continuous20')]
    calendar=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values()
    rows=[];pairs=[]
    for (period,horizon),g in d.groupby(['period','horizon']):
        cutoff=calendar[-(int(horizon)+2)]
        g=g[g.date.le(cutoff)] # Exclude calendar-right-censored cohorts before missingness stress.
        a=g[g.strategy.eq('low_atr')].set_index('date');s=a['mean'].dropna()
        annual=s.groupby(s.index.year).mean()
        rows.append(dict(period=period,horizon=int(horizon),dates=len(a),labeled_dates=len(s),mean=float(s.mean()),median_date=float(s.median()),positive_dates=float(s.gt(0).mean()),mean_excluding_best5_dates=float(s.sort_values().iloc[:-5].mean()),worst_year_mean=float(annual.min()),positive_years=int(annual.gt(0).sum()),years=len(annual),missing_labels=int((a.selected-a.labels).sum()),selected=int(a.selected.sum()),stress_mean_missing_minus100=float(((a['mean'].fillna(0)*a.labels-(a.selected-a.labels))/a.selected).mean()),annual_block_bootstrap=bootstrap_year_means(s),leave_one_year_out_min=float(min(s[s.index.year!=y].mean() for y in annual.index))))
        for coverage in ['available','complete_dates']:
            part=g if coverage=='available' else g[g.selected.eq(g.labels)]
            wide=part.pivot(index='date',columns='strategy',values='mean')
            for comparator in ['all','rs']:
                matched=wide[['low_atr',comparator]].dropna();delta=matched.low_atr-matched[comparator]
                pairs.append(dict(period=period,horizon=int(horizon),coverage=coverage,comparator=comparator,paired_dates=len(delta),mean_difference=float(delta.mean()),median_difference=float(delta.median()),positive_fraction=float(delta.gt(0).mean()),annual_block_bootstrap=bootstrap_year_means(delta)))
    report=dict(status='Exploratory robustness, not independent confirmation',maturity='Only signal dates whose t+1+horizon lies within global observed calendar; sample-end censoring excluded before all checks',rows=rows,pairs=pairs,limitations=['Year blocks are few and cross-year forward labels remain dependent; intervals descriptive, not significance certification','Missing=-100% is an intentionally pessimistic diagnostic, not an imputation or realistic terminal payoff model','Deleting best dates is a concentration stress, not a tradable selection rule','No execution/cost/cash-account validation; lowATR hypothesis already inspected'])
    (OUT/'robustness.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
