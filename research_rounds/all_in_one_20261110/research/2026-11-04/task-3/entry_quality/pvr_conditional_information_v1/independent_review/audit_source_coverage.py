"""Pre-label counts only. No future prices, label files, new score or fitting."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;BASE=HERE.parent
SOURCE=BASE.parent/'pvr_residual_ranking_v1/run_v1_exact_ties/ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet'
FEATURES={'RS20':'relative_return20','frontier':'close_gap_prior_high20','low_improvement':'low_improvement'}
PERIOD=['2022_23','2024','2025H2_2026H1']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def summarize(x,group):
    # Original PVR slot already embodies native round12 plus H1 tie ordering.
    known=x[np.isfinite(x.score)].copy();known['N']=known.groupby(group).sid.transform('size')
    eligible=known[known.N>=10].sort_values(group+['original_PVR_slot']).copy()
    eligible['ordinal']=eligible.groupby(group).cumcount()+1
    eligible['decile']=1+(10*(eligible.ordinal-1)//eligible.N)
    assert eligible.decile.between(1,10).all()
    cell=group+['decile'];base=eligible.groupby(cell,sort=False).agg(n=('sid','size')).reset_index()
    result={}
    for period in PERIOD:
        p=x[x.period==period];k=known[known.period==period];e=eligible[eligible.period==period];b=base.merge(e[cell+['period']].drop_duplicates(),on=cell,validate='one_to_one');b=b[b.period==period]
        nsmall=e.loc[e.N<20].groupby(group).N.first()
        if len(nsmall):
            s=e[e.N<20].groupby(cell).size()
            assert (s<=2).all()
            assert int((s==2).sum())==int((nsmall-10).sum())
        result[period]=dict(original_rows=len(p),finite_PVR_rows=len(k),PVR_Nge10_rows=len(e),PVR_Nge10_groups=e.groupby(group).ngroups,
            decile_cells=len(b),singleton_cells=int((b.n==1).sum()),N10_19_groups=len(nsmall),
            N10_19_decile_doubleton_cells=int((nsmall-10).sum()),N10_19_possible_doubleton_rows=int(2*(nsmall-10).sum()))
    perfeature={}
    for name,col in FEATURES.items():
        z=eligible.copy();z['median']=z.groupby(cell)[col].transform('median')
        z['LOW']=np.isfinite(z[col])&(z[col]<z['median']);z['HIGH']=np.isfinite(z[col])&(z[col]>z['median'])
        z['NEUTRAL']=np.isfinite(z[col])&(z[col]==z['median']);z['UNKNOWN_FEATURE']=~np.isfinite(z[col])
        c=z.groupby(cell,sort=False).agg(n=('sid','size'),low=('LOW','sum'),high=('HIGH','sum'),neutral=('NEUTRAL','sum'),unknown=('UNKNOWN_FEATURE','sum')).reset_index()
        c['has_two_arms']=(c.low>0)&(c.high>0)
        z=z.merge(c[cell+['has_two_arms']],on=cell,validate='many_to_one')
        f={}
        for period in PERIOD:
            p=z[z.period==period];b=c.merge(p[cell].drop_duplicates(),on=cell,validate='one_to_one');paired=b[b.has_two_arms]
            involved=p[p.has_two_arms&(p.LOW|p.HIGH)]
            f[period]=dict(fixed_decile_cells=len(b),cells_two_strict_arms=len(paired),cells_no_comparison=len(b)-len(paired),
                original_cell_member_rows=int(paired.n.sum()),strict_arm_rows=len(involved),low_rows=int(involved.LOW.sum()),high_rows=int(involved.HIGH.sum()),
                neutral_rows_in_comparable_cells=int(paired.neutral.sum()),unknown_feature_rows_in_comparable_cells=int(paired.unknown.sum()),
                comparable_days=involved.day.nunique(),comparable_sectors=involved.sector.nunique(),
                comparable_sector_days=involved[['window','day','sector']].drop_duplicates().shape[0])
        perfeature[name]=f
    return result,perfeature,eligible

def main():
    cols=['window','day','sid','sector','score','original_H1_rank','original_PVR_slot',*FEATURES.values()]
    x=pd.read_parquet(SOURCE,columns=cols);assert len(x)==133713 and not x.duplicated(['window','day','sid']).any()
    x['period']=np.where(x.window.eq('strong'),'2025H2_2026H1',np.where(x.day<'2024-01-01','2022_23','2024'))
    primary,features,e=summarize(x,['window','day','sector'])
    globalbase,globalfeatures,globalrows=summarize(x,['window','day'])
    # Only cell cardinality, never future performance, after global-bin-sector split.
    split=globalrows.groupby(['window','day','decile','sector']).size().reset_index(name='n')
    split['period']=np.where(split.window.eq('strong'),'2025H2_2026H1',np.where(split.day<'2024-01-01','2022_23','2024'))
    splitout={p:dict(groups=len(g),n_ge2_groups=int((g.n>=2).sum()),potential_member_rows=int(g.loc[g.n>=2,'n'].sum()))for p,g in split.groupby('period')}
    totals={name:dict(strict_arm_rows=sum(v['strict_arm_rows']for v in fs.values()),cells_two_strict_arms=sum(v['cells_two_strict_arms']for v in fs.values()),comparable_sector_days=sum(v['comparable_sector_days']for v in fs.values()))for name,fs in features.items()}
    assert sum(r['PVR_Nge10_rows']for r in primary.values())==49612
    assert totals['RS20']['strict_arm_rows']==29948 and totals['RS20']['cells_two_strict_arms']==13635 and totals['RS20']['comparable_sector_days']==2551
    cases=[]
    for sid,day in [('000620.SZ','2022-01-10'),('000620.SZ','2022-01-24')]:
        target=x[x.sid.eq(sid)&x.day.eq(day)].iloc[0]
        group=x[x.window.eq(target.window)&x.day.eq(day)&x.sector.eq(target.sector)&np.isfinite(x.score)]
        ee=e[e.window.eq(target.window)&e.day.eq(day)&e.sector.eq(target.sector)]
        cases.append(dict(sid=sid,day=day,known_PVR_N=len(group),eligible_n=len(ee),decile_sizes=ee.groupby('decile').size().to_dict(),can_have_within_decile_comparison=bool(len(ee)and ee.groupby('decile').size().max()>=2)))
    result=dict(status='PASS_BOUNDED_PRE_LABEL_SOURCE_COVERAGE_ONLY',mother=133713,sector_source_coverage=primary,sector_feature_arm_coverage=features,sector_feature_arm_totals=totals,
        global_source_coverage=globalbase,global_feature_arm_coverage=globalfeatures,global_decile_then_sector_cardinality_only=splitout,fixed_yingxin_coverage=cases,
        exact_N10_19_identity='N-10 doubleton bins,20-N singleton bins; possible member rows2(N-10). N10 yields no comparison.',
        freeze_static_review='No design fatal: original shared sessions, all cell members complete, pre-label median/arms and four-level equal weighting frozen. New main implementation/output not audited here.',
        label_clock_caveat='Old h20_statusKNOWN alone is not entire20shared path; all20 missing/nonobserved/invalid flags must be explicitly false and same source known. New code must compute20extrema, not reuseh60.',
        limits=['No future-label file or future path read in this audit','Feature medians computed only to count source arms, no outcome comparison','Original legal pool and static sector mapping remain old-account/nonPIT','No main implementation or future aggregation PASS yet'],new_accounts=0,new_model_runs=0,new_future_label_runs=0,
        source_sha256={str(p.resolve()):sha(p)for p in [SOURCE,BASE/'FREEZE.json',BASE.parent/'pvr_information_v1/analysis/label_clock.py',Path(__file__)]})
    out=HERE/'PRELABEL_COVERAGE_AUDIT.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'feature_totals':totals,'primary':primary,'yingxin':cases},ensure_ascii=False));print('AUDIT_SHA256',sha(out))

if __name__=='__main__':main()
