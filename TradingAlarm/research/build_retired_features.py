"""Prepare validated retired histories on a shared observed calendar for diagnostics."""
import json
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from audit_retired_readiness import inspect_history
from stock_signal_data import retired_signal_frame,stock_features
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data/stock-features'

def main():
 source=pq.ParquetFile(OUT/'local-features.parquet');schema=source.schema_arrow
 daily=pd.read_csv(ROOT/'results/stock-signal-v1/daily-candidate-counts.csv',index_col=0,parse_dates=True)
 dates=set(daily.index);histories=[];rejected=[]
 for path in sorted((ROOT/'data/retired-pilot').glob('*.json')):
  history=json.loads(path.read_text());symbol=history['symbol'];factor=ROOT/'data/retired-factors'/path.name
  check=inspect_history(history,history['master_record'])
  if not check['structurally_valid'] or not factor.exists():
   rejected.append(dict(symbol=symbol,reason=check.get('errors') or ['missing_factors']));continue
  try:
   frame=retired_signal_frame(history,json.loads(factor.read_text()))
   frame=frame.loc[(frame.index>=pd.Timestamp('2013-01-01'))&(frame.index<=daily.index.max())]
   dates.update(frame.index);histories.append((symbol,frame))
  except (ValueError,KeyError,TypeError) as exc:rejected.append(dict(symbol=symbol,reason=type(exc).__name__))
 calendar=pd.DatetimeIndex(sorted(dates));records=[]
 temp=OUT/'retired-features.tmp.parquet'
 with pq.ParquetWriter(temp,schema,compression='zstd') as writer:
  for symbol,raw in histories:
   if raw.empty:continue
   idx=calendar[(calendar>=raw.index.min())&(calendar<=raw.index.max())]
   frame=raw.reindex(idx);observed=frame.close.notna()
   lastclose=frame.signal_close.where(frame.signal_close>0).ffill()
   for key in ['open','high','low','close']:
    frame['signal_'+key]=frame['signal_'+key].where(frame['signal_'+key]>0).fillna(lastclose)
   frame['amount']=frame.amount.fillna(0)
   features=stock_features(frame)
   features['observed_bar']=observed
   features['positive_volume']=frame.volume.gt(0)&frame.tradestatus.eq('1')
   features['signal_close']=frame.signal_close
   features['symbol']=symbol;features['date']=features.index
   features=features.loc[features.index>=pd.Timestamp('2015-01-01')].reset_index(drop=True)
   if features.empty:continue
   writer.write_table(pa.Table.from_pandas(features,schema=schema,preserve_index=False))
   records.append(dict(symbol=symbol,rows=len(features),entry_days=int((features.entry_signal&features.warmup_ready&features.positive_volume).sum())))
 temp.replace(OUT/'retired-features.parquet')
 report=dict(included=len(records),rows=sum(x['rows'] for x in records),rejected=rejected,records=records,execution_ready=False,
  limitations=['Only currently repaired retired histories, not entire missing universe','No terminal payout or cash/share ledger','Observed calendar not exchange-certified','Provider-revised factor history','Future labels ending beyond last bar remain missing; do not call this survivor-free performance'])
 (OUT/'retired-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
 print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False,indent=2))

if __name__=='__main__':main()
