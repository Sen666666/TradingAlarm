"""Bounded read-only scan of the one existing canonical bar table."""
from pathlib import Path
from collections import Counter
import hashlib,json,time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parent
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet')

def main():
    start=time.monotonic();counts=Counter();sources=Counter();years=[];examples=[];ratios=[]
    cols=['symbol','trade_date','open','high','low','close','volume','amount','source']
    for batch in pq.ParquetFile(SOURCE).iter_batches(batch_size=500000,columns=cols):
        a=batch.to_pandas();counts['rows']+=len(a);sources.update(a.source.value_counts().to_dict())
        a['year']=a.trade_date.dt.year
        masks={}
        for col in ['open','high','low','close','volume','amount']:
            masks[col+'_nonfinite']=~np.isfinite(a[col]);masks[col+'_zero']=a[col].eq(0);masks[col+'_negative']=a[col].lt(0)
        masks['OHLC_geometry_invalid']=(a.high.lt(a[['open','close','low']].max(axis=1)-1e-10)|a.low.gt(a[['open','close','high']].min(axis=1)+1e-10))
        masks['weekend_row']=a.trade_date.dt.weekday.ge(5)
        masks['PVR_close_amount_unusable']=~(np.isfinite(a.close)&a.close.gt(0)&np.isfinite(a.amount)&a.amount.gt(0))
        for k,v in masks.items():counts[k]+=int(v.sum())
        bad=np.logical_or.reduce([v.to_numpy()for v in masks.values()])
        if bad.any()and len(examples)<20:examples+=a.loc[bad,cols].head(20-len(examples)).assign(trade_date=lambda z:z.trade_date.astype(str)).to_dict('records')
        years.append(a.groupby(['symbol','year']).trade_date.agg(first='min',last='max',rows='size').reset_index())
        valid=np.isfinite(a.amount)&np.isfinite(a.volume)&np.isfinite(a.close)&a.amount.gt(0)&a.volume.gt(0)&a.close.gt(0)
        sample=a.loc[valid].iloc[::1000]
        ratios.extend((sample.amount/(sample.volume*sample.close)).tolist())
    sy=pd.concat(years).groupby(['symbol','year']).agg(first=('first','min'),last=('last','max'),rows=('rows','sum')).reset_index()
    days=pd.to_datetime(pd.read_csv(ROOT/'BAR_DAY_COVERAGE.csv').trade_date).to_numpy()
    sy['observed_market_union_sessions_between_first_last']=np.searchsorted(days,sy['last'].to_numpy(),side='right')-np.searchsorted(days,sy['first'].to_numpy(),side='left')
    sy['internal_missing_rows_unknown_reason']=sy.observed_market_union_sessions_between_first_last-sy.rows
    assert sy.internal_missing_rows_unknown_reason.ge(0).all()
    sy.to_csv(ROOT/'SYMBOL_YEAR_OBSERVED_ENVELOPE_GAPS.csv',index=False)
    gap=sy.groupby('year').agg(rows=('rows','sum'),symbols=('symbol','nunique'),internal_missing_rows=('internal_missing_rows_unknown_reason','sum'),symbols_with_internal_gap=('internal_missing_rows_unknown_reason',lambda z:int(z.gt(0).sum())))
    gap.to_csv(ROOT/'YEAR_INTERNAL_GAPS_UNKNOWN_REASON.csv')
    z=dict(status='COMPLETE_ONE_EXISTING_TABLE_READ_ONLY',source=str(SOURCE),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),counts=dict(counts),sources=dict(sources),
      amount_volume_close_ratio_sample=dict(n=len(ratios),q10=float(np.quantile(ratios,.1)),median=float(np.median(ratios)),q90=float(np.quantile(ratios,.9)),meaning='Empirical unit sanity only, not proof of provider currency/volume units'),
      gaps='Within observed first/last date of each symbol/year against union of observed table dates, not official trading calendar or listing interval. Missing reason UNKNOWN, no claim all gaps are suspensions; prefirst/postlast gaps not counted.',
      bad_examples=examples,elapsed_seconds=time.monotonic()-start,new_market_data_downloads=0,new_accounts=0)
    (ROOT/'QUALITY_SCAN.json').write_text(json.dumps(z,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in z.items()if k not in ['bad_examples']},ensure_ascii=False,indent=2));print(gap.loc[2022:].to_string())

if __name__=='__main__':main()
