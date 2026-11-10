"""Reproduce frozen May/November financial sampling without outcome columns."""
import pandas as pd

def calendar_requests(candidates):
 r=candidates.loc[candidates.active20.eq(20)&candidates.date.dt.year.between(2016,2025)&candidates.date.dt.month.isin([5,11]),['symbol','date','active20']].sort_values(['date','symbol'])
 if r.duplicated(['symbol','date']).any():raise ValueError('duplicate candidate')
 tasks=[];seen=set()
 for row in r.itertuples(index=False):
  for offset in [1,2,3,4]:
   q=row.date.to_period('Q')-offset;key=(row.symbol,q.year,q.quarter)
   if key in seen:continue
   seen.add(key);tasks.append(dict(symbol=row.symbol,year=q.year,quarter=q.quarter,first_candidate_date=str(row.date.date())))
 return r,pd.DataFrame(tasks,columns=['symbol','year','quarter','first_candidate_date'])
