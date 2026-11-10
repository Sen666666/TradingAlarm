"""Original PVR attribution from committed cache only. No signal/account calls."""
from pathlib import Path
import json,time,hashlib,os
from concurrent.futures import ThreadPoolExecutor
import numpy as np
import pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
B=Path(__file__).resolve().parent
C=B.parent/'daily_signal_cache_pilot20_v1/full_universe_v1'
W=.9**np.arange(20,-1,-1);W=W/W.sum()
COLS=['sid','day','source_row_present','native__e0_ready','native__g_ready','native__i_target','native__i_buy','native__i_entered','native__i_exited','native__i_floor','native__g_grade','pvr__u','pvr__b','pvr__e','pvr__E','pvr__score','pvr__r','pvr__scale','pvr__amount_ref','pvr__valid_observation','pvr__clock_block','price__open','price__high','price__low','price__close','price__amount']
def dump(name,x):
    (B/name).write_text(json.dumps(x,ensure_ascii=False,indent=2,allow_nan=False,default=str)+'\n')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def stock(file):
    a=pd.read_parquet(C/file,columns=COLS)
    sid=a.sid.iloc[0];a=a.loc[a.source_row_present].reset_index(drop=True)
    n=len(a); close=a.price__close.to_numpy(float); logc=np.log(close)
    ix=np.arange(n); entered=a.native__i_entered.eq(1).to_numpy(); active=a.native__i_target.eq(1).to_numpy()
    start=np.maximum.accumulate(np.where(entered,ix,-1));age=ix-start;age[start<0]=-1
    ep=np.cumsum(entered);eligible=(a.native__e0_ready.eq(1)&a.native__g_ready.eq(True)&a.native__i_target.eq(1)&a.native__i_buy.eq(True)).to_numpy()
    stats=dict(sid=sid,observed=n,buy_days=int(eligible.sum()),left_censored_buy_days=int((eligible&(start<0)).sum()),episodes=int(entered.sum()),boundary_attribution_excluded=int((eligible&(ix<21)).sum()))
    if n<22:return pd.DataFrame(),stats
    # Drop first 21 cached observations because their complete 21-day attribution and prior anchor are not cached.
    # Never fill unknown pre-2022 d_j or left-censored I age.
    e=sliding_window_view(a.pvr__e.to_numpy(float),21)[1:];u=sliding_window_view(a.pvr__u.to_numpy(float),21)[1:]
    b=sliding_window_view(a.pvr__b.to_numpy(float),21)[1:];r=sliding_window_view(a.pvr__r.to_numpy(float),21)[1:]
    d=e*W;price=u*W;am=d-price;E=d.sum(axis=1);Ep=price.sum(axis=1);de=am.sum(axis=1)
    mass=np.abs(d).sum(axis=1);sq=(d*d).sum(axis=1)
    valid=np.isfinite(d).all(axis=1)&(sliding_window_view(a.pvr__clock_block.to_numpy(float),21)[1:].ptp(axis=1)==0) if False else np.isfinite(d).all(axis=1)&(np.ptp(sliding_window_view(a.pvr__clock_block.to_numpy(float),21)[1:],axis=1)==0)
    oldE=a.pvr__E.to_numpy(float)[21:]; known=valid&np.isfinite(oldE)
    stats['reconstructed_rows']=int(known.sum());stats['max_E_error']=float(np.max(np.abs(E[known]-oldE[known]))) if known.any() else 0.
    stats['max_e_formula_error']=float(np.nanmax(np.abs(e-u*(1+.5*np.abs(u)*b)))) if np.isfinite(e).any() else 0.
    assert stats['max_E_error']<1e-12 and stats['max_e_formula_error']<1e-12
    prev=sliding_window_view(logc[:-1],21);end=logc[21:,None]
    denom=np.abs(r);kappa=np.divide(np.sign(r)*(end-prev),denom,out=np.ones_like(r),where=denom>0)
    kappa=np.clip(kappa,0,1)
    Epath=(d*kappa).sum(axis=1)
    # Retain original amount evidence except positive amount amplification of an up-day whose gain was surrendered.
    withdrawn=(np.maximum(am,0)*(u>0)*(b>0)*(1-kappa)).sum(axis=1)
    Eamt=E-withdrawn
    f=pd.DataFrame({'sid':sid,'day':a.day.iloc[21:].to_numpy(),'obs':ix[21:],'episode':ep[21:],'age':age[21:],'entry_day':pd.NaT,'score':a.pvr__score.iloc[21:].to_numpy(),'E':E,'E_price':Ep,'delta_amt':de,'Cmax':np.divide(np.abs(d).max(axis=1),mass,out=np.full(len(mass),np.nan),where=mass>0),'Neff':np.divide(mass*mass,sq,out=np.full(len(mass),np.nan),where=sq>0),'signed_coherence':np.divide(E,mass,out=np.full(len(mass),np.nan),where=mass>0),'max_abs_contribution_age':20-np.abs(d).argmax(axis=1),'positive_days':(e>0).sum(axis=1),'E_amt_retained':Eamt,'E_path_retained':Epath,'withdrawn_amt':withdrawn,'pvr_mass':mass,'close':close[21:],'I_floor':a.native__i_floor.iloc[21:].to_numpy(),'g_grade':a.native__g_grade.iloc[21:].to_numpy(),'buy':eligible[21:],'valid':valid,'i_active':active[21:]})
    f.loc[start[21:]>=0,'entry_day']=a.day.to_numpy()[start[21:][start[21:]>=0]]
    f=f.loc[f.buy&f.valid&f.age.ge(0)&np.isfinite(f.score)].copy()
    if f.empty:return f,stats
    pos=f.obs.to_numpy(int)
    f['episode_id']=sid+':'+f.episode.astype(str);f['year']=f.day.dt.year
    f['next_open_range_zero']=False;f['next_open_gap']=np.nan
    q=pos+1<n;nextp=pos[q]+1
    f.loc[q,'next_open_range_zero']=(a.price__high.to_numpy()[nextp]==a.price__low.to_numpy()[nextp])
    f.loc[q,'next_open_gap']=a.price__open.to_numpy()[nextp]/close[pos[q]]-1
    for h in [5,20,60]:
        for key in ['ret','mfe','mae','nextopen_ret','elapsed_days']:f[f'{key}{h}']=np.nan
        ok=pos+h<n;pp=pos[ok]
        if not len(pp):continue
        fut=sliding_window_view(close[1:],h)[pp];rel=fut/close[pp,None]-1
        f.loc[ok,f'ret{h}']=rel[:,-1];f.loc[ok,f'mfe{h}']=np.maximum(0,rel.max(axis=1));f.loc[ok,f'mae{h}']=np.minimum(0,rel.min(axis=1))
        f.loc[ok,f'nextopen_ret{h}']=close[pp+h]/a.price__open.to_numpy(float)[pp+1]-1
        f.loc[ok,f'elapsed_days{h}']=(a.day.iloc[pp+h].to_numpy()-a.day.iloc[pp].to_numpy())/np.timedelta64(1,'D')
    f['big60']=np.where(f.ret60.notna(),((f.mfe60>=.30)&(f.ret60>=.20)).astype(float),np.nan)
    f['fail_rebound20']=np.where(f.ret20.notna(),((f.mfe20>=.05)&(f.ret20<=-.05)).astype(float),np.nan)
    return f,stats

def summarize(g):
    d=dict(N=len(g),episodes=g.episode_id.nunique(),stocks=g.sid.nunique(),dates=g.day.nunique())
    for c in ['score','E','E_price','delta_amt','Cmax','Neff','ret5','ret20','ret60','mfe60','mae20','mae60','big60','fail_rebound20','nextopen_ret20','nextopen_ret60']:
        v=g[c].dropna();d[c+'_n']=len(v);d[c+'_mean']=float(v.mean()) if len(v) else None;d[c+'_median']=float(v.median()) if len(v) else None
    return d

def run():
    start=time.time();manifest=json.loads((C/'CACHE_DATASET.json').read_text())
    assert manifest['file_count']==5517
    freeze=dict(status='FROZEN_BEFORE_PATH_LABEL_READ',cache_identity=manifest['cache_identity'],source_sha256=manifest['source_sha256'],cache_manifest_sha256=sha(C/'CACHE_DATASET.json'),code_sha256=sha(__file__),weights=W.tolist(),no_signal_or_account_execution=True,attribution_boundary='Exclude first21 actual cached observations; never synthesize pre2022 d_j. Invalid full21/block unknown. Unknown I start excluded until recorded i_entered.',event='sid + cumulative original i_entered; age0 is original entered observation. i_buy never starts/restarts episode.',primary='One original I entry age0 per episode; secondary first repeated original i_buy at exact age1..5,6..20,21+ reported separately, never pooled.',match='Same signal date, floor(original PVR score/2), exact I observation age; at least4 in feature-formed stratum. Pair high/low extreme inward, omit median. Membership frozen before checking horizon completeness; never replace censored pairs.',periods={'development_diagnostic':'2022-2023','already_seen_time_external_diagnostic':'2024-2026-05-15'},candidates={'E_price':'sum w*u, amount ablation','E_amt_retained':'E - sum w * max(e-u,0) * 1[u>0 and b>0] * (1-kappa)','E_path_retained':'sum w*e*kappa','kappa':'clip(sign(r_j)*(log C_t-log C_(j-1))/abs(r_j),0,1); r=0 ->1; only through t'},labels={'ret_h':'C_(t+h)/C_t-1, h actual observed bars, fullh only','mfe_mae':'max/min of future close/anchor-1 including 0','big60':'mfe60>=30% AND terminal60>=20%','fail_rebound20':'mfe20>=5% AND terminal20<=-5%','nextopen':'unexecuted next open benchmark, not fill simulation'},no_hyperparameter_search=True)
    if (B/'FREEZE.json').exists():raise RuntimeError('Existing freeze; do not silently overwrite')
    dump('FREEZE.json',freeze)
    frames=[];stats=[]
    with ThreadPoolExecutor(max_workers=8) as pool:
        for k,(f,s) in enumerate(pool.map(stock,list(manifest['files']))):
            frames.append(f);stats.append(s)
            if (k+1)%500==0:print('READ',k+1,round(time.time()-start,1),flush=True)
    x=pd.concat(frames,ignore_index=True);ss=pd.DataFrame(stats);ss.to_csv(B/'SOURCE_RECONSTRUCTION_CHECKS.csv',index=False)
    x['cohort']=np.select([x.age.eq(0),x.age.between(1,5),x.age.between(6,20)],['entry0','repeat1_5','repeat6_20'],default='repeat21plus')
    x['period']=np.where(x.year<=2023,'2022_2023','2024_2026_seen');x['pvrbin']=(x.score//2).astype(int)
    x=x.sort_values(['sid','episode','day']);x.to_parquet(B/'ALL_BUY_ATTRIBUTIONS.parquet',index=False,compression='zstd')
    y=x.drop_duplicates(['episode_id','cohort'],keep='first').copy();y.to_parquet(B/'EVENT_COHORTS.parquet',index=False,compression='zstd')
    cover=[]
    for (year,cohort),g in y.groupby(['year','cohort']):cover.append(dict(year=int(year),cohort=cohort,**summarize(g)))
    dump('EVENT_COVERAGE.json',cover)
    features=['delta_amt','Cmax','Neff','E_price','E_amt_retained','E_path_retained']
    pairs=[]
    # Pairing depends on feature values, date, original score band, exact age only. No price label selection.
    for (cohort,day,scorebin,age),g in y.groupby(['cohort','day','pvrbin','age'],sort=False):
        if len(g)<4:continue
        for feat in features:
            gg=g.loc[g[feat].notna()].sort_values([feat,'sid'])
            m=len(gg)//2
            if len(gg)<4:continue
            low=gg.iloc[:m];high=gg.iloc[-m:].iloc[::-1]
            for (_,lo),(_,hi) in zip(low.iterrows(),high.iterrows()):
                p=dict(cohort=cohort,day=day,year=int(hi.year),period=hi.period,pvrbin=int(scorebin),age=int(age),feature=feat,high_sid=hi.sid,low_sid=lo.sid,high_ep=hi.episode_id,low_ep=lo.episode_id,feature_high=float(hi[feat]),feature_low=float(lo[feat]),score_gap=float(hi.score-lo.score))
                for col in ['ret5','ret20','ret60','mfe60','mae20','mae60','big60','fail_rebound20','nextopen_ret20','nextopen_ret60']:
                    p[col+'_high']=hi[col];p[col+'_low']=lo[col];p[col+'_diff']=hi[col]-lo[col]
                pairs.append(p)
    z=pd.DataFrame(pairs);z.to_parquet(B/'MATCHED_PAIRS.parquet',index=False,compression='zstd')
    out=[];rng=np.random.default_rng(34219)
    for (cohort,period,feat),g in z.groupby(['cohort','period','feature']):
        rec=dict(cohort=cohort,period=period,feature=feat,pairs=len(g),episodes=len(set(g.high_ep)|set(g.low_ep)),stocks=len(set(g.high_sid)|set(g.low_sid)),dates=g.day.nunique(),score_gap_mean=float(g.score_gap.mean()))
        for col in ['ret5','ret20','ret60','mfe60','mae20','mae60','big60','fail_rebound20','nextopen_ret20','nextopen_ret60']:
            q=g.loc[g[col+'_diff'].notna()].copy();v=q[col+'_diff']
            rec[col+'_n']=len(q);rec[col+'_high']=float(q[col+'_high'].mean()) if len(q) else None;rec[col+'_low']=float(q[col+'_low'].mean()) if len(q) else None;rec[col+'_diff']=float(v.mean()) if len(q) else None
            if len(q):
                q['month']=q.day.dt.to_period('M').astype(str);a=q.groupby('month')[col+'_diff'].agg(['sum','count']);ns=len(a)
                draws=rng.integers(0,ns,size=(1000,ns));boot=a['sum'].to_numpy()[draws].sum(1)/a['count'].to_numpy()[draws].sum(1)
                rec[col+'_month_boot_lo']=float(np.quantile(boot,.025));rec[col+'_month_boot_hi']=float(np.quantile(boot,.975))
        out.append(rec)
    pd.DataFrame(out).to_csv(B/'MATCHED_SUMMARY.csv',index=False)
    # Same entry-day top20 and top20% reorder ablations. No capacity inference and no new eligibility filters.
    rank=[];entry=y.loc[y.cohort.eq('entry0')]
    for day,g in entry.groupby('day'):
        if len(g)<20:continue
        for cap in ['top20','top20pct']:
            n=min(20,len(g)) if cap=='top20' else max(1,int(np.ceil(.2*len(g))))
            for feat in ['E','E_price','E_amt_retained','E_path_retained']:
                s=g.sort_values([feat,'sid'],ascending=[False,True]).head(n)
                for _,r in s.iterrows():rank.append(dict(cap=cap,ranker=feat,**r.to_dict()))
    rank=pd.DataFrame(rank);rank.to_parquet(B/'ENTRY_RANKING_SELECTIONS.parquet',index=False,compression='zstd')
    rs=[]
    for (period,cap,ranker),g in rank.groupby(['period','cap','ranker']):rs.append(dict(period=period,cap=cap,ranker=ranker,**summarize(g)))
    dump('ENTRY_RANKING_SUMMARY.json',rs)
    dump('COMPLETION.json',dict(status='COMPLETE_DESCRIPTIVE_DIAGNOSTIC_NOT_ALPHA_OR_EXECUTION_VALIDATION',stocks=len(ss),cache_observed_rows=int(ss.observed.sum()),buy_days=int(ss.buy_days.sum()),episodes_started=int(ss.episodes.sum()),left_censored_buy_days=int(ss.left_censored_buy_days.sum()),boundary_attribution_excluded=int(ss.boundary_attribution_excluded.sum()),reconstructed_rows=int(ss.reconstructed_rows.sum()),max_E_error=float(ss.max_E_error.max()),max_e_formula_error=float(ss.max_e_formula_error.max()),attributed_buy_rows=len(x),event_cohort_rows=len(y),unique_episodes=y.episode_id.nunique(),matched_pairs=len(z),elapsed_seconds=time.time()-start))
    print((B/'COMPLETION.json').read_text(),flush=True)
if __name__=='__main__':run()
