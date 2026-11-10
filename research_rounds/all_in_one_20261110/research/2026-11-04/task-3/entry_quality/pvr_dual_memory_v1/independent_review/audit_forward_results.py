"""Recount frozen-ticket saved price diagnostics, not new signals/accounts."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;BASE=HERE.parent;R=BASE/'results'
KEY=['window','day','sid'];DAY=['family','period','window','day'];ROW=DAY+['arm']
MET=['ret20_open','mfe20_open','mae20_open','ret20_close','mfe20_close','mae20_close']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def equal(a,b,keys,cols):
    a=a.sort_values(keys).reset_index(drop=True);b=b.sort_values(keys).reset_index(drop=True)
    assert a[keys].equals(b[keys])
    assert np.allclose(a[cols].to_numpy(float),b[cols].to_numpy(float),rtol=1e-10,atol=1e-12,equal_nan=True)
def main():
    seal=json.loads((R/'COMPLETION.json').read_text());assert seal['status']=='COMPLETE_FIXED_EQUAL_TICKET_PRICE_DIAGNOSIS_NOT_ACCOUNT'
    for p,h in seal['sources'].items():assert sha(p)==h,p
    for n,h in seal['outputs'].items():assert sha(R/n)==h,n
    lockpath=BASE/'ranks/COMPLETION_PRE_FUTURE_LABELS.json';lock=json.loads(lockpath.read_text())
    for n,h in lock['outputs'].items():assert sha(lockpath.parent/n)==h,n
    ranks=pd.read_parquet(BASE/'ranks/ALL_FAMILY_RANKS_PRE_LABEL.parquet')
    labelpath=BASE.parent/'pvr_conditional_information_v1/path20_labels/PATH20_LABELS.parquet'
    y=pd.read_parquet(labelpath,columns=KEY+['path20_complete']+MET)
    x=ranks.merge(y,on=KEY,validate='many_to_one');assert x.path20_complete.notna().all()
    expected=[];supports=[]
    for(fam,window,day),g in x.groupby(['family','window','day'],sort=True):
        arms=['PVR','FAST']+(['SLOW','CONT']if fam=='COMMON'else[]);K=int(g.K.iloc[0]);N=len(g)
        known=g.path20_complete.astype(bool);union=g[['pick_'+a for a in arms]].any(axis=1);matched=bool(known[union].all());U=int((~known).sum())
        supports.append(dict(family=fam,period=g.period.iloc[0],window=window,day=day,N=N,K=K,selected_union=int(union.sum()),unknown_union=int((union&~known).sum()),matched_all_arms=matched,pool_unknown=U,pool_known=N-U))
        for arm in arms:
            pick=g['pick_'+arm].astype(bool);v=g[pick&known];u=int((pick&~known).sum());assert pick.sum()==K
            row=dict(family=fam,period=g.period.iloc[0],window=window,day=day,arm=arm,N=N,K=K,known_selected=len(v),unknown_selected=u,matched_all_arms=matched,pool_unknown=U,pool_known=N-U,
                selected_slow_unknown=int((pick&g.E_slow.isna()).sum()),selected_PVR_unknown=int((pick&g.score.isna()).sum()),fast_nonpositive_count=int((pick&g.E_fast.le(0)).sum()),slow_nonpositive_count=int((pick&g.E_slow.le(0)).sum()))
            for m in MET:row['mean_'+m]=v[m].mean()
            for q in [.1,.5,.9]:row['terminal_q'+str(int(q*100))]=np.quantile(v.ret20_open,q)if len(v)else np.nan
            row['negative_terminal_fraction']=v.ret20_open.lt(0).mean()if len(v)else np.nan
            for name,metric in [('peak30','mfe20_open'),('terminal30','ret20_open')]:
                tail=known&g[metric].ge(.30);T=int(tail.sum());a=int((pick&tail).sum())
                row.update({name+'_pool_known_tails':T,name+'_selected_known_tails':a,name+'_precision_lower':a/K,name+'_precision_upper':(a+u)/K,
                    name+'_known_capture':a/T if T else np.nan,name+'_capture_lower':a/(T+U-u)if T else np.nan,name+'_capture_upper':(a+u)/(T+u)if T else np.nan,
                    name+'_lost_PVR_tails':int((tail&g.pick_PVR&~pick).sum()),name+'_gained_PVR_tails':int((tail&pick&~g.pick_PVR).sum())})
            expected.append(row)
    e=pd.DataFrame(expected);s=pd.DataFrame(supports);got=pd.read_parquet(R/'ALL_FIXED_PICK_DAY_DIAGNOSTICS.parquet')
    cols=[c for c in e if c not in ROW];equal(e,got,ROW,cols)
    equal(s,pd.read_csv(R/'MATCHED_DAY_SUPPORT.csv'),DAY,[c for c in s if c not in DAY])
    m=e[e.matched_all_arms];assert (m.known_selected==m.K).all()and(m.unknown_selected==0).all()
    metrics=['mean_'+z for z in MET]+['terminal_q10','terminal_q50','terminal_q90','negative_terminal_fraction']+[t+'_'+z for t in ['peak30','terminal30']for z in ['precision_lower','precision_upper','known_capture','capture_lower','capture_upper']]
    summary=pd.read_csv(R/'MATCHED_DAY_EQUAL_SUMMARY.csv');periodkey=['family','period','arm']
    for key,g in m.groupby(periodkey):
        row=summary.set_index(periodkey).loc[key]
        assert row.matched_dates==len(g)and row.source_picks==g.K.sum()and row.known_selected==g.known_selected.sum()and row.unknown_selected==0
        assert np.allclose(row[metrics].to_numpy(float),g[metrics].mean().to_numpy(float),rtol=1e-10,atol=1e-12,equal_nan=True)
        for t in ['peak30','terminal30']:
            assert row[t+'_tail_opportunity_dates']==g[t+'_pool_known_tails'].gt(0).sum()
            for c in ['pool_known_tails','selected_known_tails','lost_PVR_tails','gained_PVR_tails']:assert row[t+'_'+c]==g[t+'_'+c].sum()
    cov=pd.read_csv(R/'ALL_SOURCE_PICK_COVERAGE.csv').set_index(periodkey);bounds=pd.read_csv(R/'ALL_SOURCE_TAIL_PRECISION_BOUNDS.csv').set_index(periodkey)
    for key,g in e.groupby(periodkey):
        row=cov.loc[key];b=bounds.loc[key];K=int(g.K.sum());u=int(g.unknown_selected.sum())
        assert row.source_dates==len(g)and row.source_picks==K and row.known_selected==int(g.known_selected.sum())and row.unknown_selected==u
        assert row.matched_dates==int(g.matched_all_arms.sum())and row.matched_picks==int(g.loc[g.matched_all_arms,'K'].sum())
        for t in ['peak30','terminal30']:
            a=int(g[t+'_selected_known_tails'].sum());assert b[t+'_known_tails']==a
            assert np.isclose(b[t+'_precision_count_lower'],a/K)and np.isclose(b[t+'_precision_count_upper'],(a+u)/K)
    base=m[m.arm=='PVR'][['family','window','day']+metrics]
    diff=m.merge(base,on=['family','window','day'],suffixes=('','_PVR'),validate='many_to_one')
    for z in metrics:diff['delta_'+z]=diff[z]-diff[z+'_PVR']
    dc=['delta_'+z for z in metrics]
    equal(diff,pd.read_parquet(R/'MATCHED_DAY_ARM_DELTAS_VS_PVR.parquet'),ROW,dc)
    d=diff.groupby(periodkey)[dc].mean().reset_index();equal(d,pd.read_csv(R/'MATCHED_DAY_EQUAL_DELTAS_VS_PVR.csv'),periodkey,dc)
    calpath=BASE.parent/'pvr_information_v1/export/FEATURE_MANIFEST_PRE_LABEL.json';cal=json.loads(calpath.read_text())['calendars']
    calendar=pd.DataFrame([dict(window=w,day=d,block20=j//20)for w,ds in cal.items()for j,d in enumerate(ds)])
    blocks=diff.merge(calendar,on=['window','day'],validate='many_to_one').groupby(['family','period','window','block20','arm'])[dc].mean().reset_index()
    equal(blocks,pd.read_csv(R/'FIXED20_SESSION_BLOCK_DELTAS.csv'),['family','period','window','block20','arm'],dc)
    bs=pd.read_csv(R/'FIXED20_SESSION_BLOCK_SUMMARY.csv').set_index(periodkey+['metric'])
    for key,g in blocks.groupby(periodkey):
        for z in ['delta_mean_ret20_open','delta_peak30_precision_lower','delta_mean_mae20_open']:
            row=bs.loc[(*key,z)];assert row.blocks==len(g)and row.positive_blocks==g[z].gt(0).sum()and row.negative_blocks==g[z].lt(0).sum()
    cases=[]
    for period in ['DEV_2022_23','DIAG_2024','DIAG_2025H2_2026H1']:
        cont=d[(d.family=='COMMON')&(d.period==period)&(d.arm=='CONT')].iloc[0]
        source=s[(s.family=='COMMON')&(s.period==period)]
        cp=bounds.loc[('COMMON',period,'CONT')];pv=bounds.loc[('COMMON',period,'PVR')]
        overlap=max(cp.peak30_precision_count_lower,pv.peak30_precision_count_lower)<=min(cp.peak30_precision_count_upper,pv.peak30_precision_count_upper)
        cases.append(dict(period=period,COMMON_source_dates=len(source),COMMON_matched_dates=int(source.matched_all_arms.sum()),matched_CONT_minus_PVR_terminal_pp=100*cont.delta_mean_ret20_open,
            fullsource_CONT_known_peaktails=int(cp.peak30_known_tails),fullsource_PVR_known_peaktails=int(pv.peak30_known_tails),CONT_unknown_selected=int(cp.unknown_selected),PVR_unknown_selected=int(pv.unknown_selected),fullsource_peak_precision_bounds_overlap=bool(overlap)))
    ds=pd.read_csv(BASE/'ranks/DAY_POOL_AND_CORRELATION_PRE_LABEL.csv');correlations={p:float(g.fast_slow_spearman.median())for p,g in ds[ds.family=='COMMON'].groupby('period')}
    result=dict(status='PASS_BOUNDED_FIXED_TICKET_FORWARD_DIAGNOSTICS_AND_MISSING_BOUNDS_WITH_LIMITS',source_day_arm_rows=len(e),matched_day_arm_rows=len(m),
        all_frozen_rank_output_SHA_unchanged=True,all_sameK_union_support_metrics_quantiles_tails_and_sharp_bounds_recounted=True,
        all_matched_day_equal_summaries_source_counts_deltas_and_calendar_blocks_verified=True,
        principal_checks=cases,prelabel_fast_slow_median_Spearman=correlations,
        interpretation=['COMMON CONT matched terminal deltas are negative but matched dates selectively exclude unknown union tickets; not all-source degradation proof','Fullsource tail precision bounds overlap; observed known tail counts do not rank unknown outcomes','Known capture means only overT>0 pool-tail opportunity dates, not all matched dates','Summary terminal q10/q50/q90 are date-level selected-pool quantiles averaged equally across dates, not pooled period quantiles','Disjoint e windows are not statistically independent; observed weak correlation is not incremental predictive gain'],
        limits=['No new rawprice label reconstruction; reuse prior independently audited complete20shared-session labels','No real probe/permission/orders/funding or account return','COMMON versus FAST_ONLY differ in cohort and K; no free2K union improvement','Repeated stock-day and overlapping20session labels dependent, static universe and industry nonPIT','All historical periods previously consumed; no true unseen OOS or parameter validation proof'],remaining_blocks_for_reviewed_saved_scope=[],new_accounts=0,new_signals_or_scores=0,
        sources={str(p.resolve()):sha(p)for p in [R/'COMPLETION.json',R/'ALL_FIXED_PICK_DAY_DIAGNOSTICS.parquet',R/'MATCHED_DAY_SUPPORT.csv',R/'MATCHED_DAY_EQUAL_SUMMARY.csv',R/'ALL_SOURCE_TAIL_PRECISION_BOUNDS.csv',R/'ALL_SOURCE_PICK_COVERAGE.csv',R/'FIXED20_SESSION_BLOCK_SUMMARY.csv',BASE/'evaluate_frozen.py',BASE/'ranks/COMPLETION_PRE_FUTURE_LABELS.json',HERE/'RANK_SOURCE_AUDIT.json',HERE/'DUAL_INPUT_AUDIT.json',Path(__file__)]})
    out=HERE/'FORWARD_RESULT_AUDIT.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'principal_checks':cases,'correlations':correlations},ensure_ascii=False));print('AUDIT_SHA256',sha(out))

if __name__=='__main__':main()
