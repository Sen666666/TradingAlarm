"""Fixed entry-quality alternatives, with no portfolio-return interpretation."""
import json,itertools
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import grouped
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'results/stock-entry-v1'
HORIZONS=(10,21,63,126)

def select(data,key):
    # Ranking sees only current features. Missing future labels never cause refilling.
    ordered=data.sort_values(['date',key,'turnover60','symbol'],ascending=[True,True,False,True])
    return ordered.groupby('date').head(10)

def main():
    OUT.mkdir(exist_ok=True)
    protocol=dict(hypotheses=['Lower ATR/price may avoid volatile failed breakouts','Smaller (close-prior55high)/ATR may avoid extended entries'],sampling='Same frozen first-session-per-month breakout+SMA200 candidates',selections=['all','RS top10','liquidity top10','low ATR/price top10','low breakout extension top10'],horizons=list(HORIZONS),periods=['2015-2021','2022+'],ranking='ascending feature, descending lagged turnover, ascending symbol; no future-label refilling',limitation='Exploratory reused history; price labels, not account returns; no costs/execution/terminal payouts; monthly sampling does not simulate continuous two-week trading; overlapping horizons and missing endpoints')
    p=OUT/'protocol.json'
    if p.exists() and json.loads(p.read_text())!=protocol:raise ValueError('protocol changed')
    p.write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
    base=ROOT/'results/stock-signal-ths-retired-v1'
    daily=pd.read_csv(base/'daily-candidate-counts.csv',index_col=0,parse_dates=True)
    first=daily.groupby(daily.index.to_period('M')).head(1).index
    candidates=pd.read_parquet(base/'provisional-candidates.parquet');candidates=candidates[candidates.date.isin(first)]
    wanted=set(candidates.symbol);parts=[]
    cols=['symbol','date','signal_close','observed_bar','positive_volume','atr20','breakout55']
    for symbol,f in itertools.chain.from_iterable(grouped(pq.ParquetFile(ROOT/'data/stock-features'/p),cols) for p in ['local-features.parquet','ths-retired-features.parquet']):
        if symbol not in wanted:continue
        f=f.sort_values('date').reset_index(drop=True)
        available=f.observed_bar&f.positive_volume
        out=f[['date','symbol']].copy()
        out['atr_fraction']=f.atr20/f.signal_close
        out['extension_atr']=(f.signal_close-f.breakout55)/f.atr20.replace(0,np.nan)
        for n in HORIZONS:
            valid=available.shift(-1,fill_value=False)&available.shift(-(n+1),fill_value=False)
            out[f'forward_{n}']=(f.signal_close.shift(-(n+1))/f.signal_close.shift(-1)-1).where(valid)
        parts.append(out[out.date.isin(first)])
    data=candidates.merge(pd.concat(parts),on=['symbol','date'],validate='one_to_one')
    if not np.isfinite(data[['atr_fraction','extension_atr']]).all().all():raise ValueError('invalid current ranking feature')
    selections={'all':data,'rs':data[data.rs_order<=10],'liquidity':data[data.liquidity_order<=10],'low_atr':select(data,'atr_fraction'),'low_extension':select(data,'extension_atr')}
    pd.concat([f.assign(selection=name) for name,f in selections.items()],ignore_index=True).to_parquet(OUT/'selected-observations.parquet',index=False)
    rows=[]
    for name,f in selections.items():
        for dt,g in f.groupby('date'):
            for n in HORIZONS:
                values=g[f'forward_{n}'].dropna()
                rows.append(dict(selection=name,date=dt,horizon=n,selected=len(g),labels=len(values),mean=values.mean(),tail80=values.ge(.8).mean() if len(values) else np.nan))
    table=pd.DataFrame(rows);table['period']=np.where(table.date.dt.year<2022,'2015-2021','2022+')
    table.to_csv(OUT/'by-date.csv',index=False)
    summary=table.groupby(['period','selection','horizon']).agg(dates=('date','count'),labeled_dates=('mean','count'),selected=('selected','sum'),available_labels=('labels','sum'),mean_price_return=('mean','mean'),mean_tail80_fraction=('tail80','mean'))
    summary.to_csv(OUT/'summary.csv')
    table.assign(year=table.date.dt.year).groupby(['year','selection','horizon']).agg(mean_price_return=('mean','mean'),labels=('labels','sum')).to_csv(OUT/'annual.csv')
    table[table.selected.eq(table.labels)].groupby(['period','selection','horizon']).agg(dates=('date','count'),mean_price_return=('mean','mean')).to_csv(OUT/'complete-date-sensitivity.csv')
    print(summary.to_string())
if __name__=='__main__':main()
