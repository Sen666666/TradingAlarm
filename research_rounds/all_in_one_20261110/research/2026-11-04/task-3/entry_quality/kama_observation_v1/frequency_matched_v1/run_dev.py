"""Development-only frequency lock. No validation outcomes or account engine."""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import argparse
import json
import hashlib
import sys
import time
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
SHARED=BASE.parent/'channel_atr_fsm_v1'
sys.path.insert(0,str(BASE));sys.path.insert(0,str(SHARED))
import engine
import runner
import kama
import core

DEV_END='2023-12-31'
PAIR_RUNS=[SHARED/'shard_a/run_v1',SHARED/'shard_b/run_v1']


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(engine.clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def read_dev(meta):
    price=Path(next(p for p in meta['source_sha256'] if p.endswith('/signal.parquet')))
    paths={'price':price,'native':Path(meta['refs']['facts']),'cp_input':Path(meta['refs']['CP1_input'])}
    source={}
    data={}
    for label,path in paths.items():
        expected=meta['source_sha256'].get(str(path),meta['output_sha256'].get(str(path)))
        actual=sha(path)
        if expected!=actual:raise ValueError('source SHA mismatch '+str(path))
        source[str(path)]=actual
        # Predicate read prevents even materializing 2024/validation observations.
        f=pd.read_parquet(path,filters=[('date','<=',pd.Timestamp(DEV_END))])
        f.index=pd.DatetimeIndex(f.index).as_unit('ns').normalize()
        assert f.empty or str(f.index.max().date())<=DEV_END
        assert f.index.is_unique and f.index.is_monotonic_increasing
        data[label]=f
    return data,source


def worker(task):
    slot,sids,out=task;out=Path(out)
    metas={x['symbol']:x for x in json.loads(runner.MANIFEST.read_text())}
    counts={k:np.zeros(478,dtype=np.int64) for k in ['protection','I_competing','no_exit20','protection_commonP0','protection_I_raised','protection_band_raised']}
    gates=Counter();reports=[];errors=[];common_n=0;started=time.monotonic()
    for number,sid in enumerate(sids):
        try:
            anchors=[];pair_sha={}
            for root in PAIR_RUNS:
                path=root/sid.replace('.','_')/'CP_ANCHOR_PAIRS.json'
                if path.exists():
                    pair_sha[str(path)]=sha(path)
                    # Never access saved future exits, strong labels or returns.
                    for p in json.loads(path.read_text()):
                        if '2022-01-01'<=p['anchor_day']<=DEV_END:
                            slim={k:p.get(k) for k in ['sid','anchor_day','anchor_id','status','P0']}
                            slim['entry_reference']={'next_observation_day':(p.get('entry_reference')or{}).get('next_observation_day')}
                            anchors.append(slim)
            if not anchors:
                reports.append(dict(sid=sid,status='NO_DEVELOPMENT_RAW_ANCHOR',raw_anchors=0,common_n=0));continue
            data,bindings=read_dev(metas[sid]);price=data['price']
            features=engine.features(price)
            indicators=kama.calculate(price,features)
            emas,weights=core.ema_matrix(price,indicators)
            a=core.arrays(price,features,data['native'],indicators,emas,weights)
            local=Counter();n=0
            for pair in anchors:
                status,common=core.common_anchor(pair,a)
                gates[status]+=1;local[status]+=1
                if common is None:continue
                n+=1;common_n+=1
                result=core.evaluate(common,a)
                for name,value in result.items():counts[name]+=value
            reports.append(dict(sid=sid,status='COMPLETE',raw_anchors=len(anchors),common_n=n,
                gates=dict(local),source_sha256=bindings,pair_source_sha256=pair_sha,
                maximum_computed_price_day=None if price.empty else str(price.index.max().date()),
                validation_data_not_computed=True))
        except Exception as error:
            errors.append(dict(sid=sid,error=repr(error)))
        if (number+1)%50==0:print(json.dumps(dict(worker=slot,completed=number+1,total=len(sids),errors=len(errors),seconds=time.monotonic()-started)),flush=True)
    save(out/f'WORKER_{slot}.json',dict(worker=slot,reports=reports,errors=errors,common_n=common_n,gates=dict(gates),
        counts={k:v.tolist()for k,v in counts.items()},seconds=time.monotonic()-started))
    return dict(worker=slot,common_n=common_n,errors=len(errors),raw_anchors=sum(x['raw_anchors']for x in reports),seconds=time.monotonic()-started)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--out',type=Path,required=True);parser.add_argument('--processes',type=int,default=3)
    args=parser.parse_args();assert args.processes==3
    args.out.mkdir(exist_ok=False)
    files=[HERE/'FREEZE.md',HERE/'core.py',Path(__file__),BASE/'kama.py',SHARED/'engine.py',runner.MANIFEST]
    bindings={str(p.resolve()):sha(p) for p in files}
    save(args.out/'RUN_START.json',dict(source_sha256=bindings,phase='DEV_FREQUENCY_COUNTS_ONLY',period_grid=core.PERIODS.tolist(),source_cutoff=DEV_END))
    sids=sorted(x['symbol']for x in json.loads(runner.MANIFEST.read_text()))
    started=time.monotonic()
    tasks=[(i,sids[i::3],str(args.out.resolve()))for i in range(3)]
    with ProcessPoolExecutor(max_workers=3)as pool:workers=list(pool.map(worker,tasks))
    if any(x['errors']for x in workers):
        save(args.out/'RUN_RECEIPT.json',dict(status='PARTIAL_ERROR_NO_RETRY',workers=workers,source_sha256=bindings));raise SystemExit('No retry; inspect preserved errors')
    inputs=[json.loads((args.out/f'WORKER_{i}.json').read_text())for i in range(3)]
    assert sum(x['raw_anchors']for x in workers)==35713,'development raw mother changed'
    n=sum(x['common_n']for x in inputs);gates=Counter()
    for x in inputs:gates.update(x['gates'])
    totals={name:np.sum([np.asarray(x['counts'][name],dtype=np.int64)for x in inputs],axis=0)for name in inputs[0]['counts']}
    records=[]
    for j,period in enumerate([None,*core.PERIODS.tolist()]):
        records.append(dict(arm='KAMA'if period is None else'EMA',period=period,common_n=n,
            **{name:int(value[j])for name,value in totals.items()},
            protection_frequency=None if not n else int(totals['protection'][j])/n))
    save(args.out/'DEVELOPMENT_FREQUENCY_COUNTS.json',dict(common_n=n,gate_counts=dict(gates),arms=records,workers=workers))
    if not n:
        lock=dict(status='NO_COMMON_EVALUABLE_ANCHORS_STOP_VALIDATION',period=None)
    else:
        target=int(totals['protection'][0]);distance=np.abs(totals['protection'][1:]-target)
        best=int(np.flatnonzero(distance==distance.min())[-1]);period=int(core.PERIODS[best])
        error_pp=100*int(distance[best])/n
        lock=dict(status='LOCKED_FOR_VALIDATION'if error_pp<=1. else'FREQUENCY_MISMATCH_GT1PP_STOP_VALIDATION',period=period,
            KAMA_protection_count=target,EMA_protection_count=int(totals['protection'][best+1]),common_n=n,
            absolute_frequency_error_percentage_points=error_pp,selection='min absolute integer protection count difference; ties larger period',
            validation_warm='KAMA and lockedEMA seed residual <=1%; separate dev-style EMA480 metadata subgroup',
            development_only=True,validation_outcomes_used=False,source_sha256=bindings)
    assert all(sha(p)==h for p,h in bindings.items()),'source changed; preserve outputs'
    save(args.out/'LOCK_EMA.json',lock)
    save(args.out/'RUN_RECEIPT.json',dict(status='COMPLETE_DEVELOPMENT_COUNTS_ONLY',workers=workers,common_n=n,
        raw_anchors=sum(x['raw_anchors']for x in workers),gate_counts=dict(gates),source_sha256=bindings,
        EMA_lock_status=lock['status'],elapsed_seconds=time.monotonic()-started,
        new_accounts=0,new_orders=0,new_quantities=0,new_returns=0,validation_observation_values_materialized_or_used=False))
    print(json.dumps(lock),flush=True)


if __name__=='__main__':main()
