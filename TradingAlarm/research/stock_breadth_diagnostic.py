"""Frozen majority-trend market gate; descriptive overlapping labels, not portfolio NAV."""
import json
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/stock-breadth-v1'

def main():
    OUT.mkdir(exist_ok=True)
    protocol=dict(hypothesis='Broad participation may distinguish sustained trends from isolated breakouts.',rule='At signal close, strictly more than 50% of warmup-ready observed positive-volume stocks above own SMA200. No threshold optimization.',sources=['local-features.parquet','ths-retired-features.parquet'],periods=['2015-2021','2022+'],labels='Existing frozen monthly21/63/126session price labels; next-session start; no annualization or account-return claims.',comparisons=['unfiltered','breadth_pass','breadth_fail'],limitations=['Reused historical validation; exploratory','Survivor coverage and endpoint missingness unresolved','Overlapping forward labels; no independent significance claims','Market breadth is not sector membership or sector rotation','No dividends ledger, costs, positions or executable fills'])
    path=OUT/'protocol.json'
    if path.exists() and json.loads(path.read_text())!=protocol:raise ValueError('protocol changed')
    path.write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
    parts=[]
    for name in protocol['sources']:
        for batch in pq.ParquetFile(ROOT/'data/stock-features'/name).iter_batches(batch_size=200000,columns=['date','signal_close','sma200','warmup_ready','observed_bar','positive_volume']):
            f=batch.to_pandas();ready=f.warmup_ready&f.observed_bar&f.positive_volume
            f=f.assign(eligible=ready,above=ready&f.signal_close.gt(f.sma200))
            parts.append(f.groupby('date')[['eligible','above']].sum())
    breadth=pd.concat(parts).groupby(level=0).sum()
    breadth['fraction_above_sma200']=breadth.above/breadth.eligible.replace(0,float('nan'))
    breadth['gate']=breadth.fraction_above_sma200.gt(.5)
    breadth.to_csv(OUT/'daily-breadth.csv')
    labels=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/rank-diagnostic-by-date.csv',parse_dates=['date'])
    joined=labels.merge(breadth,on='date',validate='many_to_one')
    joined['period']=joined.date.ge(pd.Timestamp('2022-01-01')).map({False:'2015-2021',True:'2022+'})
    rows=[]
    for (period,selection,horizon),g in joined.groupby(['period','selection','horizon']):
        for name,mask in [('unfiltered',pd.Series(True,index=g.index)),('breadth_pass',g.gate),('breadth_fail',~g.gate)]:
            sample=g[mask];complete=sample[sample.selected.eq(sample.labels)]
            rows.append(dict(period=period,selection=selection,horizon=int(horizon),condition=name,dates=len(sample),labeled_dates=int(sample['mean'].notna().sum()),selected=int(sample.selected.sum()),available_labels=int(sample.labels.sum()),mean_price_return=sample['mean'].mean(),median_date_return=sample['mean'].median(),mean_tail80_fraction=sample.tail80_fraction.mean(),complete_dates=len(complete),complete_mean_price_return=complete['mean'].mean()))
    pd.DataFrame(rows).to_csv(OUT/'summary.csv',index=False)
    joined.to_csv(OUT/'by-date.csv',index=False)
    joined['year']=joined.date.dt.year
    joined.groupby(['year','selection','horizon','gate']).agg(dates=('date','count'),mean_price_return=('mean','mean'),selected=('selected','sum'),available_labels=('labels','sum')).to_csv(OUT/'annual.csv')
    contrasts=[]
    for (period,horizon,gate),g in joined.groupby(['period','horizon','gate']):
        wide=g.pivot(index='date',columns='selection',values='mean')
        pair=wide[['relative_strength_top10','all_candidates']].dropna()
        delta=pair.relative_strength_top10-pair.all_candidates
        contrasts.append(dict(period=period,horizon=int(horizon),gate=bool(gate),paired_dates=len(pair),mean_rs_minus_all=delta.mean(),positive_difference_fraction=delta.gt(0).mean()))
    pd.DataFrame(contrasts).to_csv(OUT/'same-market-selection-contrast.csv',index=False)

    print(pd.DataFrame(rows).query("selection=='relative_strength_top10'")[['period','horizon','condition','dates','mean_price_return','complete_dates']].to_string(index=False))
if __name__=='__main__':main()
