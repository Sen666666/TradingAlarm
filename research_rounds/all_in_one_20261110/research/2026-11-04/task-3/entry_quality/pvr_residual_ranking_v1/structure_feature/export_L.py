"""Read full original signals; export exactly the original primary candidate rows."""
from pathlib import Path
from collections import Counter
import importlib.util
import hashlib
import json
import time
import numpy as np
import pandas as pd
import features as own

HERE=Path(__file__).resolve().parent
ENTRY=HERE.parents[1]
PRIOR=ENTRY/'pvr_information_v1'
PRIMARY=PRIOR/'universe_audit/PRIMARY_CANDIDATES.jsonl'
PRIMARY_SHA='49b4a70d62a497d8b610e15133a2e9f383c14a1b360275b785c0b0955e92496a'
EXPORTED=PRIOR/'export/features.parquet'
EXPORTER=PRIOR/'export/export_features.py'
ORIGINAL_FEATURE=PRIOR/'feature_design/features.py'
SM=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(v):
    if isinstance(v,dict):return {str(k):clean(x)for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [clean(x)for x in v]
    if v is None or v is pd.NA or v is pd.NaT:return None
    if isinstance(v,pd.Timestamp):return str(v.date())
    if isinstance(v,np.generic):v=v.item()
    return None if isinstance(v,float)and not np.isfinite(v)else v
def save(name,value):(HERE/name).write_text(json.dumps(clean(value),ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def main():
    assert sha(PRIMARY)==PRIMARY_SHA
    assert not(HERE/'L_FEATURES.parquet').exists()
    spec=importlib.util.spec_from_file_location('original_pvr_export_readonly_loader',EXPORTER)
    loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
    assert sha(ORIGINAL_FEATURE)==loader.FEATURE_SHA
    started=time.monotonic();sources={str(p.resolve()):sha(p)for p in[PRIMARY,EXPORTED,EXPORTER,ORIGINAL_FEATURE,SM,HERE/'features.py',Path(__file__)]}
    records=[]
    with PRIMARY.open()as stream:
        for i,line in enumerate(stream):
            x=json.loads(line);records.append(dict(candidate_index=i,sid=x['sid'],day=x['day'],window=x['window'],decision_at=x['decision_at']))
    primary=pd.DataFrame(records);assert len(primary)==133713
    assert not primary.duplicated(['window','sid','day']).any()
    metas={r['symbol']:r for r in json.loads(SM.read_text())}
    outputs=[];errors=[];prefix=None;examples=[]
    for number,(sid,rows)in enumerate(primary.groupby('sid',sort=True)):
        dates=pd.DatetimeIndex(rows.day)
        try:
            signal=loader.read_signal(metas[sid],sources) # Only reader; never exporter.execute/compute_features.
            valid,block=loader.API.original_observation_clock(signal)
            full=own.calculate(signal,valid,block)
            selected=full.reindex(dates).copy();selected.index=rows.index
            selected['source_row_present']=dates.isin(signal.index)
            selected['pvr_valid_observation']=selected.pvr_valid_observation.fillna(False).astype(bool)
            selected['L_status']=selected.L_status.fillna('NO_EXACT_SOURCE_OBSERVATION')
            group_data={int(k):(g.index.strftime('%Y-%m-%d').tolist(),g.close.to_numpy(float))for k,g in signal.loc[valid].groupby(block[valid],sort=False)}
            evidence={name:[]for name in ['recent5_close_days','prior5_close_days','recent5_close_values','prior5_close_values']}
            for _,row in selected.iterrows():
                if row.L_status=='KNOWN':
                    days,values=group_data[int(row.pvr_clock_block)];j=int(row.pvr_block_observation)
                    evidence['recent5_close_days'].append(days[j-4:j+1]);evidence['prior5_close_days'].append(days[j-9:j-4])
                    evidence['recent5_close_values'].append(values[j-4:j+1].tolist());evidence['prior5_close_values'].append(values[j-9:j-4].tolist())
                else:
                    for name in evidence:evidence[name].append(None)
            for name,value in evidence.items():selected[name]=value
            for name in rows.columns:selected[name]=rows[name]
            if sid=='300058.SZ':
                cut=pd.Timestamp('2022-01-04');short=signal.loc[:cut].copy()
                sv,sb=loader.API.original_observation_clock(short);small=own.calculate(short,sv,sb)
                shared=full.loc[small.index]
                prefix=dict(sid=sid,cutoff=str(cut.date()),truncated_source_rows=len(short),full_source_rows=len(signal),
                            all_columns_all_common_rows_exact=small.equals(shared),no_original_PVR_recalculation=True)
                assert prefix['all_columns_all_common_rows_exact']
            if len(examples)<3:
                ex=selected.loc[selected.day.eq('2022-01-04')&selected.L_status.eq('KNOWN')]
                if not ex.empty:examples.append(clean(ex.iloc[0].to_dict()))
            outputs.append(selected)
        except Exception as error:
            errors.append(dict(sid=sid,error=repr(error)))
            blank=rows.copy();blank['L']=np.nan;blank['L_status']='SOURCE_ERROR_NO_VALUE_IMPUTED';outputs.append(blank)
        if(number+1)%200==0:print(json.dumps(dict(completed_symbols=number+1,errors=len(errors),seconds=time.monotonic()-started)),flush=True)
    out=pd.concat(outputs,ignore_index=True).sort_values('candidate_index').reset_index(drop=True)
    assert len(out)==133713 and out.candidate_index.tolist()==list(range(133713))
    assert out[['sid','day','window']].equals(primary[['sid','day','window']])
    # Compare only the saved original clock/mask. No PVR values are recomputed.
    saved=pd.read_parquet(EXPORTED,columns=['sid','day','window','pvr_valid_observation','pvr_clock_block','pvr_block_observation','source_segment'])
    joined=out.merge(saved,on=['sid','day','window'],how='left',suffixes=('_new','_old'),validate='one_to_one')
    clock={}
    for name in ['pvr_valid_observation','pvr_clock_block','pvr_block_observation','source_segment']:
        x,y=joined[name+'_new'],joined[name+'_old']
        comparable=joined.L_status.ne('SOURCE_ERROR_NO_VALUE_IMPUTED')
        equal=x.eq(y)|(x.isna()&y.isna());clock[name]=dict(mismatches=int((comparable&~equal.fillna(False)).sum()),source_error_rows_not_compared=int((~comparable).sum()))
    assert not any(x['mismatches']for x in clock.values()),clock
    out.to_parquet(HERE/'L_FEATURES.parquet',index=False,compression='zstd')
    save('PREFIX_CHECK.json',prefix);save('SMALL_EXAMPLES.json',examples);save('SOURCE_ERRORS.json',errors)
    save('RUN_RECEIPT.json',dict(status='COMPLETE'if not errors else'COMPLETE_ROWS_WITH_SOURCE_UNKNOWN',rows=len(out),symbols=primary.sid.nunique(),
        L_status_counts=dict(Counter(out.L_status)),by_window={str(k):dict(Counter(v.L_status))for k,v in out.groupby('window')},
        original_clock_crosscheck=clock,true_truncated_prefix=prefix,source_sha256=sources,
        output_sha256=sha(HERE/'L_FEATURES.parquet'),elapsed_seconds=time.monotonic()-started,
        no_future_labels=True,no_future_pivots=True,no_nonPIT_fills=True,PVR_recalculations=0,new_accounts=0,new_ranking_rules=0))
    print(json.dumps(dict(rows=len(out),statuses=dict(Counter(out.L_status)),errors=len(errors),seconds=time.monotonic()-started)),flush=True)


if __name__=='__main__':main()
