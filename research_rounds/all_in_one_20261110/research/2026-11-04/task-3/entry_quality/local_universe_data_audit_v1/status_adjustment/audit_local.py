"""Bounded local-file audit only. Never imports builders or opens network clients."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import os
import time
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pyarrow.dataset as ds

HERE=Path(__file__).resolve().parent
ROOT=Path('/Users/bytedance/repos/my-quant')
DATA=ROOT/'data'
PATHS={
    'suspend_status':DATA/'processed/factors/suspend_status/suspend_status.parquet',
    'adjusted_daily_bars':DATA/'processed/adjusted_daily_bars/adjusted_daily_bars.parquet',
    'adjustment_factors':DATA/'processed/adjustment_factors/adjustment_factors.parquet',
    'securities':DATA/'processed/securities/securities.parquet',
    'daily_bars_history':DATA/'processed/daily_bars_history/daily_bars.parquet',
}


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v)for v in x]
    if isinstance(x,(pd.Timestamp,np.datetime64)):return str(pd.Timestamp(x))
    if isinstance(x,np.generic):x=x.item()
    if x is None or x is pd.NA or x is pd.NaT:return None
    return None if isinstance(x,float)and not np.isfinite(x)else x


def save(name,x):
    (HERE/name).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def scan(name,path):
    before=path.stat();f=pq.ParquetFile(path)
    symbols=set();years=Counter();nulls=Counter();nonfinite=Counter();nonpositive=Counter()
    values={};date_min={};date_max={};future_refs=0;rows=0
    for b in f.iter_batches(batch_size=262144):
        rows+=len(b)
        for field,c in zip(b.schema,b.columns):
            key=field.name;nulls[key]+=c.null_count
            if key=='symbol':symbols.update(c.drop_null().unique().to_pylist())
            if pa.types.is_timestamp(field.type):
                dates=c.to_numpy(zero_copy_only=False).astype('datetime64[ns]');ok=~np.isnat(dates)
                if ok.any():
                    lo=str(dates[ok].min())[:10];hi=str(dates[ok].max())[:10]
                    date_min[key]=min(date_min.get(key,lo),lo);date_max[key]=max(date_max.get(key,hi),hi)
                    if key=='trade_date':
                        yy,n=np.unique(dates[ok].astype('datetime64[Y]').astype(int)+1970,return_counts=True)
                        years.update(dict(zip(map(int,yy),map(int,n))))
            elif pa.types.is_floating(field.type) or pa.types.is_integer(field.type):
                a=c.to_numpy(zero_copy_only=False);finite=np.isfinite(a)
                nonfinite[key]+=int((~finite).sum());nonpositive[key]+=int((finite&(a<=0)).sum())
            elif key in {'adjustment_type','source','suspend_types','is_suspended','is_resumed'}:
                counter=values.setdefault(key,Counter());counter.update(c.to_pylist())
        if 'reference_trade_date'in b.schema.names:
            a=b.column(b.schema.get_field_index('reference_trade_date')).to_numpy(zero_copy_only=False).astype('datetime64[ns]')
            t=b.column(b.schema.get_field_index('trade_date')).to_numpy(zero_copy_only=False).astype('datetime64[ns]')
            future_refs+=int((a>t).sum())
    after=path.stat();assert before.st_size==after.st_size and before.st_mtime_ns==after.st_mtime_ns
    return dict(path=str(path),rows=rows,symbols=len(symbols),schema=[dict(name=x.name,type=str(x.type))for x in f.schema_arrow],
                row_groups=f.metadata.num_row_groups,file_bytes=before.st_size,mtime_ns=before.st_mtime_ns,
                dates={k:dict(min=date_min[k],max=date_max[k])for k in date_min},rows_by_trade_year=dict(years),
                null_counts=dict(nulls),numeric_nonfinite_counts=dict(nonfinite),numeric_nonpositive_counts=dict(nonpositive),
                categorical_counts={k:dict(v)for k,v in values.items()},reference_later_than_row=future_refs,
                sha256=sha(path),unchanged_during_scan=True)


def file_inventory():
    # Filenames only, not every raw table. Never reads token/config files.
    inventories={};matches=[]
    needles=('namechange','name_change','corporate_action','stock_basic','dividend','st_status')
    for area in ['raw','meta','processed']:
        counts=Counter()
        for base,dirs,files in os.walk(DATA/area):
            for n in dirs:
                rel=str((Path(base)/n).relative_to(DATA))
                if any(s in n.lower()for s in needles):matches.append(dict(kind='directory',path=rel))
            for n in files:
                p=Path(base)/n;rel=p.relative_to(DATA)
                if area=='raw':group='/'.join(rel.parts[:5])
                else:group='/'.join(rel.parts[:3])
                counts[group]+=1
                if any(s in n.lower()for s in needles):matches.append(dict(kind='file',path=str(rel)))
        inventories[area]=dict(counts)
    rawsamples=[]
    for group in [DATA/'raw/tushare/a_share/suspend_status', DATA/'raw/tushare/a_share/adjustment_factors', DATA/'raw/tushare/a_share/daily_bars']:
        paths=sorted(group.rglob('*.parquet'))
        if not paths:continue
        p=paths[0];f=pq.ParquetFile(p);head=f.read_row_group(0).slice(0,3).to_pandas()
        rawsamples.append(dict(path=str(p),parquet_files_in_group=len(paths),rows=f.metadata.num_rows,
                               schema=[dict(name=x.name,type=str(x.type))for x in f.schema_arrow],head=head.to_dict('records')))
    return dict(file_counts=inventories,matching_filename_or_directory=matches,raw_table_samples=rawsamples,
                absent_name_does_not_prove_absence_in_unrelated_uninspected_paths=True)


def main():
    assert not(HERE/'DATA_AUDIT.json').exists()
    start=time.monotonic();results={}
    for name,path in PATHS.items():
        results[name]=scan(name,path)
        print(json.dumps(dict(scanned=name,rows=results[name]['rows'],symbols=results[name]['symbols'],seconds=time.monotonic()-start)),flush=True)
    suspend=pd.read_parquet(PATHS['suspend_status']);securities=pd.read_parquet(PATHS['securities'])
    results['suspend_status']['all_rows']=suspend.to_dict('records')
    results['suspend_status']['flag_counts']={k:suspend[k].value_counts(dropna=False).to_dict()for k in ['is_suspended','is_resumed','suspend_event_count']}
    st=securities.name.astype('string').str.contains('ST',case=False,na=False)
    results['securities']['current_snapshot_ST_name_count']=int(st.sum())
    results['securities']['ST_name_examples']=securities.loc[st].head(8).to_dict('records')
    results['securities']['specific_names']=securities.loc[securities.symbol.isin(['000620.SZ','002583.SZ','600734.SH'])].to_dict('records')
    # One fixed small observed-price example: compare persisted raw vs qfq and
    # factors. No simulated orders or reconstructed adjusted path.
    samples={}
    for sid in ['000620.SZ','002583.SZ']:
        got={}
        for name in ['daily_bars_history','adjusted_daily_bars','adjustment_factors']:
            frame=ds.dataset(PATHS[name]).to_table(filter=(ds.field('symbol')==sid)&(ds.field('trade_date')>=pd.Timestamp('2022-01-01'))&(ds.field('trade_date')<=pd.Timestamp('2022-01-26'))).to_pandas()
            got[name]=frame.head(3).to_dict('records')
        samples[sid]=got
    save('DATA_AUDIT.json',results)
    save('RAW_META_INVENTORY.json',file_inventory())
    save('FIXED_EXISTING_ROWS.json',samples)
    files=[ROOT/'src/my_quant/data/builders/suspend_status_factors.py',ROOT/'src/my_quant/data/builders/adjustment_factors.py',
           ROOT/'src/my_quant/data/builders/adjusted_daily_bars.py',ROOT/'src/my_quant/data/adjustments.py',
           ROOT/'src/my_quant/data/cleaning.py',ROOT/'src/my_quant/data/sources/__init__.py',Path(__file__)]
    save('AUDIT_RECEIPT.json',dict(status='COMPLETE_BOUNDED_LOCAL_READ_ONLY',elapsed_seconds=time.monotonic()-start,
         source_sha256={str(p):sha(p)for p in files},local_download_calls=0,refresh_runs=0,backtests=0,
         inspected_processed_tables=list(PATHS),raw_samples_only=True,no_st_or_suspension_false_imputation=True))
    print(json.dumps(dict(status='COMPLETE',seconds=time.monotonic()-start)),flush=True)


if __name__=='__main__':main()
