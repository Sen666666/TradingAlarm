"""Post-primary explanatory decomposition and explicit exploratory asymmetric candidate."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,hashlib,time
import numpy as np,pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
B=Path(__file__).resolve().parent;C=B.parent/'daily_signal_cache_pilot20_v1/full_universe_v1'
W=.9**np.arange(20,-1,-1);W/=W.sum()
def dump(name,obj):(B/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2,default=str)+'\n')
def part(file):
 a=pd.read_parquet(C/file,columns=['sid','day','source_row_present','pvr__u','pvr__b','pvr__e','pvr__r','price__close']);a=a.loc[a.source_row_present].reset_index(drop=True)
 if len(a)<22:return pd.DataFrame()
 u=sliding_window_view(a.pvr__u.to_numpy(float),21)[1:];b=sliding_window_view(a.pvr__b.to_numpy(float),21)[1:];e=sliding_window_view(a.pvr__e.to_numpy(float),21)[1:];r=sliding_window_view(a.pvr__r.to_numpy(float),21)[1:]
 am=W*.5*u*np.abs(u)*b;logc=np.log(a.price__close.to_numpy(float));prev=sliding_window_view(logc[:-1],21)
 k=np.clip(np.divide(np.sign(r)*(logc[21:,None]-prev),np.abs(r),out=np.ones_like(r),where=np.abs(r)>0),0,1)
 d=e*W;ret={'sid':a.sid.iloc[0],'day':a.day.iloc[21:].to_numpy()}
 for name,mask in [('up_high',(u>0)&(b>0)),('up_low',(u>0)&(b<0)),('down_high',(u<0)&(b>0)),('down_low',(u<0)&(b<0))]:ret['amt_'+name]=(am*mask).sum(axis=1)
 ret['E_positive_retained']=(d-np.maximum(d,0)*(1-k)).sum(axis=1)
 return pd.DataFrame(ret)
def main():
 tick=time.time();y=pd.read_parquet(B/'EVENT_COHORTS.parquet');manifest=json.loads((C/'CACHE_DATASET.json').read_text())
 dump('SUPPLEMENT_FREEZE.json',dict(status='EXPLORATORY_AFTER_PRIMARY_OUTCOMES_ALREADY_OBSERVED',purpose='Separate four algebraic amount sources; diagnose symmetric kappa removal of recovered negative evidence; no new out-of-sample claim',candidate='E_positive_retained=E-sum(max(d_j,0)*(1-kappa_jt)); preserve all original negative evidence, remove only current-close surrendered positive evidence',four_quadrants='signed .5*w*u*abs(u)*b split by sign(u),sign(b); sum equals delta_amt',no_parameter_search=True,code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
 keys={sid:set(g.day)for sid,g in y.groupby('sid')}
 fs=[]
 with ThreadPoolExecutor(max_workers=8)as pool:
  for k,f in enumerate(pool.map(part,list(manifest['files']))):
   if len(f) and f.sid.iloc[0]in keys:fs.append(f.loc[f.day.isin(keys[f.sid.iloc[0]])])
 q=pd.concat(fs,ignore_index=True);y=y.merge(q,on=['sid','day'],validate='one_to_one');assert np.nanmax(np.abs(y[['amt_up_high','amt_up_low','amt_down_high','amt_down_low']].sum(axis=1)-y.delta_amt))<1e-12
 y.to_parquet(B/'EVENT_COHORTS_SUPPLEMENT.parquet',index=False,compression='zstd')
 # Primary first-entry matched explanatory effects, no claim of independent alpha.
 rows=[]
 for (day,scorebin,age),g in y.loc[y.cohort.eq('entry0')].groupby(['day','pvrbin','age'],sort=False):
  if len(g)<4:continue
  for feat in ['amt_up_high','amt_up_low','amt_down_high','amt_down_low','E_positive_retained']:
   gg=g.sort_values([feat,'sid']);m=len(gg)//2;lo=gg.iloc[:m];hi=gg.iloc[-m:].iloc[::-1]
   for(_,a),(_,b)in zip(lo.iterrows(),hi.iterrows()):
    z=dict(day=day,year=int(b.year),period=b.period,feature=feat,high=b.sid,low=a.sid,feature_diff=b[feat]-a[feat],score_gap=b.score-a.score)
    for col in ['ret20','ret60','big60','fail_rebound20']:z[col]=b[col]-a[col]
    rows.append(z)
 p=pd.DataFrame(rows);p.to_parquet(B/'SUPPLEMENT_PAIRS.parquet',index=False,compression='zstd')
 ss=[]
 for (period,feat),g in p.groupby(['period','feature']):
  z=dict(period=period,feature=feat,pairs=len(g),ties=int(g.feature_diff.eq(0).sum()))
  for col in ['ret20','ret60','big60','fail_rebound20']:z[col+'_n']=int(g[col].notna().sum());z[col+'_diff']=g[col].mean()
  ss.append(z)
 pd.DataFrame(ss).to_csv(B/'SUPPLEMENT_MATCHED_SUMMARY.csv',index=False)
 # Fair ranker comparison: same dates and full outcomes for BOTH frozen selections, no post-label stock replacement.
 entry=y.loc[y.cohort.eq('entry0')];rows=[];rng=np.random.default_rng(49243)
 for day,g in entry.groupby('day'):
  if len(g)<20:continue
  for cap in ['top20','top20pct']:
   n=20 if cap=='top20'else int(np.ceil(.2*len(g)));base=g.sort_values(['E','sid'],ascending=[False,True]).head(n)
   for feat in ['E_price','E_amt_retained','E_path_retained','E_positive_retained']:
    alt=g.sort_values([feat,'sid'],ascending=[False,True]).head(n)
    for h in [20,60]:
     if base['ret'+str(h)].notna().sum()!=n or alt['ret'+str(h)].notna().sum()!=n:continue
     rows.append(dict(day=day,period=base.period.iloc[0],year=int(base.year.iloc[0]),cap=cap,ranker=feat,h=h,n=n,turnover=1-len(set(base.episode_id)&set(alt.episode_id))/n,base=base['ret'+str(h)].mean(),alternative=alt['ret'+str(h)].mean(),diff=alt['ret'+str(h)].mean()-base['ret'+str(h)].mean(),base_median=base['ret'+str(h)].median(),alternative_median=alt['ret'+str(h)].median(),big60_diff=alt.big60.mean()-base.big60.mean(),fail20_diff=alt.fail_rebound20.mean()-base.fail_rebound20.mean(),open_diff=alt['nextopen_ret'+str(h)].mean()-base['nextopen_ret'+str(h)].mean()))
 r=pd.DataFrame(rows);r.to_csv(B/'COMMON_COMPLETE_DATE_RANKING.csv',index=False)
 rr=[]
 for (period,cap,feat,h),g in r.groupby(['period','cap','ranker','h']):
  g=g.copy();g['month']=g.day.dt.to_period('M').astype(str);a=g.groupby('month')['diff'].agg(['sum','count']);draw=rng.integers(0,len(a),size=(1000,len(a)));boot=a['sum'].to_numpy()[draw].sum(1)/a['count'].to_numpy()[draw].sum(1)
  rr.append(dict(period=period,cap=cap,ranker=feat,h=int(h),dates=len(g),selected_event_count=int(g.n.sum()),turnover=g.turnover.mean(),base=g.base.mean(),alternative=g.alternative.mean(),diff_equaldate=g['diff'].mean(),diff_eventweighted=np.average(g['diff'],weights=g.n),boot_lo=np.quantile(boot,.025),boot_hi=np.quantile(boot,.975),open_diff=g.open_diff.mean()))
 pd.DataFrame(rr).to_csv(B/'COMMON_COMPLETE_RANKING_SUMMARY.csv',index=False)
 year=r.groupby(['year','cap','ranker','h']).agg(dates=('day','size'),diff=('diff','mean'),turnover=('turnover','mean')).reset_index();year.to_csv(B/'YEAR_RANKING.csv',index=False)
 # Case pairs are explanatory and selected after observing outcomes, never used to set rankers.
 z=pd.read_parquet(B/'MATCHED_PAIRS.parquet');z=z.loc[z.cohort.eq('entry0')&z.feature.eq('delta_amt')].copy()
 case=[]
 for period in ['2022_2023','2024_2026_seen']:
  for kind,mask in [('amount_high_success_low_failure',z.big60_high.eq(1)&z.fail_rebound20_low.eq(1)),('amount_high_failure_low_success',z.fail_rebound20_high.eq(1)&z.big60_low.eq(1))]:
   v=z.loc[mask&z.period.eq(period)].assign(absgap=lambda g:abs(g.score_gap)).sort_values(['absgap','day']).head(2)
   for _,r0 in v.iterrows():
    for side in ['high','low']:
     ev=y.loc[y.episode_id.eq(r0[side+'_ep'])&y.cohort.eq('entry0')].iloc[0].to_dict();ev.update(kind=kind,side=side,matched_day=r0.day,paired_sid=r0[('low'if side=='high'else'high')+'_sid']);case.append(ev)
 pd.DataFrame(case).to_csv(B/'EXPLANATORY_CASES.csv',index=False)
 dump('SUPPLEMENT_COMPLETION.json',dict(status='COMPLETE_EXPLORATORY_NOT_VALIDATED_ALPHA',event_cohort_rows=len(y),seconds=time.time()-tick))
 print(pd.DataFrame(ss).to_string(index=False));print(pd.DataFrame(rr).to_string(index=False));print('COMPLETE',time.time()-tick)
if __name__=='__main__':main()
