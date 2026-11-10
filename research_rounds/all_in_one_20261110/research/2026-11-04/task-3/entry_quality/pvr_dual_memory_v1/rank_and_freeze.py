"""Original-e dual memory frozen ranking only; no forward labels/account."""
from pathlib import Path
import hashlib,json,time
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parent
OLD=ROOT.parent/'pvr_residual_ranking_v1/run_v1_exact_ties/ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet'
FEATURE=ROOT/'features/DUAL_MEMORY_FEATURES.parquet'
KEY=['window','day','sid'];DAY=['window','day']

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):
    with p.open('x')as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def pct(s):return (s.rank(method='average')-1)/(len(s)-1)
def period(day):return np.select([day.lt('2024-01-01'),day.lt('2025-01-01')],['DEV_2022_23','DIAG_2024'],default='DIAG_2025H2_2026H1')

def main():
    out=ROOT/'ranks';out.mkdir(exist_ok=False);start=time.monotonic()
    src={str(p.resolve()):sha(p)for p in[Path(__file__),ROOT/'FREEZE.json',OLD,FEATURE]}
    base=pd.read_parquet(OLD,columns=KEY+['roles','sector','score','original_H1_rank','original_H1_slot','original_PVR_slot'])
    f=pd.read_parquet(FEATURE);cols=KEY+['e','E_fast','E_slow','fast_status','slow_status','fast_start_day','fast_end_day','slow_start_day','slow_end_day']
    x=base.merge(f[cols],on=KEY,how='left',validate='one_to_one');assert len(x)==133713
    x['period']=period(x.day);x['N_original']=x.groupby(DAY).sid.transform('size')
    assert np.isfinite(x.loc[np.isfinite(x.E_slow),'score']).all()
    sources=[];daystats=[]
    for family in ['COMMON','FAST_ONLY']:
        known=np.isfinite(x.E_fast)
        if family=='COMMON':known&=np.isfinite(x.E_slow)&np.isfinite(x.score)
        a=x.loc[known].copy();a['N']=a.groupby(DAY).sid.transform('size');a=a[a.N.ge(10)].copy()
        a['K']=np.ceil(a.N/10).astype(int);a['family']=family
        a['p_fast']=a.groupby(DAY).E_fast.transform(pct)
        if family=='COMMON':a['p_slow']=a.groupby(DAY).E_slow.transform(pct)
        a['rank_PVR']=a.groupby(DAY).original_PVR_slot.rank(method='first').astype(int)
        a['rank_FAST']=0
        if family=='COMMON':
            u=2*(a.N-1)
            fa=np.rint(a.p_fast*u);sl=np.rint(a.p_slow*u)
            assert np.allclose(fa,a.p_fast*u,rtol=0,atol=1e-10)and np.allclose(sl,a.p_slow*u,rtol=0,atol=1e-10)
            a['CONT_numerator']=(3*fa+7*sl).astype(int);a['S_cont']=a.CONT_numerator/(20*(a.N-1))
            a['rank_SLOW']=0;a['rank_CONT']=0
        for keys,g in a.groupby(DAY,sort=False):
            for name,col in [('FAST','E_fast')]+([('SLOW','E_slow'),('CONT','CONT_numerator')]if family=='COMMON'else[]):
                order=g.sort_values([col,'original_H1_rank','sid'],ascending=[False,True,True]).index
                a.loc[order,'rank_'+name]=np.arange(1,len(g)+1)
        arms=['PVR','FAST']+(['SLOW','CONT']if family=='COMMON'else[])
        for arm in arms:a['pick_'+arm]=a['rank_'+arm].le(a.K)
        for keys,g in a.groupby(DAY,sort=False):
            K=int(g.K.iloc[0]);assert all(int(g['pick_'+z].sum())==K for z in arms)
            z=dict(window=keys[0],day=keys[1],period=g.period.iloc[0],family=family,N=len(g),K=K,
              original_N=int(g.N_original.iloc[0]),fast_slow_spearman=float(g.E_fast.rank().corr(g.E_slow.rank()))if family=='COMMON'else None,
              fast_originalPVR_unknown=int(g.score.isna().sum()),slow_unknown=int(g.E_slow.isna().sum()))
            if family=='COMMON':z.update(FAST_CONT_overlap=int((g.pick_FAST&g.pick_CONT).sum()),FAST_CONT_union=int((g.pick_FAST|g.pick_CONT).sum()),PVR_CONT_overlap=int((g.pick_PVR&g.pick_CONT).sum()))
            daystats.append(z)
        sources.append(a)
    ranked=pd.concat(sources,ignore_index=True);ranked.to_parquet(out/'ALL_FAMILY_RANKS_PRE_LABEL.parquet',index=False)
    ds=pd.DataFrame(daystats);ds.to_csv(out/'DAY_POOL_AND_CORRELATION_PRE_LABEL.csv',index=False)
    coverage=[]
    for p,g in x.groupby('period'):
        c=dict(period=p,original_rows=len(g),original_dates=g.day.nunique(),fast_ready=int(np.isfinite(g.E_fast).sum()),slow_ready=int(np.isfinite(g.E_slow).sum()),fast_only=int((np.isfinite(g.E_fast)&~np.isfinite(g.E_slow)).sum()),fast_ready_PVR_unknown=int((np.isfinite(g.E_fast)&~np.isfinite(g.score)).sum()))
        for family in ['COMMON','FAST_ONLY']:
            q=ranked[(ranked.period==p)&(ranked.family==family)];c[family+'_rows']=len(q);c[family+'_dates']=q.day.nunique();c[family+'_source_picks_per_arm']=int(q.pick_PVR.sum())
        coverage.append(c)
    pd.DataFrame(coverage).to_csv(out/'SOURCE_COVERAGE.csv',index=False)
    case=((ranked.sid.eq('000620.SZ')&ranked.day.between('2022-01-01','2022-01-31'))
      |(ranked.sid.eq('300666.SZ')&ranked.window.eq('strong'))
      |(ranked.sid.eq('300085.SZ')&ranked.day.between('2024-09-12','2024-10-31'))
      |(ranked.sid.eq('002583.SZ')&(ranked.day.between('2024-01-01','2024-01-31')|ranked.day.between('2024-09-01','2024-11-30'))))
    cols=['family','day','sid','N_original','N','K','score','e','E_fast','E_slow','p_fast','p_slow','S_cont','original_PVR_slot','rank_PVR','rank_FAST','rank_SLOW','rank_CONT','pick_PVR','pick_FAST','pick_SLOW','pick_CONT']
    ranked.loc[case,cols].sort_values(['sid','day','family']).to_csv(out/'ALL_FIXED_CASE_RANKS.csv',index=False)
    # Full raw source values for cases outside an eligible family remain available.
    x[x.sid.isin(['000620.SZ','300666.SZ','300085.SZ','002583.SZ'])].to_parquet(out/'FOUR_STOCK_ALL_ORIGINAL_RAW_CASES.parquet',index=False)
    save(out/'COMPLETION_PRE_FUTURE_LABELS.json',dict(status='RANKS_POOLS_TOPK_FROZEN_BEFORE_LOADING_LABELS',source_sha256=src,
      outputs={p.name:sha(p)for p in out.iterdir()if p.is_file()},new_scores=2,new_residual_models=0,new_accounts=0,elapsed_seconds=time.monotonic()-start))
    print(pd.DataFrame(coverage).to_string(index=False))
    early=ranked[(ranked.family=='COMMON')&((ranked.sid.eq('000620.SZ')&ranked.day.between('2022-01-01','2022-01-31'))|(ranked.sid.eq('002583.SZ')&ranked.day.isin(['2024-10-14','2024-10-18','2024-10-21']))|(ranked.sid.eq('300666.SZ')&ranked.day.isin(['2025-09-26','2026-01-15']))|(ranked.sid.eq('300085.SZ')&ranked.day.isin(['2024-09-24','2024-10-08','2024-10-09'])))]
    print(early[cols].to_string(index=False))

if __name__=='__main__':main()
