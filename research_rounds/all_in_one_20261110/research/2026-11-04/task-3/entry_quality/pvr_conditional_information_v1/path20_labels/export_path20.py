"""Exactly20 shared-session close-path labels. No features/ranks/accounts."""
from pathlib import Path
from collections import Counter
import hashlib
import json
import time
import numpy as np
import pandas as pd
import pyarrow.parquet as pq

HERE=Path(__file__).resolve().parent
ENTRY=HERE.parents[1]
OLD=ENTRY/'pvr_information_v1'
PRIMARY=OLD/'universe_audit/PRIMARY_CANDIDATES.jsonl'
FEATURES=OLD/'export/features.parquet'
QUOTES=OLD/'export/reference_quotes.parquet'
MANIFEST=OLD/'export/FEATURE_MANIFEST_PRE_LABEL.json'
LABELS=OLD/'analysis/results_v2/LABELS.parquet'
CLOCK=OLD/'analysis/label_clock.py'
KEY=['window','day','sid']


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,value):(HERE/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def calculate(features,quotes,keys,calendars,old):
    """The existing h20 endpoint/entry status is retained, never called path-known."""
    output=[];checks=[]
    for window,calendar in calendars.items():
        q=quotes.loc[quotes.window.eq(window)].reset_index(drop=True)
        f=features.loc[features.window.eq(window)].reset_index(drop=True)
        kk=keys.loc[keys.window.eq(window)].copy().reset_index(drop=True)
        legacy=kk[KEY].merge(old,on=KEY,how='left',validate='one_to_one')
        assert legacy.h20_status.notna().all()
        assert q[KEY].equals(f[KEY])
        symbols=np.asarray(pd.unique(q.sid));n=len(calendar)
        assert len(q)==len(symbols)*n
        assert np.array_equal(q.day.to_numpy().reshape(-1,n),np.tile(calendar,(len(symbols),1)))
        assert np.array_equal(q.sid.to_numpy().reshape(-1,n),np.repeat(symbols[:,None],n,axis=1))
        assert not q[['valid','observed']].isna().any().any()
        assert not f.stock_source_row_present.isna().any()
        shape=(len(symbols),n);array=lambda x:np.asarray(x).reshape(shape)
        C=array(q.close.to_numpy(float));O=array(q.open.to_numpy(float))
        present=array(f.stock_source_row_present.to_numpy(bool));observed=array(q.observed.to_numpy(bool));valid=array(q.valid.to_numpy(bool))
        block=array(q.block.to_numpy(float,na_value=np.nan));segment=array(f.source_segment.to_numpy(float))
        si=pd.Index(symbols).get_indexer(kk.sid);ti=pd.Index(calendar).get_indexer(kk.day)
        assert (si>=0).all()and(ti>=0).all()
        future=ti[:,None]+np.arange(1,21)[None,:]
        within=future<n;mature=within.all(axis=1);at=future.clip(max=n-1)
        fp=present[si[:,None],at];fo=observed[si[:,None],at];fv=valid[si[:,None],at]
        path=C[si[:,None],at];fb=block[si[:,None],at];fs=segment[si[:,None],at]
        cb=block[si,ti];cs=segment[si,ti]
        ids_known=np.isfinite(fb)&np.isfinite(fs)&np.isfinite(cb[:,None])&np.isfinite(cs[:,None])
        same_block=ids_known&(fb==cb[:,None]);same_segment=ids_known&(fs==cs[:,None])
        price=np.isfinite(path)&(path>0)
        rowgood=fp&fo&fv&price&same_block&same_segment&within
        complete=(legacy.h20_status.to_numpy()=='KNOWN')&mature&rowgood.all(axis=1)
        status=legacy.h20_status.to_numpy(dtype=object).copy()
        reasons=[('PATH_ROW_MISSING',~fp),('PATH_NOT_OBSERVED',fp&~fo),('PATH_JOINT_INVALID',fp&~fv),
                 ('PATH_CLOSE_INVALID',~price),('PATH_SOURCE_ID_UNKNOWN',~ids_known),
                 ('PATH_BLOCK_TRANSITION',ids_known&~same_block),('PATH_SEGMENT_TRANSITION',ids_known&~same_segment)]
        legacy_known=legacy.h20_status.eq('KNOWN').to_numpy()
        for name,bad in reversed(reasons):status[legacy_known&mature&(bad&within).any(axis=1)]=name
        assert np.array_equal(status=='KNOWN',complete)
        first=(ti+1).clip(max=n-1);end=(ti+20).clip(max=n-1)
        startO=O[si,first];startC=C[si,ti];terminal=C[si,end]
        row=kk.copy()
        # All original flags and existing endpoint labels survive byte-values.
        for name in legacy.columns:
            if name not in KEY:row[name]=legacy[name]
        row['path20_status']=status;row['path20_complete']=complete
        row['path20_shared_sessions_available']=within.sum(axis=1)
        row['path20_known_comparable_close_count']=rowgood.sum(axis=1)
        row['path20_start_next_shared_day']=[calendar[t+1]if t+1<n else None for t in ti]
        row['path20_terminal_shared_day']=[calendar[t+20]if t+20<n else None for t in ti]
        row['path20_current_CLOSE_reference']=startC
        row['path20_next_OPEN_reference']=np.where(ti+1<n,startO,np.nan)
        row['path20_terminal_CLOSE_reference']=np.where(mature,terminal,np.nan)
        for name,bad in reasons:
            row['path20_any_'+name.removeprefix('PATH_').lower()]=pd.arrays.BooleanArray((bad&within).any(axis=1),~mature)
        high=path.max(axis=1);low=path.min(axis=1)
        with np.errstate(divide='ignore',invalid='ignore'):
            for origin,base in [('next_OPEN',startO),('decision_CLOSE',startC)]:
                row['path20_MFE_'+origin]=np.where(complete,high/base-1,np.nan)
                row['path20_MAE_'+origin]=np.where(complete,low/base-1,np.nan)
                row['path20_return_'+origin]=np.where(complete,terminal/base-1,np.nan)
        # Check old entry/terminal values wherever they were defined, including
        # rows later rejected solely for an internal missing shared session.
        endpoint_known=legacy.h20_status.eq('KNOWN').to_numpy()
        with np.errstate(divide='ignore',invalid='ignore'):
            opened=terminal/startO-1;closed=terminal/startC-1;gap=startO/startC-1
        assert np.array_equal(opened[endpoint_known],legacy.loc[endpoint_known,'h20_next_OPEN_return'].to_numpy(float))
        old_close=legacy.h20_decision_CLOSE_return.to_numpy(float)
        ck=np.isfinite(old_close)
        assert np.array_equal(closed[ck],old_close[ck])
        oldgap=legacy.next_OPEN_gap.to_numpy(float);gk=np.isfinite(oldgap)
        assert np.array_equal(gap[gk],oldgap[gk])
        # Keep finite path evidence only on complete rows; no repeated clipped
        # terminal price is exported as a fake20-path for censored observations.
        row['path20_close_days']=[future_days(calendar,t)if ok else None for t,ok in zip(ti,complete)]
        row['path20_close_values']=[values.tolist()if ok else None for values,ok in zip(path,complete)]
        checks.append(dict(window=window,rows=len(row),old_h20_KNOWN=int(endpoint_known.sum()),
            path20_complete=int(complete.sum()),old_known_missing_internal_path=int((endpoint_known&~complete).sum()),
            status_counts=dict(Counter(status)),existing_endpoint_returns_bitexact=True,existing_gap_bitexact=True,
            negative_MFE_next_OPEN=int((row.path20_MFE_next_OPEN<0).sum()),positive_MAE_next_OPEN=int((row.path20_MAE_next_OPEN>0).sum())))
        output.append(row)
    return pd.concat(output,ignore_index=True).sort_values('candidate_index').reset_index(drop=True),checks


def future_days(calendar,t):return list(calendar[t+1:t+21])


def main():
    assert not(HERE/'PATH20_LABELS.parquet').exists()
    started=time.monotonic();manifest=json.loads(MANIFEST.read_text());calendars=manifest['calendars']
    assert sha(FEATURES)==manifest['outputs']['features.parquet']['sha256']
    assert sha(QUOTES)==manifest['outputs']['reference_quotes.parquet']['sha256']
    rows=[]
    with PRIMARY.open()as stream:
        for i,line in enumerate(stream):
            x=json.loads(line);rows.append(dict(candidate_index=i,window=x['window'],day=x['day'],sid=x['sid'],decision_at=x['decision_at']))
    keys=pd.DataFrame(rows);assert len(keys)==133713 and not keys.duplicated(KEY).any()
    features=pd.read_parquet(FEATURES,columns=KEY+['stock_source_row_present','source_segment'])
    quotes=pd.read_parquet(QUOTES)
    names=pq.read_schema(LABELS).names
    oldcols=KEY+[x for x in names if x.startswith('h20_')or x in ['next_OPEN_gap','halt_status']or x.startswith('current_')or x.startswith('next_')]
    old=pd.read_parquet(LABELS,columns=list(dict.fromkeys(oldcols)))
    assert not old.duplicated(KEY).any()
    result,checks=calculate(features,quotes,keys,calendars,old)
    assert len(result)==133713 and result.candidate_index.tolist()==list(range(133713))
    assert result[KEY].equals(keys[KEY])
    result.to_parquet(HERE/'PATH20_LABELS.parquet',index=False,compression='zstd')
    # Genuine truncate at an observation after t+20: labels may use future20,
    # never any observation beyond the fixed terminal boundary.
    window='2022_2024';candidate=keys.loc[keys.window.eq(window)].iloc[0]
    t=calendars[window].index(candidate.day);shortcal=calendars[window][:t+21]
    fq=features.loc[features.window.eq(window)&features.day.isin(shortcal)]
    qq=quotes.loc[quotes.window.eq(window)&quotes.day.isin(shortcal)]
    short,_=calculate(fq,qq,keys.loc[[candidate.name]],{window:shortcal},old)
    full=result.loc[result.candidate_index.eq(candidate.candidate_index)].reset_index(drop=True)
    scalarcols=[x for x in result if not x.endswith('_days')and not x.endswith('_values')]
    exact=short[scalarcols].equals(full[scalarcols])
    assert exact
    save('TERMINAL_TRUNCATION_CHECK.json',dict(window=window,sid=candidate.sid,decision_day=candidate.day,
        terminal_day=shortcal[-1],calendar_rows=len(shortcal),all_scalar_columns_exact=exact,
        no_use_beyond_twentieth_shared_session=True))
    files=[PRIMARY,FEATURES,QUOTES,MANIFEST,LABELS,CLOCK,Path(__file__)]
    save('RUN_RECEIPT.json',dict(status='COMPLETE_FIXED20_SHARED_SESSION_PATH_LABELS',rows=len(result),checks=checks,
        complete=int(result.path20_complete.sum()),status_counts=dict(Counter(result.path20_status)),
        calendars={k:dict(first=v[0],last=v[-1],sessions=len(v))for k,v in calendars.items()},
        source_sha256={str(p.resolve()):sha(p)for p in files},output_sha256=sha(HERE/'PATH20_LABELS.parquet'),
        signed_extrema_not_clipped=True,decision_CLOSE_labels_use_same_complete_sample=True,
        no_skip_or_carry_or_calendar_extension=True,new_Account_runs=0,new_PVR_calculations=0,
        new_rank_or_bin_definitions=0,elapsed_seconds=time.monotonic()-started))
    print(json.dumps(dict(rows=len(result),checks=checks,seconds=time.monotonic()-started)),flush=True)


if __name__=='__main__':main()
