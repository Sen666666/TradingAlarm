"""Saved-row invariants plus fifteen fixed-case small-group arithmetic only."""
from pathlib import Path
from collections import Counter
from fractions import Fraction as Q
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import hashlib,json,math
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent;BASE=HERE.parent;RUN=BASE/'run_v1'
KEY=['window','day','sid'];GROUP=['window','day','sector']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pct(values):
    s=sorted(range(len(values)),key=lambda j:values[j]);out=[None]*len(s);i=0
    while i<len(s):
        k=i+1
        while k<len(s)and values[s[k]]==values[s[i]]:k+=1
        v=Q(i+k-1,2*(len(s)-1))
        for j in s[i:k]:out[j]=v
        i=k
    return out
def rounded(v):
    with localcontext()as c:
        c.prec=50
        return float((Decimal(v.numerator)/Decimal(v.denominator)).quantize(Decimal('1e-12'),rounding=ROUND_HALF_EVEN))
def close(actual,expected):
    assert np.allclose(np.asarray(actual,float),np.asarray([float(x)for x in expected]),rtol=1e-10,atol=1e-11,equal_nan=True)
def iso_minmax(p,q):
    # Independent max-min weighted interval characterization; no author PAVA.
    unique=sorted(set(p));weights=[p.count(v)for v in unique]
    totals=[sum((q[j]for j in range(len(p))if p[j]==v),Q(0))for v in unique]
    pred={}
    for j,v in enumerate(unique):
        pred[v]=max(min(sum(totals[a:b+1],Q(0))/sum(weights[a:b+1])for b in range(j,len(unique)))for a in range(j+1))
    return [pred[v]for v in p]

def main():
    comp=json.loads((RUN/'COMPLETION.json').read_text());assert comp['status']=='COMPLETE_STATIC_RANK_OBSERVATION_ONLY'
    for p,h in comp['input_sha256'].items():assert sha(p)==h,p
    for n,h in comp['output_sha256'].items():assert sha(RUN/n)==h,n
    x=pd.read_parquet(RUN/'ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet')
    assert len(x)==133713 and not x.duplicated(KEY).any()
    original=[]
    with (BASE.parent/'pvr_information_v1/universe_audit/PRIMARY_CANDIDATES.jsonl').open()as f:
        original=[json.loads(line)for line in f]
    for col in KEY+['roles','original_H1_rank','original_H1_slot','original_PVR_priority_rank','original_PVR_slot']:
        values=x[col].tolist()
        if col=='roles':values=[list(v)for v in values]
        assert values==[r[col]for r in original],col
    ready=x.original_PVR_ready
    assert np.array_equal(x.loc[ready,'score'].to_numpy(float),np.array([r['original_PVR']for r in original if r['original_PVR_ready']],float))
    assert np.isfinite(x.score).equals(ready)
    cv=np.isfinite(x[['score','relative_return20','close_gap_prior_high20','low_improvement']]).all(axis=1)
    assert cv.equals(x.common_valid)
    assert x.groupby(GROUP).sid.transform('size').equals(x.n_legal)
    assert x.groupby(GROUP).common_valid.transform('sum').equals(x.n_common)
    known=x.rank_status.eq('KNOWN');unknown=~known
    assert len(x[known])==49612 and x[known].groupby(GROUP).ngroups==3083
    for dest in ['hybrid_S_pending_slot','hybrid_S_isotonic_pending_slot']:
        assert (x.loc[unknown,dest]==x.loc[unknown,'original_PVR_slot']).all()
        for _,g in x.groupby(GROUP,sort=False):assert sorted(g[dest])==sorted(g.original_PVR_slot)
        for _,g in x.groupby(['window','day'],sort=False):
            assert g.set_index(dest).sector.sort_index().equals(g.set_index('original_PVR_slot').sector.sort_index())
    for col in ['p','q','residual_percentile','structure_percentile','S','S_naive_RS','S_isotonic']:
        assert np.isfinite(x.loc[known,col]).all()and x.loc[known,col].between(0,1).all(),col
    for col,ordercol in [('original_H1_slot','H1_sector_rank'),('original_PVR_slot','PVR_sector_rank'),('hybrid_S_pending_slot','hybrid_S_sector_rank')]:
        expected=x.groupby(GROUP)[col].rank(method='first').astype(int)
        assert expected.equals(x[ordercol]),ordercol
    freeze=json.loads((BASE/'FREEZE.json').read_text());early=pd.read_csv(RUN/'EARLY_FIXED_CASE_TABLE.csv',dtype={'sid':str})
    assert set(early.sid+'|'+early.day)==set(freeze['early_table_dates'])and len(early)==15
    sample_keys=x.merge(early[KEY],on=KEY,validate='one_to_one')[GROUP].drop_duplicates()
    sampled=[];groups=0;rows=0;round_sensitive=[]
    for k in sample_keys.itertuples(index=False,name=None):
        g=x.loc[x.window.eq(k[0])&x.day.eq(k[1])&x.sector.eq(k[2])&known].copy()
        target=early.loc[early.window.eq(k[0])&early.day.eq(k[1])]
        if g.empty:
            assert (target.rank_status!='KNOWN').all()
            sampled.append(dict(group=list(k),status='UNKNOWN_NO_FIT'));continue
        n=len(g);assert n>=10
        pp=pct(g.PVR_round12.tolist());qq=pct(g.relative_return20.tolist());pm=sum(pp,Q(0))/n;qm=sum(qq,Q(0))/n
        b=max(Q(0),sum(((p-pm)*(q-qm)for p,q in zip(pp,qq)),Q(0))/sum(((p-pm)**2 for p in pp),Q(0)));a=qm-b*pm
        residual=[q-a-b*p for p,q in zip(pp,qq)];rr=pct([rounded(r)for r in residual])
        hp=pct(g.close_gap_prior_high20.tolist());lp=pct(g.low_improvement.tolist());raw=[(h+l)/2 for h,l in zip(hp,lp)];shape=pct([rounded(v)for v in raw])
        isop=iso_minmax(pp,qq);isor=[q-v for q,v in zip(qq,isop)];isorank=pct([rounded(v)for v in isor])
        expected={'p':pp,'q':qq,'OLS_prediction':[a+b*p for p in pp],'OLS_residual':residual,'residual_percentile':rr,'frontier_percentile':hp,'low_percentile':lp,'structure_raw':raw,'structure_percentile':shape,'isotonic_prediction':isop,'isotonic_residual':isor,'isotonic_residual_percentile':isorank,'S':[Q(1,2)*p+Q(3,10)*r+Q(1,5)*s for p,r,s in zip(pp,rr,shape)],'S_isotonic':[Q(1,2)*p+Q(3,10)*r+Q(1,5)*s for p,r,s in zip(pp,isorank,shape)]}
        for name,v in expected.items():close(g[name],v)
        for score,dest in [('S','hybrid_S_pending_slot'),('S_isotonic','hybrid_S_isotonic_pending_slot')]:
            order=g.sort_values([score,'original_H1_rank','sid'],ascending=[False,True,True]).index
            assert np.array_equal(g.loc[order,dest],np.sort(g.original_PVR_slot))
        rounded_order=g.assign(roundS=g.S.round(12)).sort_values(['roundS','original_H1_rank','sid'],ascending=[False,True,True]).sid.tolist()
        raw_order=g.sort_values(['S','original_H1_rank','sid'],ascending=[False,True,True]).sid.tolist()
        if rounded_order!=raw_order:round_sensitive.append(dict(group=list(k),raw_order=raw_order,round12_order=rounded_order))
        groups+=1;rows+=n;sampled.append(dict(group=list(k),n=n,OLS_beta=float(b),independent_minmax_isotonic_checked=True))
    # Clock and min ratios only on the fixed fifteen displayed rows, not all source histories.
    target=x.merge(early[KEY],on=KEY,validate='one_to_one')
    for r in target.itertuples():
        if r.L_status=='KNOWN':
            recent=list(r.recent5_close_days);prior=list(r.prior5_close_days)
            assert len(recent)==len(prior)==5
            assert prior==sorted(prior)and recent==sorted(recent)and prior[-1]<recent[0]and recent[-1]==r.day
            assert all(d<=r.day for d in prior+recent)
            assert math.isclose(min(r.recent5_close_values)/min(r.prior5_close_values)-1,r.low_improvement,rel_tol=1e-12,abs_tol=1e-12)
    coverage=json.loads((RUN/'COVERAGE_AND_FORM_RISK.json').read_text())
    for window,g in x.groupby('window'):
        c=coverage[window];assert c['legal_rows']==len(g)and c['rank_status_counts']==g.rank_status.value_counts().to_dict()
        kg=g[g.rank_status=='KNOWN'];assert c['known_rows']==len(kg)and c['known_groups']==kg.groupby(GROUP).ngroups
        assert c['S_vs_isotonic_changed_rows']==int((kg.S_common_rank!=kg.S_isotonic_common_rank).sum())
        assert c['S_vs_PVR_changed_rows']==int((kg.hybrid_S_pending_slot!=kg.original_PVR_slot).sum())
    assert sum(c['S_vs_isotonic_changed_rows']for k,c in coverage.items()if k!='fixed_target_dates')==22105
    bound=[BASE/'FREEZE.json',BASE/'rank_saved_candidates.py',RUN/'COMPLETION.json',RUN/'ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet',RUN/'COVERAGE_AND_FORM_RISK.json',RUN/'EARLY_FIXED_CASE_TABLE.csv',BASE/'structure_feature/L_FEATURES.parquet',Path(__file__)]
    result=dict(status='INPUTS_AND_FIXED_CASE_FORMULAS_VERIFIED_V1_FINAL_SCORE_TIE_FIX_PENDING',original_rows=133713,known_rows=49612,known_sector_day_groups=3083,changed_rows_vs_isotonic=22105,
        full_saved_original_keys_roles_scores_and_slots_verified=True,all_sector_slot_sets_and_unknown_slots_fixed=True,fixed_early_cases=15,manual_group_count=groups,manual_group_rows=rows,manual_group_checks=sampled,
        manual_OLS='Exact rational rank/OLS arithmetic, not importing producer',manual_isotonic='Independent weighted interval max-min characterization, not producer PAVA',
        sampled_final_S_round12_order_sensitivity=round_sensitive,
        limits=['No full3083group fit/PAVA recomputation','Prior high/RS20 original price endpoints not independently reconstructed here','Low ratios/dates checked from saved ten-close evidence for15target rows only','Slot values are pending ordinals; no claim of native financial numeric key wiring','Current raw-float S sorting reviewed as frozen; round12-sensitivity listed separately, not silently changed','No causal alpha, actual funding, profit counterfactual or account execution'],
        remaining_blocks_for_reviewed_static_observation_scope=['V1 raw-float S ordering can break mathematical ties; exact integer numerator sidecar pending audit'],new_accounts=0,new_indicator_or_strategy_runs=0,source_sha256={str(p.resolve()):sha(p)for p in bound})
    out=HERE/'SAVED_RANK_AUDIT.json';out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:result[k]for k in ['status','original_rows','known_rows','known_sector_day_groups','manual_group_count','manual_group_rows']},ensure_ascii=False));print('round_sensitive_groups',len(round_sensitive));print('AUDIT_SHA256',sha(out))

if __name__=='__main__':main()
