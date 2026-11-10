"""Build causal features from local bars without claiming executable stock returns."""
import json
from pathlib import Path
import pandas as pd
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from stock_signal_data import stock_features
ROOT=Path(__file__).resolve().parent
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
OUT=ROOT/'data/stock-features';OUT.mkdir(exist_ok=True)

def grouped(pfile,columns):
    carry=pd.DataFrame();last=None
    for batch in pfile.iter_batches(batch_size=150000,columns=columns):
        frame=pd.concat([carry,batch.to_pandas()],ignore_index=True)
        if not frame.symbol.is_monotonic_increasing:raise ValueError('input not symbol sorted')
        final=frame.symbol.iloc[-1]
        carry=frame[frame.symbol.eq(final)].copy()
        for symbol,group in frame[frame.symbol.ne(final)].groupby('symbol',sort=False):
            if last is not None and symbol<=last:raise ValueError('repeated symbol across chunks')
            last=symbol;yield symbol,group
    if len(carry):yield str(carry.symbol.iloc[0]),carry

def main():
    master=pd.read_csv(ROOT/'results/stock-data-audit/master-crosswalk.csv',dtype={'symbol':str}).set_index('symbol')
    file=pq.ParquetFile(SOURCE)
    dates=set()
    for batch in file.iter_batches(batch_size=500000,columns=['trade_date']):
        dates.update(pd.to_datetime(batch.column(0).to_pandas()).unique())
    calendar=pd.DatetimeIndex(sorted(dates));calendar=calendar[calendar>=pd.Timestamp('2013-01-01')]
    columns=['symbol','trade_date','open','high','low','close','amount','volume','reference_adjustment_factor']
    writer=None;records=[];count=0
    temp=OUT/'local-features.tmp.parquet';target=OUT/'local-features.parquet'
    try:
        for symbol,group in grouped(file,columns):
            if symbol not in master.index:continue
            group=group.set_index('trade_date').sort_index()
            if group.index.duplicated().any():raise ValueError('duplicate bar:'+symbol)
            group=group.loc[group.index>=pd.Timestamp('2013-01-01')]
            if group.empty:continue
            idx=calendar[(calendar>=group.index.min())&(calendar<=group.index.max())]
            frame=group.reindex(idx)
            observed=frame.close.notna()
            for key in ['open','high','low','close']:
                frame['signal_'+key]=(frame[key]*frame.reference_adjustment_factor).where(observed)
            lastclose=frame.signal_close.ffill()
            for key in ['open','high','low','close']:
                frame['signal_'+key]=frame['signal_'+key].fillna(lastclose)
            frame['amount']=frame.amount.fillna(0)*1000
            frame['volume']=frame.volume.fillna(0)*100
            features=stock_features(frame)
            # Missing observed-market sessions cannot fill; exact ST/limits remain unknown.
            features['observed_bar']=observed
            features['positive_volume']=frame.volume.gt(0)
            features['signal_close']=frame.signal_close
            features['symbol']=symbol
            features['date']=features.index
            features=features.loc[features.index>=pd.Timestamp('2015-01-01')].reset_index(drop=True)
            if features.empty:continue
            if not np.isfinite(features.signal_close).all():raise ValueError('invalid close:'+symbol)
            table=pa.Table.from_pandas(features,preserve_index=False)
            if writer is None:writer=pq.ParquetWriter(temp,table.schema,compression='zstd')
            writer.write_table(table)
            count+=1
            records.append(dict(symbol=symbol,rows=len(features),missing_bar_sessions=int((~features.observed_bar).sum()),entry_days=int((features.entry_signal&features.warmup_ready&features.observed_bar&features.positive_volume).sum())))
            if count%500==0:print('symbols',count,flush=True)
    finally:
        if writer is not None:writer.close()
    if not count:raise ValueError('no features')
    temp.replace(target)
    report=dict(source=str(SOURCE),symbols=count,rows=sum(x['rows'] for x in records),
                calendar='Union of locally observed market dates; exchange-calendar completeness not certified.',
                input_price='Stored qfq multiplied by per-symbol reference factor to recover raw price times contemporaneous factor; provider revisions not point-in-time certified.',
                execution_ready=False,limitations=['Survivor-biased local source until retired histories merged','Missing bar is non-executable, not automatically certified suspension','Historical ST/price limits and cash/share corporate actions pending','No account returns calculated'],records=records)
    (OUT/'manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
