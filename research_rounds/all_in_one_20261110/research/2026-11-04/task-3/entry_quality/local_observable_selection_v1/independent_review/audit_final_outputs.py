"""Read-only saved-row audit. No indicator, account, or forward-label execution."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=Path(__file__).resolve().parent
KEY=['sid','day']
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p): return json.loads(Path(p).read_text())
def half_rank(v):
    # Independent integer form of twice average ascending rank minus two.
    vv=sorted(v.tolist()); out={}; i=0
    while i<len(vv):
        j=i+1
        while j<len(vv) and vv[j]==vv[i]: j+=1
        out[vv[i]]=i+j-1
        i=j
    return v.map(out).astype('int64')
def same(a,b):
    np.testing.assert_allclose(np.asarray(a,float),np.asarray(b,float),rtol=0,atol=0,equal_nan=True)
def main():
    binds={}; checked=0
    for sub in ['ranks','cache_comparison']:
        p=ROOT/sub/'COMPLETION.json'; c=load(p); binds[str(p)]=sha(p)
        for source,h in c['sources'].items():
            assert sha(source)==h,(source,'source hash'); checked+=1
        for name,h in c['outputs'].items():
            assert sha(ROOT/sub/name)==h,(name,'output hash'); checked+=1
    x=pd.read_parquet(ROOT/'features/LOCAL_FIXED_DATE_FEATURES.parquet')
    a=pd.read_parquet(ROOT/'ranks/ALL_FIXED_DATE_RANKS.parquet')
    oldpath=next(p for p in load(ROOT/'ranks/COMPLETION.json')['sources'] if p.endswith('STOCK_MANIFEST.json'))
    old={r['symbol'] for r in load(oldpath)}
    dates=sorted(x.day.unique()); assert len(dates)==7 and len(x)==38619 and x.sid.nunique()==5517
    assert not x.duplicated(KEY).any() and x.groupby('day').size().eq(5517).all()
    assert len(a)==50386 and not a.duplicated(['scope']+KEY).any()
    assert a.groupby('scope').size().to_dict()=={'FULL_LOCAL':38619,'OLD1709_EXACT_SUBPOOL':11767}
    full=a[a.scope.eq('FULL_LOCAL')].set_index(KEY).sort_index()
    # Source fields must be unchanged by ranking, including missing-target rows.
    pd.testing.assert_frame_equal(full[x.columns.difference(KEY)].sort_index(axis=1),x.set_index(KEY).sort_index()[x.columns.difference(KEY)].sort_index(axis=1))
    assert full.in_old1709_exact.eq(full.index.get_level_values('sid').isin(old)).all()
    sub=a[a.scope.eq('OLD1709_EXACT_SUBPOOL')]
    assert set(sub.sid)==set(x.sid)&old and sub.groupby('day').size().eq(1681).all()
    present=x.target_row_present
    assert x.target_status.eq('OBSERVED_TARGET_BAR').equals(present)
    for value,status,minobs in [('score','pvr_status',85),('e','e_status',65),('E_fast','fast_status',69),('E_slow','slow_status',127)]:
        known=np.isfinite(x[value]); assert np.array_equal(known,x[status].eq('KNOWN'))
        assert np.array_equal(known,present & x.pvr_valid_observation.eq(True) & x.current_block_observations_through_t.ge(minobs))
    assert np.all(x.loc[np.isfinite(x.E_slow),'E_fast'].notna())
    same(x.current_close_qfq,x.raw_close*x.qfq_adjustment_factor)
    same(x.current_amount_passthrough,x.raw_amount)
    same(x.qfq_adjustment_factor,x.raw_adjustment_factor/x.reference_adjustment_factor)
    top=[]; groups=[]
    for (scope,day),g in a.groupby(['scope','day']):
        for queue,col in [('PVR','score'),('FAST','E_fast')]:
            q=g[g.target_row_present & np.isfinite(g[col])]
            expected=q.sort_values([col,'sid'],ascending=[False,True])
            assert expected['rank_'+queue].tolist()==list(range(1,len(q)+1)),(scope,day,queue)
            assert g['N_'+queue].eq(len(q)).all()
            assert g.loc[~g.index.isin(q.index),'rank_'+queue].isna().all()
            if queue=='FAST': same(q.p_start,half_rank(q.E_fast)/(2*(len(q)-1)))
            top.extend((scope,day,queue,sid,r+1) for r,sid in enumerate(expected.sid.head(20)))
        q=g[g.target_row_present & np.isfinite(g.E_fast)&np.isfinite(g.E_slow)]
        af=half_rank(q.E_fast); bs=half_rank(q.E_slow); den=2*(len(q)-1)
        same(q.p_fast_CONT,af/den); same(q.p_slow_CONT,bs/den)
        num=3*af+7*bs
        same(q.CONT_exact_numerator,num); same(q.S_cont,num/(20*(len(q)-1)))
        expected=q.assign(independent_num=num).sort_values(['independent_num','sid'],ascending=[False,True])
        assert expected.rank_CONT.tolist()==list(range(1,len(q)+1))
        assert g.N_CONT.eq(len(q)).all() and g.loc[~g.index.isin(q.index),'rank_CONT'].isna().all()
        top.extend((scope,day,'CONT',sid,r+1) for r,sid in enumerate(expected.sid.head(20)))
        groups.append(dict(scope=scope,day=day,PVR=int(g.rank_PVR.notna().sum()),FAST=int(g.rank_FAST.notna().sum()),CONT=len(q),CONT_tie_excess=int(num.duplicated().sum())))
    saved=pd.read_csv(ROOT/'ranks/ALL_TOP20_LISTS.csv')
    got=set(saved[['scope','day','queue','sid','queue_rank']].itertuples(index=False,name=None))
    assert got==set(top) and len(saved)==840
    assert saved.groupby(['scope','day','queue']).size().eq(20).all()
    assert len(saved[saved.scope.eq('FULL_LOCAL')])==420
    cov=pd.read_csv(ROOT/'ranks/COVERAGE_AND_TOP20_OLD_POOL_EXCLUSIONS.csv')
    coverage=[]
    for day,g in a[a.scope.eq('FULL_LOCAL')].groupby('day'):
        z=cov[cov.day.eq(day)].iloc[0]
        for col,val in [('mother',len(g)),('observed',g.target_row_present.sum()),('missing_target_bar',(~g.target_row_present).sum()),('old_in_canonical',g.in_old1709_exact.sum()),('old_not_in_canonical',28),('fast_ready_slow_notready',(g.rank_FAST.notna()&g.rank_CONT.isna()).sum())]: assert z[col]==val,(day,col)
        for queue,value in [('PVR','score'),('FAST','E_fast'),('CONT','CONT_exact_numerator')]:
            t=g[g['rank_'+queue].le(20)]
            assert z[queue+'_ready']==g['rank_'+queue].notna().sum()
            assert z[queue+'_top20_outside_old']==(~t.in_old1709_exact).sum()
            assert z[queue+'_score_ties']==g.loc[g['rank_'+queue].notna(),value].duplicated().sum()
            assert z[queue+'_top20_current_ST_name']==t.current_name_contains_ST_snapshot.sum()
        coverage.append({k:(v.item() if hasattr(v,'item') else v) for k,v in z.items()})
    # Saved global cache summaries: independently aggregate saved comparisons only.
    c=pd.read_csv(ROOT/'cache_comparison/ALL_EXACT_OLD_SYMBOL_DATE_COMPARISONS.csv')
    cs=pd.read_csv(ROOT/'cache_comparison/PVR_CACHE_COMPARISON_BY_DATE.csv')
    assert len(c)==11767 and not c.duplicated(KEY).any()
    for day,g in c.groupby('day'):
        z=cs[cs.day.eq(day)].iloc[0]; mask=np.isfinite(g.score_new)&np.isfinite(g.score_old)
        assert int(z.both_PVR_known)==mask.sum()
        for col in ['r','scale','u','b','e','E','score']:
            d=(g.loc[mask,col+'_new']-g.loc[mask,col+'_old']).abs()
            assert abs(z[col+'_max_abs_difference']-d.max())<2e-12
            assert int(z[col+'_within_1e8'])==d.le(1e-8).sum()
        assert abs(z.amount_ref_new_old_median_ratio-(g.loc[mask,'amount_ref_new']/g.loc[mask,'amount_ref_old']).median())<1e-15
    dc=pd.read_csv(ROOT/'cache_comparison/OLD_PENDING_DUAL_CACHE_COMPARISONS_DIAGNOSTIC_ONLY.csv')
    ds=pd.read_csv(ROOT/'cache_comparison/DUAL_CACHE_COMPARISON_BY_DATE.csv')
    for day,g in dc.groupby('day'):
        z=ds[ds.day.eq(day)].iloc[0]; assert z.old_pending_derived_overlap_only==len(g)
        for col in ['E_fast','E_slow']:
            m=np.isfinite(g[col+'_new'])&np.isfinite(g[col+'_old']);d=(g.loc[m,col+'_new']-g.loc[m,col+'_old']).abs()
            assert z[col+'_both_known']==m.sum() and z[col+'_within_1e8']==d.le(1e-8).sum()
            assert abs(z[col+'_max_abs_difference']-d.max())<2e-12
    for p in [ROOT/'features/RUN_RECEIPT.json',ROOT/'features/PREFIX_CHECKS.json',ROOT/'features/INDEPENDENT_REFERENCE_CHECKS.json',ROOT/'features/derive.py',ROOT/'features/export_once.py',ROOT/'rank_fixed_dates.py',ROOT/'compare_saved_cache.py',Path(__file__),OUT/'FOUR_SOURCE_COMPARISON_AUDIT.json',OUT/'THREE_MAX_DIFFERENCE_AUDIT.json']:
        binds[str(p.resolve())]=sha(p)
    result=dict(status='PASS_ALL_SAVED_RANKS_AND_COUNTS_WITH_SOURCE_LIMITS',scope='All38619 feature rows,50386 scope-rank rows,42 queue-date-scope top20 lists,840 selected rows; all saved cache summary aggregates. No raw-source or indicator rerun.',source_output_hashes_checked=checked,coverage=coverage,groups=groups,cache_summary=cs[['day','both_PVR_known','score_within_1e8','score_max_abs_difference']].to_dict('records'),remaining_implementation_blocks=[],limits=['Stock-score universe, not native E0/I/CP/order eligibility;5517 current canonical source symbols, not historical all-market PIT universe.','Full5517 H1 unavailable: exact score ties use symbol; old subset recomputes percentiles within its own pool.','decision_at15:00+08 is a nominal close index, not historical publication, receive, availability or execution evidence.','Qfq fixed terminal normalization cancels analytically; factor vintage is not PIT. Same-snapshot prefix checks do not certify historical vintages.','Current names and ST text are annotations, not historical issuer/ST status.','Old/new cache differences persist; old pending dual cache is diagnostic overlap only. No values overwritten or source provider correctness certified.','Four-stock and three-max-difference raw/pure-function checks are separately bounded receipts; exporter full-history/reference and prefix receipts are source-bound rather than independently rerun here.','No accounts, executions, future outcomes, source refreshes, parameter scans or indicator recalculations in this final audit.'],bindings=binds)
    p=OUT/'FINAL_OUTPUT_AUDIT.json';p.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'status':result['status'],'receipt':str(p),'sha256':sha(p),'rank_rows':len(a),'top_rows':len(saved),'PVR_top20_outside_old':[r['PVR_top20_outside_old']for r in coverage]},ensure_ascii=False))
if __name__=='__main__':main()
