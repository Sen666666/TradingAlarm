"""Audit whether low measured ATR comes from non-trading gaps."""
from pathlib import Path
import itertools
import pandas as pd
import pyarrow.parquet as pq
from build_stock_features import grouped
ROOT=Path(__file__).resolve().parent;OUT=ROOT/'results/stock-entry-v1'
d=pd.read_parquet(OUT/'selected-observations.parquet');d=d[d.selection.eq('all')];wanted=set(d.symbol);parts=[]
for symbol,f in itertools.chain.from_iterable(grouped(pq.ParquetFile(ROOT/'data/stock-features'/p),['symbol','date','observed_bar','positive_volume']) for p in ['local-features.parquet','ths-retired-features.parquet']):
 if symbol not in wanted:continue
 f=f.sort_values('date');f['active20']=(f.observed_bar&f.positive_volume).rolling(20,min_periods=20).sum();parts.append(f[['symbol','date','active20']])
a=d.merge(pd.concat(parts),on=['symbol','date'],validate='one_to_one');a.to_parquet(OUT/'all-candidate-activity-audit.parquet',index=False)
print('selected',len(a),'fewer than20 active days',int(a.active20.lt(20).sum()),'fewer than10',int(a.active20.lt(10).sum()))
print(a[a.active20.lt(10)][['symbol','date','active20','atr_fraction','forward_10']].head(12).to_string(index=False))

from stock_entry_diagnostic import select,HORIZONS
rows=[]
for name,base in [('all',a),('continuous20',a[a.active20.eq(20)])]:
 for strategy,g in [('all',base),('low_atr',select(base,'atr_fraction')),('rs',select(base,'rs_order'))]:
  for dt,f in g.groupby('date'):
   for n in HORIZONS:
    v=f[f'forward_{n}'].dropna()
    rows.append(dict(activity=name,strategy=strategy,date=dt,period='2015-2021' if dt.year<2022 else '2022+',horizon=n,selected=len(f),labels=len(v),mean=v.mean()))
t=pd.DataFrame(rows);t.to_csv(OUT/'activity-sensitivity-by-date.csv',index=False)
s=t.groupby(['activity','strategy','period','horizon']).agg(dates=('date','count'),selected=('selected','sum'),labels=('labels','sum'),mean_price_return=('mean','mean'))
s.to_csv(OUT/'activity-sensitivity-summary.csv');print(s.loc['continuous20'].to_string())
