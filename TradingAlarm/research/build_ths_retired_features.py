"""THS retired signal diagnostic inputs; excludes unsupported actions and synthetic fills."""
import json
from pathlib import Path
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from ths_signal_adjustment import signal_frame
from stock_signal_data import stock_features
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'data/stock-features'

def main():
    local=pq.ParquetFile(OUT/'local-features.parquet')
    dates=set();local_symbols=set()
    for b in local.iter_batches(columns=['date','symbol']):
        f=b.to_pandas();dates.update(f.date);local_symbols.update(f.symbol.unique())
    last=max(dates);histories=[];rejected=[]
    for p in sorted((ROOT/'data/ths-raw').glob('*.json')):
        symbol=p.stem[4:]+('.SH' if p.stem[:4]=='USHD' else '.SZ')
        if p.stem[:4] not in ('USHD','USZD'):raise ValueError('unexpected namespace')
        if symbol in local_symbols:raise ValueError('duplicate instrument across sources: '+symbol)
        try:
            frame=signal_frame(json.loads(p.read_text()),json.loads((ROOT/'data/ths-rights'/p.name).read_text()))
            frame=frame.loc[:last]
            dates.update(frame.index[frame.observed_bar]);histories.append((symbol,frame))
        except (ValueError,KeyError,TypeError) as e:rejected.append(dict(symbol=symbol,reason=str(e)))
    calendar=pd.DatetimeIndex(sorted(dates));records=[]
    temp=OUT/'ths-retired-features.tmp.parquet'
    with pq.ParquetWriter(temp,local.schema_arrow,compression='zstd') as writer:
        for symbol,raw in sorted(histories):
            if raw.empty:continue
            idx=calendar[(calendar>=raw.index.min())&(calendar<=raw.index.max())]
            # Carry event adjustments across non-session event dates, without adding sessions.
            frame=raw.reindex(raw.index.union(idx)).sort_index()
            lastclose=frame.signal_close.ffill()
            for key in ['open','high','low','close']:frame['signal_'+key]=frame['signal_'+key].fillna(lastclose)
            frame=frame.reindex(idx)
            frame['amount']=frame.amount.fillna(0)
            features=stock_features(frame)
            features['observed_bar']=frame.observed_bar.eq(True)
            features['positive_volume']=frame.volume.gt(0)&features.observed_bar
            features['signal_close']=frame.signal_close
            features['symbol']=symbol;features['date']=features.index
            features=features.loc['2015-01-01':].reset_index(drop=True)
            if features.empty:continue
            writer.write_table(pa.Table.from_pandas(features,schema=local.schema_arrow,preserve_index=False))
            records.append(dict(symbol=symbol,rows=len(features),synthetic_events=int(raw.synthetic_event_bar.sum())))
    temp.replace(OUT/'ths-retired-features.parquet')
    report=dict(symbols=len(records),rows=sum(x['rows'] for x in records),rejected=rejected,records=records,execution_ready=False,limitations=['Incomplete historical universe and terminal payouts','Signal adjustments only, not cash/share returns','Unknown ST and historical price limits','Synthetic event marks never tradable; observed calendar not certified'])
    (OUT/'ths-retired-manifest.json').write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps({k:v for k,v in report.items() if k!='records'},ensure_ascii=False))
if __name__=='__main__':main()
