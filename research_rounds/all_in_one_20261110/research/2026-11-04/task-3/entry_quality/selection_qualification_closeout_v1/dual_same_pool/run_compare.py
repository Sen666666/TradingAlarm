"""One bounded full-source cheap e/PVR/dual same-pool contrast, no E0/account."""
from pathlib import Path
from collections import Counter
import hashlib,importlib.util,json,time,csv
import numpy as np
import pandas as pd
import cheap_features

HERE=Path(__file__).resolve().parent;ENTRY=HERE.parents[1]
PRIOR=ENTRY/'pvr_information_v1'
CANONICAL=ENTRY/'local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet'
SM=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
ORIGINAL_EXPORT=PRIOR/'export/export_features.py'
GRID=PRIOR/'export/features.parquet'
PREVIOUS_PVR=HERE.parent/'adjustment_review/ALL_COMMON_FINITE_PVR_RANKS.csv'
DAYS=['2022-01-10','2022-01-24','2024-09-24','2024-10-08','2026-01-15','2026-01-20','2026-05-15']
TARGETS=['000620.SZ','300666.SZ','300085.SZ','002583.SZ','603061.SH','301611.SZ','300604.SZ','301308.SZ','002371.SZ','688012.SH','688498.SH']
KEY=['sid','day']


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(name,x):(HERE/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
def bits_equal(x,y):
    x=np.asarray(x,dtype=float);y=np.asarray(y,dtype=float);valid=np.isfinite(x)&np.isfinite(y)
    return np.array_equal(np.isfinite(x),np.isfinite(y))and np.array_equal(x[valid].view(np.uint64),y[valid].view(np.uint64))
def percentages(s):return(s.rank(method='average')-1)/(len(s)-1)


def queue_values(g,side,queue):
    if queue!='CONT':return g['score_'+side]if queue=='PVR'else g['E_fast_'+side],{}
    f=percentages(g['E_fast_'+side]);s=percentages(g['E_slow_'+side]);unit=2*(len(g)-1)
    a=np.rint(f*unit);b=np.rint(s*unit)
    assert np.allclose(a,f*unit,atol=1e-10,rtol=0)and np.allclose(b,s*unit,atol=1e-10,rtol=0)
    num=(3*a+7*b).astype('int64')
    return num,{'p_fast_'+side:f,'p_slow_'+side:s,'CONT_num_'+side:num,'CONT_'+side:num/(20*(len(g)-1))}


def main():
    assert not(HERE/'COMPLETION.json').exists()
    started=time.monotonic()
    spec=importlib.util.spec_from_file_location('same_pool_old_source_readonly_loader',ORIGINAL_EXPORT)
    loader=importlib.util.module_from_spec(spec);spec.loader.exec_module(loader)
    new=pd.read_parquet(CANONICAL);meta={r['symbol']:r for r in json.loads(SM.read_text())}
    universe=sorted(set(new.sid)&set(meta));assert len(universe)==1681
    sources={str(p.resolve()):sha(p)for p in [CANONICAL,SM,ORIGINAL_EXPORT,GRID,loader.F,Path(__file__),Path(cheap_features.__file__),PREVIOUS_PVR]}
    grid=pd.read_parquet(GRID,columns=['sid','day','window']+list(loader.API.PVR_COLUMNS)+['source_segment','pvr_clock_block','pvr_valid_observation','pvr_block_observation'])
    grid_by={sid:g for sid,g in grid.groupby('sid',sort=False)}
    old_rows=[];checks=Counter();prefixes=[]
    for number,sid in enumerate(universe):
        signal=loader.read_signal(meta[sid],sources)
        full=cheap_features.calculate(signal,loader.API)
        saved=grid_by[sid];aligned=full.reindex(pd.DatetimeIndex(saved.day))
        for col in loader.API.PVR_COLUMNS:
            assert bits_equal(aligned[col],saved[col]),(sid,col,'all-grid not bitexact')
            checks[col+'_all_grid_cells']+=len(saved);checks[col+'_finite_bitexact']+=int(np.isfinite(saved[col]).sum())
        for col in ['source_segment','pvr_clock_block','pvr_block_observation']:
            assert bits_equal(aligned[col].to_numpy(float,na_value=np.nan),saved[col].to_numpy(float,na_value=np.nan)),(sid,col)
        assert np.array_equal(aligned.pvr_valid_observation.fillna(False),saved.pvr_valid_observation)
        selected=full.reindex(pd.DatetimeIndex(DAYS)).copy();selected.insert(0,'day',DAYS);selected.insert(0,'sid',sid)
        selected['source_row_present']=pd.DatetimeIndex(DAYS).isin(signal.index)
        for field in ['pvr_status','fast_status','slow_status']:selected[field]=selected[field].fillna('NO_EXACT_SOURCE_OBSERVATION')
        selected['source_sha256']=loader.signal_path(meta[sid])[1]
        old_rows.append(selected.reset_index(drop=True))
        if sid in {'000620.SZ','002583.SZ'}:
            cutoff=pd.Timestamp('2022-01-24'if sid=='000620.SZ'else'2024-09-24');short=signal.loc[:cutoff]
            recalculated=cheap_features.calculate(short,loader.API);assert recalculated.equals(full.loc[recalculated.index])
            prefixes.append(dict(sid=sid,cutoff=str(cutoff.date()),full_source_rows=len(signal),prefix_rows=len(short),all_common_columns_exact=True))
        if(number+1)%300==0:print(json.dumps(dict(completed=number+1,total=1681,seconds=time.monotonic()-started)),flush=True)
    old=pd.concat(old_rows,ignore_index=True);assert len(old)==1681*7 and not old.duplicated(KEY).any()
    old.to_parquet(HERE/'OLD_SOURCE_FIXED_FEATURES.parquet',index=False,compression='zstd')
    new=new.loc[new.sid.isin(universe)].copy();assert len(new)==11767
    common=old.merge(new,on=KEY,how='outer',validate='one_to_one',suffixes=('_old','_new'))
    assert len(common)==11767
    common.to_parquet(HERE/'ALL_1681_COORDINATE_FEATURES.parquet',index=False,compression='zstd')
    summaries=[];ranks=[];tops=[];targets=[]
    for day,g in common.groupby('day',sort=True):
        for queue,columns in [('PVR',['score']),('FAST',['E_fast']),('CONT',['E_fast','E_slow'])]:
            complete=g.source_row_present&g.target_row_present
            for c in columns:complete&=np.isfinite(g[c+'_old'])&np.isfinite(g[c+'_new'])
            q=g.loc[complete].copy().reset_index(drop=True);assert len(q)>20
            for side in ['old','new']:
                values,extra=queue_values(q,side,queue)
                q['queue_value_'+side]=values
                for field,value in extra.items():q[field]=value
                order=q.sort_values(['queue_value_'+side,'sid'],ascending=[False,True]).index
                rank=pd.Series(index=q.index,dtype='int64');rank.loc[order]=np.arange(1,len(q)+1)
                q['rank_'+side]=rank.astype('int64')
            q['queue']=queue;q['common_pool_N']=len(q);q['rank_new_minus_old']=q.rank_new-q.rank_old
            rankcols=KEY+['queue','common_pool_N','queue_value_old','queue_value_new','rank_old','rank_new','rank_new_minus_old']
            rankcols+=[c for c in q if c.startswith(('p_fast_','p_slow_','CONT_num_','CONT_'))]
            ranks.append(q[rankcols])
            old_top=set(q.loc[q.rank_old.le(20),'sid']);new_top=set(q.loc[q.rank_new.le(20),'sid'])
            for side in ['old','new']:
                t=q.loc[q['rank_'+side].le(20),rankcols].copy();t['side']=side
                t['top20_status']=t.sid.map(lambda s:'BOTH'if s in old_top&new_top else'OLD_ONLY'if s in old_top else'NEW_ONLY')
                t=t.sort_values('rank_'+side);tops.append(t)
            summaries.append(dict(day=day,queue=queue,mother=1681,common_pool_N=len(q),top20_intersection=len(old_top&new_top),
                top20_new_only=len(new_top-old_top),top20_old_only=len(old_top-new_top),rank_changed=int(q.rank_new.ne(q.rank_old).sum()),
                max_abs_rank_change=int(q.rank_new_minus_old.abs().max()),old_queue_tie_excess=int(q.queue_value_old.duplicated().sum()),new_queue_tie_excess=int(q.queue_value_new.duplicated().sum())))
            lookup=q.set_index('sid');mother=g.set_index('sid')
            for sid in TARGETS:
                row=dict(day=day,queue=queue,sid=sid,common_pool_N=len(q))
                if sid in lookup.index:
                    z=lookup.loc[sid];row.update(status='COMMON_COMPLETE',rank_old=int(z.rank_old),rank_new=int(z.rank_new),
                        rank_new_minus_old=int(z.rank_new_minus_old),queue_value_old=float(z.queue_value_old),queue_value_new=float(z.queue_value_new),
                        old_top20=bool(z.rank_old<=20),new_top20=bool(z.rank_new<=20))
                else:
                    if sid not in mother.index:reason='OUTSIDE_1681_EXACT_INTERSECTION'
                    else:
                        z=mother.loc[sid];ok_old=bool(z.source_row_present)and all(np.isfinite(z[c+'_old'])for c in columns);ok_new=bool(z.target_row_present)and all(np.isfinite(z[c+'_new'])for c in columns)
                        reason='BOTH_UNKNOWN'if not ok_old and not ok_new else'OLD_UNKNOWN'if not ok_old else'NEW_UNKNOWN'
                    row.update(status=reason,rank_old=None,rank_new=None,rank_new_minus_old=None,queue_value_old=None,queue_value_new=None,old_top20=None,new_top20=None)
                targets.append(row)
    allr=pd.concat(ranks,ignore_index=True);allr.to_parquet(HERE/'ALL_COMMON_QUEUE_RANKS.parquet',index=False,compression='zstd')
    pd.DataFrame(summaries).to_csv(HERE/'DAY_QUEUE_SUMMARY.csv',index=False)
    pd.concat(tops,ignore_index=True).to_csv(HERE/'TOP20_BOTH_SIDES.csv',index=False)
    target=pd.DataFrame(targets);assert len(target)==231;target.to_csv(HERE/'TARGET_231_SAME_POOL_RANKS.csv',index=False)
    # Existing PVR contrast is immutable; only assert identical rank membership.
    with PREVIOUS_PVR.open()as f:previous=list(csv.DictReader(f))
    prev={(r['sid'],r['day']):(int(r['rank_old']),int(r['rank_new']))for r in previous}
    current={(r.sid,r.day):(r.rank_old,r.rank_new)for r in allr.loc[allr.queue.eq('PVR')].itertuples()}
    assert prev==current,'PVR rank bridge differs from preserved adjustment_review'
    save('PREFIX_CHECKS.json',prefixes)
    save('COMPLETION.json',dict(status='COMPLETE_CHEAP_1681_SEVEN_DATE_SAME_POOL_DUAL_CONTRAST',symbols=1681,old_feature_rows=len(old),dates=DAYS,
        queue_summaries=summaries,targets=231,all_grid_exact_checks=dict(checks),all_clock_fields_exact=True,
        same_pool_PVR_rank_bridge_to_prior_review_exact=True,source_sha256=sources,
        outputs={p.name:sha(p)for p in HERE.iterdir()if p.suffix in {'.parquet','.csv','.json'}and p.name!='COMPLETION.json'},
        elapsed_seconds=time.monotonic()-started,new_E0_I_G1_calls=0,new_accounts=0,forward_labels_read=False,new_parameters=0))
    print(json.dumps(dict(status='COMPLETE',seconds=time.monotonic()-started,summaries=summaries)),flush=True)


if __name__=='__main__':main()
