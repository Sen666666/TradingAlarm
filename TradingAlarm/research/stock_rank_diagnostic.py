"""Predeclared ranking diagnostic. Prices, not an executable portfolio backtest."""
import argparse,json,itertools
from pathlib import Path
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import grouped
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/stock-signal-v1'
HORIZONS=(21,63,126)

def forward_labels(frame):
    frame=frame.sort_values('date').reset_index(drop=True)
    result=frame[['date']].copy()
    available=frame.observed_bar & frame.positive_volume
    for n in HORIZONS:
        valid=available.shift(-1,fill_value=False)&available.shift(-(n+1),fill_value=False)
        result[f'forward_{n}']=(frame.signal_close.shift(-(n+1))/frame.signal_close.shift(-1)-1).where(valid)
    return result

def main():
    global OUT
    parser=argparse.ArgumentParser();parser.add_argument('--include-retired',action='store_true');parser.add_argument('--ths-retired',action='store_true');args=parser.parse_args()
    if args.ths_retired:args.include_retired=True
    if args.include_retired:OUT=ROOT/('results/stock-signal-ths-retired-v1' if args.ths_retired else 'results/stock-signal-retired-v1')
    sources=[ROOT/'data/stock-features/local-features.parquet']+([ROOT/('data/stock-features/ths-retired-features.parquet' if args.ths_retired else 'data/stock-features/retired-features.parquet')] if args.include_retired else [])
    protocol={'kind':'exploratory signal diagnostic, not account backtest','sampling':'first observed market session of each calendar month','selection':'top10 frozen relative-strength ranking vs top10 frozen liquidity ranking vs all trend candidates; never refill based on future label availability','horizons':list(HORIZONS),'label':'factor-adjusted close on session t+1 to t+1+horizon; require observed positive-volume endpoints; interim gaps retained and flagged limitation','aggregation':'equal weight within each selection/date then equal weight across dates; no annualization','limitations':['local survivor bias','not execution prices or account accounting','no fees, cash or position sizing','endpoint missingness can bias diagnostics; report coverage','overlapping horizons, not independent observations','revised provider adjustment factors']}
    (OUT/'rank-diagnostic-protocol.json').write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
    candidates=pd.read_parquet(OUT/'provisional-candidates.parquet')
    daily=pd.read_csv(OUT/'daily-candidate-counts.csv',index_col=0,parse_dates=True)
    first=daily.groupby(daily.index.to_period('M')).head(1).index
    candidates=candidates[candidates.date.isin(first)].copy()
    wanted=set(candidates.symbol);parts=[]
    cols=['symbol','date','signal_close','observed_bar','positive_volume']
    for symbol,frame in itertools.chain.from_iterable(grouped(pq.ParquetFile(p),cols) for p in sources):
        if symbol not in wanted:continue
        labels=forward_labels(frame);labels['symbol']=symbol
        parts.append(labels[labels.date.isin(first)])
    data=candidates.merge(pd.concat(parts),on=['symbol','date'],validate='one_to_one')
    selections={'all_candidates':data,'liquidity_top10':data[data.liquidity_order<=10],'relative_strength_top10':data[data.rs_order<=10]}
    rows=[]
    for name,subset in selections.items():
        for n in HORIZONS:
            column=f'forward_{n}'
            for date,g in subset.groupby('date'):
                values=g[column].dropna()
                rows.append(dict(selection=name,horizon=n,date=str(date.date()),selected=len(g),labels=len(values),mean=float(values.mean()) if len(values) else None,median=float(values.median()) if len(values) else None,tail80_fraction=float((values>=.8).mean()) if len(values) else None))
    table=pd.DataFrame(rows);table.to_csv(OUT/'rank-diagnostic-by-date.csv',index=False)
    summary=table.groupby(['selection','horizon']).agg(dates=('date','count'),selected=('selected','sum'),available_labels=('labels','sum'),mean_date_price_return=('mean','mean'),mean_date_tail80_fraction=('tail80_fraction','mean')).reset_index()
    summary.to_csv(OUT/'rank-diagnostic-summary.csv',index=False)
    table['year']=pd.to_datetime(table.date).dt.year
    table.groupby(['year','selection','horizon'])[['mean','selected','labels']].mean().to_csv(OUT/'rank-diagnostic-by-year.csv')
    paired=[]
    for n in HORIZONS:
        complete=table[(table.horizon==n)&(table.selected==table.labels)]
        wide=complete.pivot(index='date',columns='selection',values='mean')
        for comparator in ['liquidity_top10','all_candidates']:
            sample=wide[['relative_strength_top10',comparator]].dropna()
            for period,part in [('all',sample),('2015-2021',sample.loc[sample.index<'2022-01-01']),('2022+',sample.loc[sample.index>='2022-01-01'])]:
                diff=part.relative_strength_top10-part[comparator]
                paired.append(dict(horizon=n,comparator=comparator,period=period,complete_paired_dates=len(part),mean_rs_minus_comparator=float(diff.mean()) if len(diff) else None,positive_difference_fraction=float((diff>0).mean()) if len(diff) else None))
    pd.DataFrame(paired).to_csv(OUT/'rank-diagnostic-complete-pairs.csv',index=False)
    print(summary.to_string(index=False),flush=True)

if __name__=='__main__':main()
