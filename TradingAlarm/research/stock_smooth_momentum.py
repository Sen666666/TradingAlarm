"""Continuous-return momentum hypothesis, adapted fixed-window diagnostic."""
import json,itertools
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from stock_entry_diagnostic import ROOT,select
from build_stock_features import grouped
OUT=ROOT/'results/stock-smooth-momentum'

def smooth_feature(close,active):
 ret=close.pct_change(fill_method=None);valid=active&active.shift(1,fill_value=False)
 sign=np.sign(ret).where(valid)
 #105 returns ending21sessions ago corresponds to close[t-21]/close[t-126].
 return (-sign.rolling(105,min_periods=105).mean()).shift(21)

def main():
 OUT.mkdir(exist_ok=True)
 protocol={'source':'https://digitalcommons.chapman.edu/business_articles/115/','scope':'Hypothesis inspired by continuous-information momentum; not a replication of original paper','score':'Negative mean sign of105 daily adjusted returns ending21sessions before signal, lower=more positive days; require all105 returns observed and tradable by volume proxy','pool':'Existing continuous20 monthly breakout candidates with positive126-to21 momentum and score available','comparison':'Top10 smooth score vs top10 existingRS in identical pool; no future-label refill','limitations':['Different formation period/universe/long-only selections from paper','Not exact matching on cumulative momentum, marketcap or sector','No execution costs, cash accounting or complete historical universe; overlapping reused history','Higher average long-horizon price return does not establish portfolio alpha']}
 (OUT/'protocol.json').write_text(json.dumps(protocol,indent=2))
 d=pd.read_parquet(ROOT/'results/stock-entry-v1/all-candidate-activity-audit.parquet');d=d[d.active20.eq(20)&d.momentum126_21.gt(0)].copy();wanted=set(d.symbol);parts=[]
 for symbol,f in itertools.chain.from_iterable(grouped(pq.ParquetFile(ROOT/'data/stock-features'/p),['symbol','date','signal_close','observed_bar','positive_volume']) for p in ['local-features.parquet','ths-retired-features.parquet']):
  if symbol not in wanted:continue
  f=f.sort_values('date').reset_index(drop=True);f['smooth_score']=smooth_feature(f.signal_close,f.observed_bar&f.positive_volume);parts.append(f[['symbol','date','smooth_score']])
 d=d.merge(pd.concat(parts),on=['symbol','date'],validate='one_to_one');coverage={'positive_momentum_candidates':len(d),'score_available':int(d.smooth_score.notna().sum())};d=d.dropna(subset=['smooth_score'])
 d.to_parquet(OUT/'candidate-pool.parquet',index=False)
 selected=pd.concat([select(d,'smooth_score').assign(strategy='smooth'),select(d,'rs_order').assign(strategy='rs')]);selected.to_parquet(OUT/'selected.parquet',index=False)
 cal=pd.read_csv(ROOT/'results/stock-signal-ths-retired-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True).index.sort_values();rows=[]
 for h in [10,21,63,126]:
  mature=selected[selected.date.le(cal[-(h+2)])]
  for (strategy,dt),g in mature.groupby(['strategy','date']):
   v=g[f'forward_{h}'].dropna();rows.append(dict(strategy=strategy,date=dt,year=dt.year,period='early' if dt.year<2022 else 'recent',horizon=h,selected=len(g),labels=len(v),mean=float(v.mean())))
 t=pd.DataFrame(rows);t.to_csv(OUT/'by-date.csv',index=False);summary=[]
 for (period,h),g in t.groupby(['period','horizon']):
  for coverage_name,part in [('available',g),('complete_dates',g[g.selected.eq(g.labels)])]:
   w=part.pivot(index='date',columns='strategy',values='mean').dropna();delta=w.smooth-w.rs
   summary.append(dict(period=period,horizon=int(h),coverage=coverage_name,dates=len(w),smooth_mean=float(w.smooth.mean()),rs_mean=float(w.rs.mean()),difference=float(delta.mean()),positive_dates=float(delta.gt(0).mean())))
 (OUT/'summary.json').write_text(json.dumps(summary,indent=2));(OUT/'coverage.json').write_text(json.dumps(coverage,indent=2));print(pd.DataFrame(summary).to_string(index=False))
if __name__=='__main__':main()
