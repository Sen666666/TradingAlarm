"""One fixed 3-process local export. No account, ranking, labels or network."""
from pathlib import Path
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import multiprocessing as mp
import hashlib
import json
import time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import pyarrow.dataset as ds
import derive

HERE=Path(__file__).resolve().parent
SOURCE=Path('/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet')
RAW=Path('/Users/bytedance/repos/my-quant/data/processed/daily_bars_history/daily_bars.parquet')
PROBES={'000620.SZ','002583.SZ','300666.SZ','300085.SZ'}
PREFIX={'000620.SZ':'2022-01-10','002583.SZ':'2024-09-24','300666.SZ':'2026-01-15'}
COLS=['symbol','trade_date','close','amount','source','adjustment_factor','raw_adjustment_factor','reference_adjustment_factor','reference_trade_date']


def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb')as f:
        for x in iter(lambda:f.read(8*1024*1024),b''):h.update(x)
    return h.hexdigest()


def save(n,v):
    (HERE/n).write_text(json.dumps(v,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def bits_equal(x,y):
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float);known=np.isfinite(x)&np.isfinite(y)
    return np.array_equal(np.isfinite(x),np.isfinite(y)) and np.array_equal(x[known].view(np.uint64),y[known].view(np.uint64))


def worker(shard,symbols):
    started=time.monotonic()
    frame=ds.dataset(SOURCE).to_table(columns=COLS,filter=(ds.field('symbol')>=symbols[0])&(ds.field('symbol')<=symbols[-1])).to_pandas()
    assert sorted(frame.symbol.unique())==symbols
    result=[];prefixes=[];references=[];checks=[]
    for count,(sid,g)in enumerate(frame.groupby('symbol',sort=True)):
        g=g.sort_values('trade_date').reset_index(drop=True);full=derive.calculate(g);selected=derive.selected_rows(sid,g,full);result.append(selected)
        if sid in PREFIX:
            cutoff=pd.Timestamp(PREFIX[sid]);short=g.loc[g.trade_date<=cutoff].copy();a=derive.calculate(short)
            assert a.equals(full.loc[a.index]),(sid,'true prefix mismatch')
            prefixes.append(dict(sid=sid,cutoff=str(cutoff.date()),full_rows=len(g),prefix_rows=len(short),all_columns_common_prefix_exact=True))
        if sid in PROBES:
            sig=g.set_index('trade_date')[['close','amount']].copy();sig['segment_id']=0
            ref=derive.reference(sig);per={}
            for field in derive.FLOATS:
                assert bits_equal(ref[field],full[field]),(sid,field,'independent reference mismatch')
                per[field]=int(np.isfinite(ref[field]).sum())
            references.append(dict(sid=sid,source_rows=len(sig),all10_columns_all_rows_bitexact=True,finite_counts=per))
            ev=selected[['sid','day','r','scale','amount_ref','u','b','e','E','score','E_fast','E_slow','pvr_status','fast_status','slow_status']]
            checks.extend(ev.replace({np.nan:None}).to_dict('records'))
        if(count+1)%300==0:print(json.dumps(dict(shard=shard,symbols_completed=count+1,seconds=time.monotonic()-started)),flush=True)
    out=pd.concat(result,ignore_index=True)
    out.to_parquet(HERE/f'SHARD_{shard}.parquet',index=False,compression='zstd')
    return dict(shard=shard,symbols=len(symbols),rows=len(out),prefixes=prefixes,references=references,
                seconds=time.monotonic()-started)


def main():
    assert not(HERE/'LOCAL_FIXED_DATE_FEATURES.parquet').exists()
    started=time.monotonic();before={str(p):dict(bytes=p.stat().st_size,mtime_ns=p.stat().st_mtime_ns,sha256=sha(p))for p in [SOURCE,RAW]}
    symbols=sorted(pq.read_table(SOURCE,columns=['symbol']).column('symbol').unique().to_pylist());assert len(symbols)==5517
    save('RUN_STARTED.json',dict(symbols=5517,dates=derive.TARGETS,expected_rows=38619,processes=3,sources=before,
         code_sha256={str(p):sha(p)for p in [derive.ORIGINAL,Path(derive.__file__),Path(__file__)]},new_accounts=0,future_labels=False))
    pieces=[list(x)for x in np.array_split(np.asarray(symbols),3)]
    with ProcessPoolExecutor(max_workers=3,mp_context=mp.get_context('spawn'))as pool:
        futures=[pool.submit(worker,i,s)for i,s in enumerate(pieces)]
        receipts=[f.result()for f in futures]
    out=pd.concat([pd.read_parquet(HERE/f'SHARD_{i}.parquet')for i in range(3)],ignore_index=True)
    out=out.sort_values(['sid','day']).reset_index(drop=True)
    assert len(out)==38619 and out.sid.nunique()==5517 and not out.duplicated(['sid','day']).any()
    assert out.groupby('sid').size().eq(7).all()
    raw=ds.dataset(RAW).to_table(columns=['symbol','trade_date','close','volume','amount'],filter=ds.field('trade_date').isin([pd.Timestamp(x)for x in derive.TARGETS])).to_pandas()
    raw=raw.rename(columns={'symbol':'sid','close':'raw_close','volume':'raw_volume','amount':'raw_amount'})
    raw['day']=raw.trade_date.dt.strftime('%Y-%m-%d');raw=raw.drop(columns='trade_date')
    assert not raw.duplicated(['sid','day']).any()
    out=out.merge(raw,on=['sid','day'],how='left',validate='one_to_one')
    observed=out.target_row_present.to_numpy(bool)
    assert np.array_equal(observed,out.raw_close.notna().to_numpy()),'raw/qfq target presence differs'
    assert bits_equal(out.loc[observed,'current_amount_passthrough'],out.loc[observed,'raw_amount'])
    reconstructed=out.raw_close*out.qfq_adjustment_factor
    assert bits_equal(reconstructed[observed],out.loc[observed,'current_close_qfq'])
    assert bits_equal(out.raw_adjustment_factor/out.reference_adjustment_factor,out.qfq_adjustment_factor)
    out['qfq_price_raw_factor_crosscheck']=pd.arrays.BooleanArray(np.ones(len(out),dtype=bool),~observed)
    out.to_parquet(HERE/'LOCAL_FIXED_DATE_FEATURES.parquet',index=False,compression='zstd')
    for p in [SOURCE,RAW]:
        z=before[str(p)];assert p.stat().st_size==z['bytes'] and p.stat().st_mtime_ns==z['mtime_ns'],'source changed during export'
    summary={d:dict(rows=len(g),present=int(g.target_row_present.sum()),missing=int((~g.target_row_present).sum()),
               pvr_known=int(g.pvr_status.eq('KNOWN').sum()),e_known=int(g.e_status.eq('KNOWN').sum()),
               fast_known=int(g.fast_status.eq('KNOWN').sum()),slow_known=int(g.slow_status.eq('KNOWN').sum()),
               fast_only=int((g.fast_status.eq('KNOWN')&g.slow_status.ne('KNOWN')).sum()))for d,g in out.groupby('day')}
    save('PREFIX_CHECKS.json',[x for r in receipts for x in r['prefixes']])
    save('INDEPENDENT_REFERENCE_CHECKS.json',[x for r in receipts for x in r['references']])
    save('RUN_RECEIPT.json',dict(status='COMPLETE_FIXED_LOCAL_UNIVERSE_PURE_FEATURES',rows=len(out),symbols=5517,dates=derive.TARGETS,
         by_target=summary,worker_receipts=receipts,source_files=before,source_unchanged_during_export=True,
         code_sha256={str(p):sha(p)for p in [derive.ORIGINAL,Path(derive.__file__),Path(__file__)]},
         output_sha256=sha(HERE/'LOCAL_FIXED_DATE_FEATURES.parquet'),raw_qfq_amount_bitexact=True,raw_times_factor_price_bitexact=True,
         elapsed_seconds=time.monotonic()-started,new_accounts=0,new_rankings=0,future_labels_read=False,refresh_or_network_calls=0))
    print(json.dumps(dict(status='COMPLETE',rows=len(out),by_target=summary,seconds=time.monotonic()-started)),flush=True)


if __name__=='__main__':main()
