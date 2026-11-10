"""Audit exact rational-score ordering using saved ranks, without any refit."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;BASE=HERE.parent;OLD=BASE/'run_v1';NEW=BASE/'run_v1_exact_ties'
GROUP=['window','day','sector'];KEY=['window','day','sid']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    comp=json.loads((NEW/'COMPLETION.json').read_text())
    assert comp['status']=='COMPLETE_EXACT_MATHEMATICAL_TIES_FROM_SAVED_ONLY'
    for p,h in comp['sources'].items():assert sha(p)==h,p
    for n,h in comp['outputs'].items():assert sha(NEW/n)==h,n
    old=pd.read_parquet(OLD/'ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet');x=pd.read_parquet(NEW/'ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet')
    assert len(x)==len(old)==133713 and x[KEY].equals(old[KEY])
    changed_cols={'S','S_naive_RS','S_isotonic','S_common_rank','S_naive_RS_common_rank','S_isotonic_common_rank','hybrid_S_pending_slot','hybrid_S_isotonic_pending_slot','hybrid_S_sector_rank','hybrid_S_isotonic_sector_rank'}
    for c in old.columns:
        if c not in changed_cols:assert x[c].equals(old[c]),c
    known=x.rank_status.eq('KNOWN');assert known.sum()==49612
    names={'S':'residual_percentile','S_naive_RS':'q','S_isotonic':'isotonic_residual_percentile'}
    counts={};num={}
    for name,part in names.items():
        n=x.loc[known,'n_common'].to_numpy(int);scale=2*(n-1)
        grid=x.loc[known,['p',part,'structure_percentile']].to_numpy(float)*scale[:,None]
        integer=np.rint(grid).astype(np.int64);assert np.max(np.abs(grid-integer))<1e-10
        numerator=integer@np.array([5,3,2],dtype=np.int64);num[name]=numerator
        assert np.array_equal(x.loc[known,name+'_exact_numerator'].to_numpy(np.int64),numerator)
        assert np.array_equal(x.loc[known,name].to_numpy(float),numerator/(20*(n-1)))
        assert np.max(np.abs(old.loc[known,name].to_numpy(float)-x.loc[known,name].to_numpy(float)))<=5e-16
        count=int((old.loc[known,name+'_common_rank']!=x.loc[known,name+'_common_rank']).sum());counts[name]=count
        for _,g in x.loc[known].groupby(GROUP,sort=False):
            order=sorted(g.index,key=lambda j:(-int(x.at[j,name+'_exact_numerator']),int(x.at[j,'original_H1_rank']),x.at[j,'sid']))
            assert x.loc[order,name+'_common_rank'].tolist()==list(range(1,len(order)+1))
            if name!='S_naive_RS':
                dest='hybrid_S_pending_slot'if name=='S'else'hybrid_S_isotonic_pending_slot'
                assert x.loc[order,dest].tolist()==sorted(g.original_PVR_slot.tolist())
    assert counts=={'S':929,'S_naive_RS':788,'S_isotonic':753}
    for col in ['hybrid_S_pending_slot','hybrid_S_isotonic_pending_slot']:
        assert x.loc[~known,col].equals(old.loc[~known,col])
        for _,g in x.groupby(GROUP,sort=False):assert sorted(g[col])==sorted(g.original_PVR_slot)
        for _,g in x.groupby(['window','day'],sort=False):assert g.set_index(col).sector.sort_index().equals(g.set_index('original_PVR_slot').sector.sort_index())
    audit=json.loads((NEW/'NUMERIC_ORDER_AUDIT.json').read_text());assert audit['changed_rank_rows']==counts
    bywindow={}
    for w,g in x.loc[known].groupby('window'):
        bywindow[w]=dict(known_rows=len(g),S_vs_isotonic_changed_rows=int((g.S_common_rank!=g.S_isotonic_common_rank).sum()),S_vs_PVR_changed_rows=int((g.hybrid_S_pending_slot!=g.original_PVR_slot).sum()))
        expected=next(r for r in audit['by_window']if r['window']==w)
        for k,v in bywindow[w].items():assert expected[k]==v
    assert sum(r['S_vs_isotonic_changed_rows']for r in bywindow.values())==22058
    earlyold=pd.read_csv(OLD/'EARLY_FIXED_CASE_TABLE.csv');earlynew=pd.read_csv(NEW/'EARLY_FIXED_CASE_TABLE.csv')
    assert len(earlynew)==15 and earlyold[KEY].equals(earlynew[KEY])
    rankcols=['S_common_rank','S_naive_RS_common_rank','S_isotonic_common_rank','hybrid_S_pending_slot','hybrid_S_sector_rank','hybrid_S_isotonic_pending_slot','hybrid_S_isotonic_sector_rank']
    earlychanges={k:int((~((earlynew[k]==earlyold[k])|(earlynew[k].isna()&earlyold[k].isna()))).sum())for k in rankcols}
    targetsold=pd.read_csv(OLD/'ALL_FIXED_TARGET_DATES.csv');targetsnew=pd.read_csv(NEW/'ALL_FIXED_TARGET_DATES.csv')
    assert len(targetsnew)==151 and targetsold[KEY].equals(targetsnew[KEY])
    targetchanges={k:int((~((targetsnew[k]==targetsold[k])|(targetsnew[k].isna()&targetsold[k].isna()))).sum())for k in rankcols}
    examples=x.loc[(x.sid.isin(['300666.SZ','688123.SH']))&x.day.eq('2025-09-24'),KEY+['sector','n_common','p','q','residual_percentile','structure_percentile','S','S_exact_numerator','PVR_sector_rank','hybrid_S_sector_rank','S_naive_RS_common_rank','S_isotonic_common_rank']].to_dict('records')
    original_review=json.loads((HERE/'SAVED_RANK_AUDIT.json').read_text());assert original_review['manual_group_count']==10 and original_review['manual_group_rows']==217
    result=dict(status='PASS_BOUNDED_EXACT_TIE_CORRECTION_AND_SAVED_RANK_OBSERVATION_WITH_LIMITS',original_rows=133713,known_rows=49612,known_groups=3083,
        no_cohort_feature_PVR_RS_structural_percentile_OLS_or_isotonic_fit_changes=True,exact_half_rank_formula='S=(5A+3B+2C)/(20*(n-1)), A=2(n-1)p, B=2(n-1)residual_pct, C=2(n-1)structure_pct; all integers',
        corrected_raw_IEEE_rank_rows=counts,exact_by_window=bywindow,all_unknown_slots_and_sector_slot_patterns_fixed=True,
        fixed_early15_rank_changes=earlychanges,fixed_all151_rank_changes=targetchanges,jiangbolong_and_peer_sep24=examples,
        inherited_manual_arithmetic_scope='15 fixed cases:10 fitted sector-day groups/217 rows using exact Fraction OLS and independent min-max isotonic, not all3083 fits. Known low ratios/dates checked only on15target rows saved tenclose evidence.',
        limits=['Descriptive ranking sidecar only; no actual fund allocation or PNL counterfactual','No all-source price/RS20 endpoints/feature reconstruction','Static original candidate and industry universe are nonPIT and old-account-path-dependent','Weights/n10/linear-vs-isotonic are prior form assumptions, not independent alpha proof','Native financial numeric rank-key wiring not executed; pending ordinals are distinct','Any case profit/loss annotations are post-score context, not numerical audit of new economics'],
        remaining_blocks_for_reviewed_static_scope=[],new_model_or_fit_runs=0,new_accounts=0,
        source_sha256={str(p.resolve()):sha(p)for p in [NEW/'COMPLETION.json',NEW/'NUMERIC_ORDER_AUDIT.json',NEW/'ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet',NEW/'EARLY_FIXED_CASE_TABLE.csv',NEW/'ALL_FIXED_TARGET_DATES.csv',BASE/'EXACT_TIE_CLARIFICATION.json',BASE/'exact_ties_from_saved.py',HERE/'SAVED_RANK_AUDIT.json',Path(__file__)]})
    out=HERE/'EXACT_TIE_AND_FINAL_RANK_AUDIT.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['status','corrected_raw_IEEE_rank_rows','exact_by_window','fixed_early15_rank_changes','fixed_all151_rank_changes']},ensure_ascii=False));print('AUDIT_SHA256',sha(out))

if __name__=='__main__':main()
