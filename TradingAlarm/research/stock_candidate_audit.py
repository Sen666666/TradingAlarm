"""Provisional signal inventory, explicitly not a recommendation or return backtest."""
import argparse,json,itertools
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/stock-signal-v1';OUT.mkdir(exist_ok=True)

def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--include-retired',action='store_true');parser.add_argument('--ths-retired',action='store_true');args=parser.parse_args()
    if args.ths_retired:args.include_retired=True
    if args.include_retired:
        OUT=ROOT/('results/stock-signal-ths-retired-v1' if args.ths_retired else 'results/stock-signal-retired-v1');OUT.mkdir(exist_ok=True)
    path=ROOT/'data/stock-features/local-features.parquet'
    paths=[path]+([ROOT/('data/stock-features/ths-retired-features.parquet' if args.ths_retired else 'data/stock-features/retired-features.parquet')] if args.include_retired else [])
    parts=[];counts=[]
    columns=['symbol','date','entry_signal','warmup_ready','observed_bar','positive_volume','momentum126_21','momentum252_21','turnover60']
    for batch in itertools.chain.from_iterable(pq.ParquetFile(p).iter_batches(batch_size=200000,columns=columns) for p in paths):
        frame=batch.to_pandas()
        ready=frame.warmup_ready&frame.observed_bar&frame.positive_volume
        candidates=ready&frame.entry_signal
        parts.append(frame.loc[candidates,['symbol','date','momentum126_21','momentum252_21','turnover60']])
        counts.append(frame.assign(ready=ready,candidate=candidates).groupby('date')[['ready','candidate']].sum())
    data=pd.concat(parts,ignore_index=True)
    if data.duplicated(['symbol','date']).any():raise ValueError('duplicate source symbol/date')
    grouped=data.groupby('date')
    data['relative_strength_score']=(grouped.momentum126_21.rank(pct=True)+grouped.momentum252_21.rank(pct=True))/2
    # Tie rules fixed and deterministic, with no future returns in selection.
    data=data.sort_values(['date','relative_strength_score','turnover60','symbol'],ascending=[True,False,False,True])
    data['rs_order']=data.groupby('date').cumcount()+1
    liquidity=data.sort_values(['date','turnover60','symbol'],ascending=[True,False,True]).copy()
    liquidity['liquidity_order']=liquidity.groupby('date').cumcount()+1
    data=data.merge(liquidity[['date','symbol','liquidity_order']],on=['date','symbol'],validate='one_to_one')
    daily=pd.concat(counts).groupby(level=0).sum()
    daily.to_csv(OUT/'daily-candidate-counts.csv')
    data.to_parquet(OUT/'provisional-candidates.parquet',index=False)
    annual=daily.groupby(daily.index.year).agg({'ready':'mean','candidate':['mean','median','max']})
    annual.columns=['_'.join(x) for x in annual.columns]
    annual.to_csv(OUT/'annual-candidate-counts.csv')
    summary={'source_scope':'Local provider-covered SH/SZ histories only; retired repair not merged, so survivor biased.',
             'candidate_observations':len(data),'symbols_ever_candidate':int(data.symbol.nunique()),
             'days':len(daily),'days_at_least10_candidates':int(daily.candidate.ge(10).sum()),
             'median_candidates':float(daily.candidate.median()),
             'ranks':'Cross-section of same-day breakout+SMA200 candidates with full warmup and positive observed volume; no future returns used.',
             'execution_ready':False,'account_returns_calculated':False,
             'limitations':['ST/price limits and accessibility not filtered yet','Full retired universe not yet merged','No historical sector classifications used','Rank comparison does not establish predictive edge']}
    if args.include_retired:summary['source_scope']='Local SH/SZ plus partially repaired retired histories. Still not a complete survivor-free universe.'
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2))
    print(json.dumps(summary,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
