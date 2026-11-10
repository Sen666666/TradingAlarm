"""Within-date gate-label permutation control, not an independent alpha significance test."""
import json
from pathlib import Path
import numpy as np
import pandas as pd
from stock_entry_diagnostic import HORIZONS
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/stock-sector-proxy-v1'

def pick_indices(order,gate,top=10):
    return order[np.asarray(gate,dtype=bool)[order]][:top]

def main():
    protocol=dict(repetitions=200,seed=90731,method='Within each date randomly permute real binary gate labels among covered candidates, preserve pass count, then rank and take10; never use labels to select/refill',comparison='Actual minus randomized selection on matching dates with available forward labels; exclude globally immature forward horizons',status='Post-discovery mechanism falsification; not untouched validation',limitations=['Gate labels may not be exchangeable across stock risk/liquidity; no formal causal or significance claim','Incomplete universe and missing endpoints','Price returns only; no costs or feasible account execution','Across-date shuffle destroys persistence; not portfolio simulation'])
    p=OUT/'placebo-protocol.json'
    if p.exists() and json.loads(p.read_text())!=protocol:raise ValueError('protocol changed')
    p.write_text(json.dumps(protocol,indent=2))
    c=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet');c=c[c.active20.eq(20)]
    a=pd.read_parquet(OUT/'assignments.parquet');data=c.merge(a,on=['symbol','date'],validate='one_to_one')
    dates=sorted(data.date.unique());calendar=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values()
    rng=np.random.default_rng(protocol['seed']);N=protocol['repetitions'];scores=np.full((N+1,2,len(dates),len(HORIZONS)),np.nan);counts=np.zeros_like(scores,dtype=int);selected=np.zeros((N+1,2,len(dates)),int)
    for di,dt in enumerate(dates):
        g=data[data.date.eq(dt)].reset_index(drop=True);gates=g.gate.to_numpy(bool)
        orders=[g.sort_values([key,'turnover60','symbol'],ascending=[True,False,True]).index.to_numpy() for key in ['rs_order','atr_fraction']]
        labels=g[[f'forward_{h}' for h in HORIZONS]].to_numpy(float)
        for rep in range(N+1):
            gate=gates if rep==0 else rng.permutation(gates)
            for si,order in enumerate(orders):
                ix=pick_indices(order,gate);selected[rep,si,di]=len(ix)
                values=labels[ix]
                for hi,h in enumerate(HORIZONS):
                    if dt>calendar[-(h+2)]:continue
                    valid=values[:,hi][np.isfinite(values[:,hi])];counts[rep,si,di,hi]=len(valid)
                    if len(valid):scores[rep,si,di,hi]=valid.mean()
    summaries=[]
    for period,mask in [('2019-2021',np.array([d.year<2022 for d in dates])),('2022+',np.array([d.year>=2022 for d in dates]))]:
        for si,strategy in enumerate(['rs','low_atr']):
            for hi,h in enumerate(HORIZONS):
                actual=scores[0,si,mask,hi];deltas=[];paired=[];control=[]
                for rep in range(1,N+1):
                    random=scores[rep,si,mask,hi];valid=np.isfinite(actual)&np.isfinite(random)
                    deltas.append(float((actual[valid]-random[valid]).mean()));paired.append(int(valid.sum()));control.append(float(random[valid].mean()))
                summaries.append(dict(period=period,strategy=strategy,horizon=h,actual_mean=float(np.nanmean(actual)),mean_random_control=float(np.mean(control)),mean_actual_minus_random=float(np.mean(deltas)),difference_5pct=float(np.quantile(deltas,.05)),difference_95pct=float(np.quantile(deltas,.95)),fraction_random_controls_beating_actual=float(np.mean(np.asarray(deltas)<0)),minimum_paired_dates=min(paired),maximum_paired_dates=max(paired)))
    pd.DataFrame(summaries).to_csv(OUT/'placebo-summary.csv',index=False)
    np.savez_compressed(OUT/'placebo-details.npz',scores=scores,counts=counts,selected=selected,dates=np.asarray([str(d.date()) for d in dates]),horizons=np.asarray(HORIZONS))
    print(pd.DataFrame(summaries).to_string(index=False))
if __name__=='__main__':main()
