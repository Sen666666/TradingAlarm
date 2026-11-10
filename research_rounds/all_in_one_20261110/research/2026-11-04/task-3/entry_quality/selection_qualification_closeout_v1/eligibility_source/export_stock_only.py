"""One six-worker fixed-date original E0/G1_I signal export; never S0/account."""
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor,as_completed
import multiprocessing as mp
import hashlib,json,time
import numpy as np
import pandas as pd
import pyarrow.dataset as ds
import stock_signal as pure

HERE=Path(__file__).resolve().parent
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
DAY='2024-09-24'
COLS=['symbol','trade_date','open','high','low','close','volume','amount','adjustment_factor','raw_adjustment_factor','reference_adjustment_factor','reference_trade_date','source']


def clean(x):
    if isinstance(x,dict):return {str(k):clean(v)for k,v in x.items()}
    if isinstance(x,(list,tuple)):return [clean(v)for v in x]
    if isinstance(x,(pd.Timestamp,np.datetime64)):return str(pd.Timestamp(x))
    if isinstance(x,np.generic):x=x.item()
    if x is None or x is pd.NA or x is pd.NaT:return None
    return None if isinstance(x,float)and not np.isfinite(x)else x


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        for b in iter(lambda:f.read(8*1024*1024),b''):h.update(b)
    return h.hexdigest()


def save(path,value):Path(path).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def worker(shard,symbols):
    started=time.monotonic();dataset=ds.dataset(SOURCE)
    frame=dataset.to_table(columns=COLS,filter=ds.field('symbol').isin(symbols)&(ds.field('trade_date')<=pd.Timestamp(DAY))).to_pandas()
    groups={sid:g for sid,g in frame.groupby('symbol',sort=False)}
    statuses=Counter();rows=[];path=HERE/f'SHARD_{shard}_STOCK_SIGNAL.jsonl'
    assert not path.exists()
    with path.open('x')as out:
        for number,sid in enumerate(symbols):
            begin=time.monotonic();g=groups.get(sid,pd.DataFrame(columns=COLS)).sort_values('trade_date')
            record=dict(sid=sid,day=DAY,input_prefix_rows=len(g),target_source_row_present=False,
                        signal_status='NO_SOURCE_PREFIX',S0_eligibility_q=None,
                        S0_status='NOT_EVALUATED_STOCK_ONLY_NO_INVENTED_CAP_SECTOR_OR_MARKET_FACTS')
            try:
                if len(g):
                    assert g.source.nunique(dropna=False)==1 and g.source.notna().all()
                    record['source_first_day']=str(g.trade_date.iloc[0].date());record['source_last_prefix_day']=str(g.trade_date.iloc[-1].date())
                    current=g.loc[g.trade_date.eq(pd.Timestamp(DAY))]
                    record['target_source_row_present']=not current.empty
                    signal=g.set_index('trade_date')[['open','high','low','close','volume']].copy();signal['segment_id']=0
                    f=pure.calculate(signal);record['eligible_price_observations']=len(f)
                    if len(f):
                        record['last_observed_signal_day']=str(f.index[-1].date())
                        for k,v in f.iloc[-1].to_dict().items():record['last_observed_'+k]=v
                    if pd.Timestamp(DAY)in f.index:
                        record.update(f.loc[pd.Timestamp(DAY)].to_dict());record['signal_status']='EXACT_TARGET_STOCK_SIGNAL'
                        row=current.iloc[0]
                        for name in ['amount','adjustment_factor','raw_adjustment_factor','reference_adjustment_factor','reference_trade_date']:
                            record[name]=row[name]
                        record['stock_hold_signal']=bool(record['i_target'])if bool(record['e0_ready'])else None
                        record['stock_fresh_core_signal']=bool(record['i_target'] and record['i_buy'])if bool(record['e0_ready'])else None
                    else:
                        record['signal_status']='MISSING_TARGET_BAR'if current.empty else'REJECTED_BY_ORIGINAL_ELIGIBLE_PRICE_MASK'
            except Exception as e:
                record['signal_status']='SOURCE_OR_PURE_SIGNAL_ERROR';record['error']=repr(e)
            record['compute_seconds']=time.monotonic()-begin
            record=clean(record);rows.append(record);out.write(json.dumps(record,ensure_ascii=False,allow_nan=False)+'\n');out.flush()
            statuses[record['signal_status']]+=1
            save(HERE/f'SHARD_{shard}_PROGRESS.json',dict(shard=shard,completed_symbols=number+1,total_symbols=len(symbols),
                 status_counts=dict(statuses),seconds=time.monotonic()-started,last_sid=sid,errors=int(statuses['SOURCE_OR_PURE_SIGNAL_ERROR'])))
    return dict(shard=shard,rows=len(rows),seconds=time.monotonic()-started,status_counts=dict(statuses),output_sha256=sha(path))


def main():
    assert not(HERE/'FULL_SIGNAL_RUN_STARTED.json').exists()
    started=time.monotonic();stat=SOURCE.stat()
    dataset=ds.dataset(SOURCE);all_symbols=sorted(dataset.to_table(columns=['symbol']).column('symbol').unique().to_pylist());assert len(all_symbols)==5517
    counts=dataset.to_table(columns=['symbol'],filter=ds.field('trade_date')<=pd.Timestamp(DAY)).column('symbol').value_counts().to_pylist()
    lengths={x['values']:int(x['counts'])for x in counts}
    buckets=[[]for _ in range(6)];loads=[0]*6
    for sid in sorted(all_symbols,key=lambda s:(-lengths.get(s,0),s)):
        k=min(range(6),key=lambda k:(loads[k],len(buckets[k]),k));buckets[k].append(sid);loads[k]+=lengths.get(sid,0)
    sources=[SOURCE,Path(pure.__file__),Path(__file__),pure.RR/'pv-participation-response-20261020/code/numeric.py',
        pure.RR/'pv-participation-response-20261020/code/participation.py',pure.RR/'pv-participation-response-20261020/code/data_utils.py',
        pure.RR/'pv-strength-b5-20261025/code/evidence.py',pure.RR/'pv-strength-b5-20261025/code/policy.py',
        pure.RR/'pv-strength-b5-20261025/code/arithmetic.py',pure.RR/'pv-strength-b4-20261025/code/model.py',
        pure.RR/'b5-g1-20261025/code/grade.py',pure.RR/'b5-g1-20261025/code/policies_g1.py']
    hashes={str(p):sha(p)for p in sources}
    save(HERE/'FULL_SIGNAL_RUN_STARTED.json',dict(day=DAY,symbols=5517,processes=6,total_source_prefix_rows=sum(lengths.values()),
        per_shard_source_rows=loads,source_sha256=hashes,source_file_bytes=stat.st_size,source_mtime_ns=stat.st_mtime_ns,
        decline_candidate=False,I_kind='G1_I',signal_scope='STOCK_ONLY_NOT_S0',no_future_rows=True,new_accounts=0,new_parameters=0))
    receipts=[]
    with ProcessPoolExecutor(max_workers=6,mp_context=mp.get_context('spawn'))as pool:
        futures=[pool.submit(worker,k,b)for k,b in enumerate(buckets)]
        for f in as_completed(futures):
            receipts.append(f.result());save(HERE/'FINISHED_SHARDS.json',receipts)
    records=[]
    for k in range(6):
        with(HERE/f'SHARD_{k}_STOCK_SIGNAL.jsonl').open()as stream:records.extend(json.loads(x)for x in stream)
    out=pd.DataFrame(records).sort_values('sid').reset_index(drop=True)
    assert len(out)==5517 and not out.sid.duplicated().any()and sorted(out.sid)==all_symbols
    out.to_parquet(HERE/'STOCK_ONLY_2024_09_24.parquet',index=False,compression='zstd')
    assert SOURCE.stat().st_size==stat.st_size and SOURCE.stat().st_mtime_ns==stat.st_mtime_ns
    for path,h in hashes.items():
        if path.endswith('.py'):assert sha(path)==h,('code changed during single fixed export',path)
    exact=out.signal_status.eq('EXACT_TARGET_STOCK_SIGNAL');good=out.loc[exact]
    save(HERE/'FULL_SIGNAL_RECEIPT.json',dict(status='COMPLETE_SINGLE_FIXED_STOCK_ONLY_SIGNAL_EXPORT',rows=len(out),day=DAY,
        status_counts=out.signal_status.value_counts().to_dict(),exact_target=int(exact.sum()),
        e0_ready=int(good.e0_ready.eq(1).sum()),e0_target=int(good.e0_target.eq(1).sum()),i_target=int(good.i_target.eq(1).sum()),
        i_buy=int(good.i_buy.eq(True).sum()),fresh_core_signal=int(good.stock_fresh_core_signal.eq(True).sum()),
        output_sha256=sha(HERE/'STOCK_ONLY_2024_09_24.parquet'),source_sha256=hashes,worker_receipts=receipts,
        elapsed_seconds=time.monotonic()-started,new_accounts=0,new_orders=0,new_rankings=0,full_S0_evaluated=False))
    print(json.dumps(dict(status='COMPLETE',rows=len(out),seconds=time.monotonic()-started)),flush=True)


if __name__=='__main__':main()
