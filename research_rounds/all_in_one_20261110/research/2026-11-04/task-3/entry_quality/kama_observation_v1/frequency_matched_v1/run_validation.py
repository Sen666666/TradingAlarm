"""Locked single-EMA validation driver. No Account, order, sizing or fitting.

Import/compile is permitted before the development lock. Data computation is
only in main(), after exact development lock and source-binding validation.
"""
from pathlib import Path
from concurrent.futures import ProcessPoolExecutor
from collections import Counter
import argparse
import fcntl
import gzip
import hashlib
import json
import os
import sys
import time
import traceback

import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
BASE=HERE.parent
SHARED=BASE.parent/'channel_atr_fsm_v1'
sys.path.insert(0,str(BASE));sys.path.insert(0,str(SHARED));sys.path.insert(0,str(HERE))
import engine
import runner
import kama
import core

CAP='2026-06-30'
PAIR_RUNS=[SHARED/'shard_a/run_v1',SHARED/'shard_b/run_v1']
SEMI_RUN=SHARED/'semiconductor_full/run_v1'
GROUPS=('VALIDATION_2024_SEP_DEC','SEMICONDUCTOR_2025_2026H1')
FIXED_CASES={('002583.SZ','2024-09-20'),('300085.SZ','2024-09-12')}


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):Path(p).write_text(json.dumps(engine.clean(x),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def accepted_lock(path):
    """Frequency-only audit. Never reads validation prices or outcomes."""
    path=Path(path);lock=json.loads(path.read_text())
    assert lock['status']=='LOCKED_FOR_VALIDATION','No accepted development lock'
    assert lock['development_only'] is True and lock['validation_outcomes_used'] is False
    assert lock['absolute_frequency_error_percentage_points']<=1.
    assert lock['common_n']>0 and lock['period'] in core.PERIODS.tolist()
    assert np.array_equal(core.PERIODS,np.arange(4,481,dtype=int))
    for p,h in lock['source_sha256'].items():assert sha(p)==h,('locked source changed',p)
    receipt=json.loads((path.parent/'RUN_RECEIPT.json').read_text())
    assert receipt['status']=='COMPLETE_DEVELOPMENT_COUNTS_ONLY'
    assert receipt['validation_observation_values_materialized_or_used'] is False
    assert receipt['source_sha256']==lock['source_sha256']
    dev=json.loads((path.parent/'DEVELOPMENT_FREQUENCY_COUNTS.json').read_text())
    assert dev['common_n']==lock['common_n']
    arms=dev['arms'];assert len(arms)==478 and arms[0]['arm']=='KAMA'
    assert [r['period']for r in arms[1:]]==list(range(4,481))
    target=arms[0]['protection'];n=lock['common_n']
    minimum=min(abs(r['protection']-target)for r in arms[1:])
    expected=max(r['period']for r in arms[1:]if abs(r['protection']-target)==minimum)
    chosen=next(r for r in arms if r['period']==lock['period'])
    assert expected==lock['period'],'Lock violates frozen frequency-only/tie rule'
    assert target==lock['KAMA_protection_count'] and chosen['protection']==lock['EMA_protection_count']
    assert abs(100*minimum/n-lock['absolute_frequency_error_percentage_points'])<1e-12
    assert 100*minimum/n<=1.
    return lock


def read_validation(meta):
    price=Path(next(p for p in meta['source_sha256']if p.endswith('/signal.parquet')))
    paths={'price':price,'native':Path(meta['refs']['facts']),'cp_input':Path(meta['refs']['CP1_input'])}
    data={};bindings={}
    for label,path in paths.items():
        expected=meta['source_sha256'].get(str(path),meta['output_sha256'].get(str(path)))
        actual=sha(path)
        if actual!=expected:raise ValueError('source SHA mismatch '+str(path))
        bindings[str(path)]=actual
        f=pd.read_parquet(path,filters=[('date','<=',pd.Timestamp(CAP))])
        index=pd.DatetimeIndex(f.index)
        if index.tz is not None:index=index.tz_localize(None)
        f.index=index.as_unit('ns').normalize()
        assert f.index.is_unique and f.index.is_monotonic_increasing
        assert f.empty or str(f.index.max().date())<=CAP
        data[label]=f
    q=data['cp_input'];p=data['price'].reindex(q.index)
    if not np.array_equal(q.close.to_numpy(),p.close.to_numpy(),equal_nan=True):
        raise ValueError('CP/input and source price domains differ after common cut')
    return data,bindings


def saved_anchors(sid):
    """All saved raw anchors in fixed windows, never selected by outcomes."""
    result=[];bindings={}
    for root in PAIR_RUNS:
        path=root/sid.replace('.','_')/'CP_ANCHOR_PAIRS.json'
        if not path.exists():continue
        bindings[str(path)]=sha(path)
        for pair in json.loads(path.read_text()):
            if '2024-09-01'<=pair['anchor_day']<='2024-12-31':
                result.append((GROUPS[0],pair))
    path=SEMI_RUN/sid.replace('.','_')/'CP_ANCHOR_PAIRS.json'
    if path.exists():
        bindings[str(path)]=sha(path)
        for pair in json.loads(path.read_text()):
            if '2025-01-01'<=pair['anchor_day']<=CAP:result.append((GROUPS[1],pair))
    seen=set()
    for group,pair in result:
        identity=(group,pair['anchor_day'])
        assert identity not in seen,('duplicate saved raw anchor',sid,identity)
        seen.add(identity)
    return result,bindings


def worker(task):
    import paired_trace as signal_trace
    slot,sids,period,out=task;out=Path(out);started=time.monotonic()
    metas={x['symbol']:x for x in json.loads(runner.MANIFEST.read_text())}
    reports=[];errors=[];gates=Counter();anchor_gates=Counter();group_raw=Counter()
    counts={g:{k:np.zeros(2,dtype=np.int64)for k in ['protection','I_competing','no_exit20','protection_commonP0','protection_I_raised','protection_band_raised']}for g in GROUPS}
    common_n=Counter();warm480_n=Counter();warm480_counts={g:{k:np.zeros(2,dtype=np.int64)for k in counts[g]}for g in GROUPS}
    rows_path=out/f'WORKER_{slot}_ANCHORS.jsonl.gz'
    with gzip.open(rows_path,'wt',encoding='utf-8')as rows:
        for number,sid in enumerate(sids):
            if (out/'ERROR_STOP.json').exists():break
            try:
                anchors,pair_bindings=saved_anchors(sid)
                if not anchors:continue
                data,bindings=read_validation(metas[sid]);price=data['price']
                features=engine.features(price);indicators=kama.calculate(price,features)
                emas,weights=core.ema_matrix(price,indicators,periods=np.array([period],dtype=int))
                a=core.arrays(price,features,data['native'],indicators,emas,weights)
                # Metadata-only subgroup; no EMA480 values or exits are run.
                clean=indicators.clean_completed_observations.to_numpy(int)
                w480=np.where(indicators.math_ready.to_numpy(bool),(1.-2./481.)**(clean-10),np.nan)
                local=Counter()
                for group,pair in anchors:
                    group_raw[group]+=1
                    gate,anchor=core.anchor_only(pair,a);h20gate,common=core.common_anchor(pair,a)
                    anchor_gates[(group,gate)]+=1;gates[(group,h20gate)]+=1;local[h20gate]+=1
                    devwarm=None if anchor is None else bool(w480[anchor['anchor']]<=.01)
                    record=dict(sid=sid,group=group,anchor_day=pair['anchor_day'],anchor_id=pair.get('anchor_id'),
                        original_status=pair['status'],anchor_gate=gate,H20_gate=h20gate,
                        dev_style_EMA480_warm=devwarm,
                        original_CP_control=pair.get('CP'),original_CP_clock='SAVED_CONTROL_ONLY_NEW_Q_CAN_TRIGGER_SAME_CLOSE_UNLIKE_KAMA_EMA',
                        fixed_primary_case=(sid,pair['anchor_day'])in FIXED_CASES,
                        no_actual_position_or_fill=True)
                    if anchor is not None:
                        record['trace']=signal_trace.run(pair,a,price)
                    if common is not None:
                        result=core.evaluate(common,a);common_n[group]+=1
                        record['H20_counts']={k:v.tolist()for k,v in result.items()}
                        for k,v in result.items():counts[group][k]+=v
                        if devwarm:
                            warm480_n[group]+=1
                            for k,v in result.items():warm480_counts[group][k]+=v
                    rows.write(json.dumps(engine.clean(record),ensure_ascii=False,separators=(',',':'),allow_nan=False)+'\n')
                reports.append(dict(sid=sid,status='COMPLETE',raw_anchors=len(anchors),gates=dict(local),
                    source_sha256=bindings,pair_source_sha256=pair_bindings,source_end=None if price.empty else str(price.index[-1].date()),
                    computed_EMA_periods=[period],no_other_validation_period_computed=True))
            except Exception as error:
                item=dict(worker=slot,sid=sid,error=repr(error),traceback=traceback.format_exc());errors.append(item)
                try:
                    with (out/'ERROR_STOP.json').open('x')as f:json.dump(item,f,ensure_ascii=False,indent=2)
                except FileExistsError:pass
                break
            if (number+1)%50==0:print(json.dumps(dict(worker=slot,completed=number+1,total=len(sids),errors=len(errors),seconds=time.monotonic()-started)),flush=True)
    payload=dict(worker=slot,reports=reports,errors=errors,group_raw=dict(group_raw),
        common_n=dict(common_n),warm480_n=dict(warm480_n),
        anchor_gates=[dict(group=g,gate=k,n=v)for(g,k),v in anchor_gates.items()],
        H20_gates=[dict(group=g,gate=k,n=v)for(g,k),v in gates.items()],
        counts={g:{k:v.tolist()for k,v in d.items()}for g,d in counts.items()},
        warm480_counts={g:{k:v.tolist()for k,v in d.items()}for g,d in warm480_counts.items()},
        anchors_file=str(rows_path),seconds=time.monotonic()-started)
    save(out/f'WORKER_{slot}.json',payload)
    return dict(worker=slot,errors=len(errors),group_raw=dict(group_raw),seconds=time.monotonic()-started)


def frequency_summary(rows,only480=False):
    rows=[r for r in rows if r.get('H20_counts')is not None and(not only480 or r['dev_style_EMA480_warm'])]
    n=len(rows);totals={}
    for key in ['protection','I_competing','no_exit20','protection_commonP0','protection_I_raised','protection_band_raised']:
        totals[key]=[sum(r['H20_counts'][key][j]for r in rows)for j in range(2)]
    for j in range(2):assert sum(totals[k][j]for k in ['protection','I_competing','no_exit20'])==n
    return dict(common_n=n,counts=totals,
        protection_frequency=None if not n else [x/n for x in totals['protection']],
        validation_frequency_gap_percentage_points=None if not n else 100*abs(totals['protection'][0]-totals['protection'][1])/n,
        no_period_or_parameter_selection=True)


def distribution(values):
    v=np.asarray([float(x)for x in values if x is not None and np.isfinite(x)],dtype=float)
    if not len(v):return dict(n=0)
    return dict(n=len(v),mean=float(v.mean()),median=float(np.median(v)),
        p10=float(np.quantile(v,.1)),p90=float(np.quantile(v,.9)),min=float(v.min()),max=float(v.max()))


def exit_order(t):
    k,e=t['KAMA'],t['EMA'];ko,eo=k['outcome'],e['outcome']
    if ko==eo=='EXIT_SIGNAL':
        return 'BOTH_EXIT_KAMA_EARLIER'if k['exit_day']<e['exit_day']else'BOTH_EXIT_EMA_EARLIER'if e['exit_day']<k['exit_day']else'BOTH_EXIT_SAME_DAY'
    if ko=='EXIT_SIGNAL'and eo=='RIGHT_CENSORED':return 'KAMA_EXIT_EMA_RIGHT_CENSORED'
    if eo=='EXIT_SIGNAL'and ko=='RIGHT_CENSORED':return 'EMA_EXIT_KAMA_RIGHT_CENSORED'
    if ko==eo=='RIGHT_CENSORED':return 'BOTH_RIGHT_CENSORED'
    return 'UNKNOWN_PRESENT_'+ko+'__'+eo


def trace_summary(rows):
    eligible=[r for r in rows if r.get('trace')is not None]
    ts=[r['trace']for r in eligible]
    arms={}
    for arm in ('KAMA','EMA'):
        actual=[t[arm]for t in ts]
        observed=[x for x in actual if x['observations']>0]
        arms[arm]=dict(outcomes=dict(Counter(x['outcome']for x in actual)),
            first_exit_causes=dict(Counter(x.get('exit_reason','NO_OBSERVED_EXIT')for x in actual)),
            no_close_observation_n=sum(x['observations']==0 for x in actual),
            held_observations=distribution(x['observations']for x in observed),
            MFE_while_held=distribution(x['MFE_while_held']for x in observed),
            max_close_drawdown_while_held=distribution(x['max_close_drawdown_while_held']for x in observed),
            risk_unit='Fraction of close peak; unweighted shadow, different survival lengths, not account drawdown')
    h20=[r for r in eligible if r.get('H20_counts')is not None]
    quoted=[r for r in h20 if all(r['trace'][arm]['H20_unit_price_change']is not None for arm in ('KAMA','EMA'))]
    proxy=dict(common_H20_evaluable_n=len(h20),both_quotes_available_n=len(quoted),
        missing_one_or_both_quote_n=len(h20)-len(quoted),
        source_or_quote_missing_not_zero=True,
        KAMA=distribution(r['trace']['KAMA']['H20_unit_price_change']for r in quoted),
        EMA=distribution(r['trace']['EMA']['H20_unit_price_change']for r in quoted),
        KAMA_minus_EMA=distribution(r['trace']['KAMA']['H20_unit_price_change']-r['trace']['EMA']['H20_unit_price_change']for r in quoted),
        convention='Common E reference; if first exit within20 retain its next source OPEN unit value; else next OPEN after close20 mark. No fill, fee, reentry, compounding, cash or weight.')
    # Post-signal diagnostic only. Source-end labels are observed lower bounds,
    # explicitly separated from I-ended complete labels. Unknown contexts are
    # not used in the window q90 and remain in the coverage counts.
    label_rows=[r for r in eligible if r['trace']['common_market_end_reason']in('ORIGINAL_I_INVALID','SOURCE_END')and r['trace']['common_MFE']is not None]
    cutoff=None if not label_rows else float(np.quantile([r['trace']['common_MFE']for r in label_rows],.9))
    tail=[]if cutoff is None else[r for r in label_rows if r['trace']['common_MFE']>=cutoff]
    tail_detail={}
    for arm in ('KAMA','EMA'):
        exits=[r['trace'][arm]for r in tail if r['trace'][arm]['outcome']=='EXIT_SIGNAL']
        tail_detail[arm]=dict(observed_exit_n=len(exits),
            exited_then_common_new_high_n=sum(x['common_higher_peak_after_exit_in_entry_units']>0 for x in exits),
            extra_common_high_in_entry_units=distribution(x['common_higher_peak_after_exit_in_entry_units']for x in exits),
            observations=distribution(r['trace'][arm]['observations']for r in tail),
            exit_quote_change=distribution(x['exit_OPEN_unit_price_change']for x in exits))
    return dict(anchor_eligible_n=len(eligible),exit_comparisons_split_censor=dict(Counter(exit_order(t)for t in ts)),
        common_market_end_reasons=dict(Counter(t['common_market_end_reason']for t in ts)),arms=arms,H20_common_quote_unit_proxy=proxy,
        winner_diagnostic=dict(definition='Window q90 of independent-I/source observed maxclose/E-1; never rule-exit truncated and never a signal input.',
            quantile_method='numpy linear .9 inclusive ties',label_evaluable_n=len(label_rows),q90=cutoff,
            label_complete_I_end_n=sum(not r['trace']['common_label_is_observed_lower_bound']for r in label_rows),
            label_source_end_lower_bound_n=sum(r['trace']['common_label_is_observed_lower_bound']for r in label_rows),
            unknown_context_excluded_n=len(eligible)-len(label_rows),tail_n=len(tail),tail_stock_n=len({r['sid']for r in tail}),
            tail_complete_I_end_n=sum(not r['trace']['common_label_is_observed_lower_bound']for r in tail),
            tail_source_end_lower_bound_n=sum(r['trace']['common_label_is_observed_lower_bound']for r in tail),
            exit_comparisons_split_censor=dict(Counter(exit_order(r['trace'])for r in tail)),arms=tail_detail,
            overlapping_raw_anchors_not_independent_trades=True),
        all_raw_anchors=len(rows),original_CP_control='Saved per anchor, original same-close proposal clock differs, not included in the two-arm treatment contrast')


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--lock',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True);parser.add_argument('--processes',type=int,default=3)
    args=parser.parse_args();assert args.processes==3
    lock=accepted_lock(args.lock)
    instance=(HERE/'VALIDATION_INSTANCE.lock').open('a+')
    try:fcntl.flock(instance.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:raise SystemExit('Another validation instance owns the frozen single-instance file lock')
    instance.seek(0);instance.truncate()
    instance.write(json.dumps(dict(pid=os.getpid(),lock=str(args.lock.resolve()),out=str(args.out.resolve()))))
    instance.flush()
    import paired_trace as signal_trace
    assert hasattr(signal_trace,'run'),'Parent shared trace API not yet finalized'
    files=[HERE/'FREEZE.md',HERE/'core.py',HERE/'paired_trace.py',Path(__file__),BASE/'kama.py',SHARED/'engine.py',SHARED/'runner.py',runner.MANIFEST,args.lock]
    bindings={str(p.resolve()):sha(p)for p in files}
    args.out.mkdir(exist_ok=False)
    save(args.out/'RUN_START.json',dict(phase='LOCKED_VALIDATION_TWO_ARMS_ONLY',source_sha256=bindings,
        locked_EMA_period=lock['period'],processes=3,source_cutoff=CAP,
        raw_mothers={GROUPS[0]:12412,GROUPS[1]:2901,'2024_924_SUBSET':11904},
        validation_EMA_periods_computed=[lock['period']],new_accounts=0,new_orders=0,new_quantities=0))
    started=time.monotonic();sids=sorted(x['symbol']for x in json.loads(runner.MANIFEST.read_text()))
    tasks=[(i,sids[i::3],lock['period'],str(args.out.resolve()))for i in range(3)]
    with ProcessPoolExecutor(max_workers=3)as pool:workers=list(pool.map(worker,tasks))
    if any(x['errors']for x in workers)or(args.out/'ERROR_STOP.json').exists():
        save(args.out/'RUN_RECEIPT.json',dict(status='PARTIAL_ERROR_STOP_NO_RETRY',workers=workers,source_sha256=bindings));raise SystemExit('Preserved partial artifacts; no automatic retry')
    rows=[]
    for i in range(3):
        with gzip.open(args.out/f'WORKER_{i}_ANCHORS.jsonl.gz','rt',encoding='utf-8')as f:rows.extend(json.loads(line)for line in f)
    assert len(rows)==15313
    assert len({(r['group'],r['sid'],r['anchor_day'])for r in rows})==len(rows)
    groups={g:[r for r in rows if r['group']==g]for g in GROUPS}
    groups['VALIDATION_2024_924_ONWARD']=[r for r in groups[GROUPS[0]]if r['anchor_day']>='2024-09-24']
    assert len(groups[GROUPS[0]])==12412 and len(groups[GROUPS[1]])==2901 and len(groups['VALIDATION_2024_924_ONWARD'])==11904
    frequency={g:dict(raw_anchors=len(rs),anchor_gates=dict(Counter(r['anchor_gate']for r in rs)),
        H20_gates=dict(Counter(r['H20_gate']for r in rs)),
        main=frequency_summary(rs),dev_style_EMA480_warm_subgroup=frequency_summary(rs,True))for g,rs in groups.items()}
    save(args.out/'FREQUENCY_AND_COVERAGE.json',frequency)
    cases=[r for r in rows if r['fixed_primary_case']]
    assert {(r['sid'],r['anchor_day'])for r in cases}==FIXED_CASES
    save(args.out/'FIXED_EARLY_STRONG_CASES.json',cases)
    # Shared trace owns all price rules; this only groups existing records.
    save(args.out/'TRACE_SUMMARY.json',{g:trace_summary(rs)for g,rs in groups.items()})
    assert all(sha(p)==h for p,h in bindings.items()),'Code or accepted lock changed during validation'
    save(args.out/'RUN_RECEIPT.json',dict(status='COMPLETE_LOCKED_VALIDATION',workers=workers,
        source_sha256=bindings,locked_EMA_period=lock['period'],raw_anchors=len(rows),
        frequency=frequency,elapsed_seconds=time.monotonic()-started,
        computed_EMA_periods=[lock['period']],new_accounts=0,new_orders=0,new_quantities=0,new_portfolio_returns=0,
        original_E0_I_CP_runs=0,indicators_full_prefix=True,source_cutoff=CAP,
        validation_not_used_to_reselect_N=True,full_calendar_gap_check='NOT_VERIFIED'))
    print(json.dumps(engine.clean(dict(status='COMPLETE_LOCKED_VALIDATION',locked_EMA_period=lock['period'],raw_anchors=len(rows),frequency=frequency,seconds=time.monotonic()-started)),ensure_ascii=False),flush=True)


if __name__=='__main__':main()
