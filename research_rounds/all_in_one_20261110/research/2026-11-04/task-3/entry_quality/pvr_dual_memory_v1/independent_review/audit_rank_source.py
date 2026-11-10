"""Audit frozen pools/ranks/topK. No indicator or future-label computation."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;BASE=HERE.parent;R=BASE/'ranks'
KEY=['window','day','sid'];DAY=['window','day']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def avgpct(v):
    order=sorted(range(len(v)),key=lambda j:v[j]);out=np.empty(len(v));j=0
    while j<len(order):
        end=j+1
        while end<len(order)and v[order[end]]==v[order[j]]:end+=1
        for k in order[j:end]:out[k]=(j+end-1)/(2*(len(order)-1))
        j=end
    return out
def main():
    seal=json.loads((R/'COMPLETION_PRE_FUTURE_LABELS.json').read_text())
    assert seal['status']=='RANKS_POOLS_TOPK_FROZEN_BEFORE_LOADING_LABELS'
    for p,h in seal['source_sha256'].items():assert sha(p)==h,p
    for name,h in seal['outputs'].items():assert sha(R/name)==h,name
    f=pd.read_parquet(BASE/'features/DUAL_MEMORY_FEATURES.parquet',columns=KEY+['e','E_fast','E_slow','fast_status','slow_status'])
    old=BASE.parent/'pvr_residual_ranking_v1/run_v1_exact_ties/ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet'
    x=pd.read_parquet(old,columns=KEY+['score','original_H1_rank','original_PVR_slot']).merge(f,on=KEY,validate='one_to_one')
    a=pd.read_parquet(R/'ALL_FAMILY_RANKS_PRE_LABEL.parquet');assert not a.duplicated(['family']+KEY).any()
    ds=pd.read_csv(R/'DAY_POOL_AND_CORRELATION_PRE_LABEL.csv');summary={}
    for family in ['COMMON','FAST_ONLY']:
        good=np.isfinite(x.E_fast)
        if family=='COMMON':good&=np.isfinite(x.E_slow)&np.isfinite(x.score)
        expected=x[good].copy();expected['N']=expected.groupby(DAY).sid.transform('size');expected=expected[expected.N>=10]
        got=a[a.family==family].copy()
        assert got[KEY].reset_index(drop=True).equals(expected[KEY].reset_index(drop=True))
        assert np.array_equal(got.N.to_numpy(int),expected.N.to_numpy(int))
        assert np.array_equal(got.K.to_numpy(int),(expected.N.to_numpy(int)+9)//10)
        arms=['PVR','FAST']+(['SLOW','CONT']if family=='COMMON'else[])
        for _,g in got.groupby(DAY,sort=False):
            N=len(g);K=(N+9)//10
            assert np.allclose(g.p_fast,avgpct(g.E_fast.to_list()),rtol=0,atol=1e-14)
            if family=='COMMON':
                assert np.allclose(g.p_slow,avgpct(g.E_slow.to_list()),rtol=0,atol=1e-14)
                A=np.rint(2*(N-1)*g.p_fast).astype(np.int64);B=np.rint(2*(N-1)*g.p_slow).astype(np.int64)
                assert np.array_equal(g.CONT_numerator.to_numpy(np.int64),3*A+7*B)
                assert np.array_equal(g.S_cont.to_numpy(float),(3*A+7*B)/(20*(N-1)))
            for arm in arms:
                if arm=='PVR':order=sorted(g.index,key=lambda j:int(g.at[j,'original_PVR_slot']))
                else:
                    col={'FAST':'E_fast','SLOW':'E_slow','CONT':'CONT_numerator'}[arm]
                    order=sorted(g.index,key=lambda j:(-g.at[j,col],int(g.at[j,'original_H1_rank']),g.at[j,'sid']))
                assert g.loc[order,'rank_'+arm].tolist()==list(range(1,N+1))
                assert np.array_equal(g['pick_'+arm].to_numpy(bool),g['rank_'+arm].to_numpy(int)<=K)
                assert int(g['pick_'+arm].sum())==K
            z=ds[(ds.family==family)&(ds.window==g.window.iloc[0])&(ds.day==g.day.iloc[0])].iloc[0]
            assert z.N==N and z.K==K
            if family=='COMMON':
                assert z.FAST_CONT_overlap==int((g.pick_FAST&g.pick_CONT).sum())
                assert z.FAST_CONT_union==2*K-z.FAST_CONT_overlap
                # Complete finite cohort: avg-rank Pearson is Spearman definition.
                corr=float(np.corrcoef(avgpct(g.E_fast.to_list()),avgpct(g.E_slow.to_list()))[0,1])
                assert (pd.isna(z.fast_slow_spearman)and pd.isna(corr))or np.isclose(z.fast_slow_spearman,corr,rtol=1e-11,atol=1e-12)
        summary[family]=dict(rows=len(got),dates=got.groupby(DAY).ngroups,source_picks_per_arm=int(got.pick_PVR.sum()),native_PVR_unknown_rows=int(got.score.isna().sum()),slow_unknown_rows=int(got.E_slow.isna().sum()))
    assert summary['COMMON']['native_PVR_unknown_rows']==0
    assert summary['FAST_ONLY']['native_PVR_unknown_rows']==141
    fix=json.loads((BASE/'TECHNICAL_CORRELATION_FIX.json').read_text())
    oldtext=(BASE/'rank_and_freeze_pre_scipy_fix.py.txt').read_text();newtext=(BASE/'rank_and_freeze.py').read_text()
    assert "g.E_fast.rank().corr(g.E_slow.rank())" in newtext
    assert "method='spearman'"not in newtext
    result=dict(status='PASS_BOUNDED_PRELABEL_COMMON_FAST_POOLS_EXACT_RANKS_AND_TOPK_WITH_LIMITS',families=summary,
        rank_only_no_future_labels_read=True,all_frozen_pool_identities_and_equal_K_verified=True,
        all_common_CONT_integer_ties_H1_sid_verified=True,all_fast_native_unknown141_retained_in_baseline=True,
        technical_correlation_fix='Average-rank Pearson equals Spearman in finite COMMON cohort; no scipy install, no window/weight/topfraction change.',
        limits=['No complete original history indicator recalculation','No future associations or tail bounds audited in this receipt','COMMON and FAST_ONLY are different pools and cannot be merged as one equal-budget comparison','Fast queue not proof of real probe/E0 event; selected union may cost2K tickets'],
        remaining_blocks_for_reviewed_rank_scope=[],new_accounts=0,new_indicator_runs=0,
        sources={str(p.resolve()):sha(p)for p in [BASE/'FREEZE.json',BASE/'rank_and_freeze.py',BASE/'rank_and_freeze_pre_scipy_fix.py.txt',BASE/'TECHNICAL_CORRELATION_FIX.json',R/'COMPLETION_PRE_FUTURE_LABELS.json',R/'ALL_FAMILY_RANKS_PRE_LABEL.parquet',R/'DAY_POOL_AND_CORRELATION_PRE_LABEL.csv',R/'SOURCE_COVERAGE.csv',HERE/'DUAL_INPUT_AUDIT.json',Path(__file__)]})
    out=HERE/'RANK_SOURCE_AUDIT.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'families':summary}));print('AUDIT_SHA256',sha(out))

if __name__=='__main__':main()
