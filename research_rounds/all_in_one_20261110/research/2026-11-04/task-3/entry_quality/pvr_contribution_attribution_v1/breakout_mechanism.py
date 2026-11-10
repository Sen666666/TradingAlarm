"""Exploratory high-amount double-tail diagnosis. All features known at signal close."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,time,hashlib
import numpy as np,pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
B=Path(__file__).resolve().parent;C=B.parent/'daily_signal_cache_pilot20_v1/full_universe_v1'
def dump(n,x):(B/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def feat(file):
 a=pd.read_parquet(C/file,columns=['sid','day','source_row_present','price__close','price__high','price__low','price__amount','pvr__scale']);a=a.loc[a.source_row_present].reset_index(drop=True)
 c=a.price__close;hi=a.price__high;lo=a.price__low;s=a.pvr__scale
 h20=c.shift(1).rolling(20,min_periods=20).max();fixedh=c.shift(5).rolling(20,min_periods=20).max()
 hold=np.full(len(a),np.nan)
 if len(a)>=5:hold[4:]=(sliding_window_view(c.to_numpy(float),5)>fixedh.to_numpy(float)[4:,None]).mean(axis=1);hold[~np.isfinite(fixedh)]=np.nan
 tr=pd.concat([hi-lo,(hi-c.shift()).abs(),(lo-c.shift()).abs()],axis=1).max(axis=1);atr=tr.shift().rolling(20,min_periods=20).mean()
 out=pd.DataFrame({'sid':a.sid,'day':a.day,'break_distance':np.log(c/h20)/s,'stretch5':np.log(c/c.shift(5))/(s*np.sqrt(5)),'stretch5_ATR':(c-c.shift(5))/atr,'hold5':hold,'close_location':(2*c-hi-lo)/(hi-lo).replace(0,np.nan),'drawdown20':c/h20-1,'raw_h20':h20,'fixed_resistance':fixedh,'prior_ATR20':atr})
 return out

def main():
 tick=time.time();y=pd.read_parquet(B/'EVENT_COHORTS_SUPPLEMENT.parquet');manifest=json.loads((C/'CACHE_DATASET.json').read_text());keys={sid:set(g.day)for sid,g in y.groupby('sid')}
 dump('BREAKOUT_FREEZE.json',dict(status='EXPLORATORY_ALL_PERIODS_ALREADY_SEEN_NOT_NEW_HOLDOUT',code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),features={'break_distance':'ln(Ct/max(C[t-20:t-1])) / original_scale_t','stretch5':'ln(Ct/C[t-5])/(original_scale_t*sqrt5)','stretch5_ATR':'(Ct-C[t-5])/mean(TR[t-20:t-1]); TR=max(H-L,abs(H-Cprev),abs(L-Cprev))','hold5':'mean over j=t-4..t of 1[Cj>max(C[t-24:t-5])]; fixed resistance known before this 5-day window','close_location':'(2Ct-Ht-Lt)/(Ht-Lt); zero range unknown'},high_delta_selection='Within same date, original PVR 2-point bin, exact I age, choose top half delta_amt by value then sid; require parent group>=8. Outcome independent.',pair='Extreme inward pair by feature within selected high-delta pool; exclude exact feature ties, report ties; no replacement for censoring.',candidates={'E_support':'E - amt_up_high*(1-hold5); only amount amplification on up-days is gated by prior-resistance acceptance','E_breakout':'E - amt_up_high*1[break_distance<0]; sharp single-condition comparison, no weighted multi-feature sum'},candidate_origin='Designed after original contribution outcomes and four-quadrant diagnosis. No claim of untouched time-out sample.',no_signal_or_account_calls=True))
 frames=[]
 with ThreadPoolExecutor(max_workers=8)as pool:
  for f in pool.map(feat,list(manifest['files'])):
   if len(f)and f.sid.iloc[0]in keys:frames.append(f.loc[f.day.isin(keys[f.sid.iloc[0]])])
 y=y.merge(pd.concat(frames,ignore_index=True),on=['sid','day'],validate='one_to_one');y['E_support']=y.E-y.amt_up_high*(1-y.hold5);y['E_breakout']=y.E-y.amt_up_high*(y.break_distance<0);y.loc[y.break_distance.isna(),'E_breakout']=np.nan
 y.to_parquet(B/'EVENT_COHORTS_MECHANISM.parquet',index=False,compression='zstd')
 ff=['break_distance','stretch5','stretch5_ATR','hold5','close_location'];pairs=[];ties={}
 for (cohort,day,scorebin,age),g in y.groupby(['cohort','day','pvrbin','age'],sort=False):
  if len(g)<8:continue
  hh=g.sort_values(['delta_amt','sid'],ascending=[False,True]).head(int(np.ceil(len(g)/2)))
  for key in ff:
   gg=hh.loc[hh[key].notna()].sort_values([key,'sid']);m=len(gg)//2
   if len(gg)<4:continue
   low=gg.iloc[:m];high=gg.iloc[-m:].iloc[::-1]
   for(_,a),(_,b)in zip(low.iterrows(),high.iterrows()):
    if a[key]==b[key]:ties[(cohort,key)]=ties.get((cohort,key),0)+1;continue
    z=dict(cohort=cohort,day=day,year=int(b.year),period=b.period,feature=key,high_sid=b.sid,low_sid=a.sid,high_ep=b.episode_id,low_ep=a.episode_id,high_value=b[key],low_value=a[key],high_delta=b.delta_amt,low_delta=a.delta_amt,scoregap=b.score-a.score)
    for col in ['ret20','ret60','big60','fail_rebound20','nextopen_ret20','nextopen_ret60']:
     z[col+'_high']=b[col];z[col+'_low']=a[col];z[col+'_diff']=b[col]-a[col]
    pairs.append(z)
 p=pd.DataFrame(pairs);p.to_parquet(B/'HIGH_AMOUNT_MECHANISM_PAIRS.parquet',index=False,compression='zstd');rng=np.random.default_rng(1901);out=[];annual=[]
 for groupcols,label,store in [(['cohort','period','feature'],'period',out),(['cohort','year','feature'],'year',annual)]:
  for k,g in p.groupby(groupcols):
   d=dict(zip(groupcols,k));d.update(pairs=len(g),unique_episodes=len(set(g.high_ep)|set(g.low_ep)),dates=g.day.nunique(),scoregap=g.scoregap.mean(),high_delta=g.high_delta.mean(),low_delta=g.low_delta.mean())
   for col in ['ret20','ret60','big60','fail_rebound20','nextopen_ret20','nextopen_ret60']:
    q=g.loc[g[col+'_diff'].notna()].copy();d[col+'_n']=len(q);d[col+'_high']=q[col+'_high'].mean();d[col+'_low']=q[col+'_low'].mean();d[col+'_diff']=q[col+'_diff'].mean()
    if label=='period'and len(q):
     q['month']=q.day.dt.to_period('M').astype(str);m=q.groupby('month')[col+'_diff'].agg(['sum','count']);ix=rng.integers(0,len(m),size=(1000,len(m)));boot=m['sum'].to_numpy()[ix].sum(1)/m['count'].to_numpy()[ix].sum(1);d[col+'_boot_lo']=np.quantile(boot,.025);d[col+'_boot_hi']=np.quantile(boot,.975)
   store.append(d)
 pd.DataFrame(out).to_csv(B/'HIGH_AMOUNT_MECHANISM_SUMMARY.csv',index=False);pd.DataFrame(annual).to_csv(B/'HIGH_AMOUNT_MECHANISM_BY_YEAR.csv',index=False)
 dump('MECHANISM_TIED_PAIRS_EXCLUDED.json',{str(k):v for k,v in ties.items()})
 # Ranking retained full I-entry cohort, no high-delta label or new eligibility gate.
 rows=[]
 for day,g in y.loc[y.cohort.eq('entry0')].groupby('day'):
  if len(g)<20 or g[['E_support','E_breakout']].isna().any().any():continue
  for cap in ['top20','top20pct']:
   n=20 if cap=='top20'else int(np.ceil(.2*len(g)));base=g.sort_values(['E','sid'],ascending=[False,True]).head(n)
   for key in ['E_support','E_breakout']:
    alt=g.sort_values([key,'sid'],ascending=[False,True]).head(n)
    for h in [20,60]:
     if base['ret'+str(h)].notna().sum()!=n or alt['ret'+str(h)].notna().sum()!=n:continue
     rows.append(dict(day=day,period=base.period.iloc[0],year=int(base.year.iloc[0]),cap=cap,ranker=key,h=h,n=n,turnover=1-len(set(base.episode_id)&set(alt.episode_id))/n,base=base['ret'+str(h)].mean(),alternative=alt['ret'+str(h)].mean(),diff=alt['ret'+str(h)].mean()-base['ret'+str(h)].mean(),big60_diff=alt.big60.mean()-base.big60.mean(),fail20_diff=alt.fail_rebound20.mean()-base.fail_rebound20.mean(),open_diff=alt['nextopen_ret'+str(h)].mean()-base['nextopen_ret'+str(h)].mean()))
 r=pd.DataFrame(rows);r.to_csv(B/'BREAKOUT_COMMON_DATE_RANKING.csv',index=False);rr=[]
 for(period,cap,key,h),g in r.groupby(['period','cap','ranker','h']):
  g=g.copy();g['month']=g.day.dt.to_period('M').astype(str);m=g.groupby('month')['diff'].agg(['sum','count']);ix=rng.integers(0,len(m),size=(1000,len(m)));boot=m['sum'].to_numpy()[ix].sum(1)/m['count'].to_numpy()[ix].sum(1)
  rr.append(dict(period=period,cap=cap,ranker=key,h=h,dates=len(g),selected_events=int(g.n.sum()),turnover=g.turnover.mean(),base=g.base.mean(),alternative=g.alternative.mean(),diff=g['diff'].mean(),eventweighted_diff=np.average(g['diff'],weights=g.n),boot_lo=np.quantile(boot,.025),boot_hi=np.quantile(boot,.975),open_diff=g.open_diff.mean(),big60_diff=g.big60_diff.mean(),fail20_diff=g.fail20_diff.mean()))
 pd.DataFrame(rr).to_csv(B/'BREAKOUT_RANKING_SUMMARY.csv',index=False);r.groupby(['year','cap','ranker','h']).agg(dates=('day','size'),diff=('diff','mean'),open_diff=('open_diff','mean'),big60_diff=('big60_diff','mean'),fail20_diff=('fail20_diff','mean'),turnover=('turnover','mean')).reset_index().to_csv(B/'BREAKOUT_RANKING_BY_YEAR.csv',index=False)
 # Execution observations: no inference that range>0 equals tradability.
 exe=[]
 for year,g in y.loc[y.cohort.eq('entry0')].groupby('year'):exe.append(dict(year=int(year),entry_events=len(g),next_open_known=int(g.next_open_gap.notna().sum()),next_observed_oneprice=int(g.next_open_range_zero.sum()),next_open_gap_gt3pct=int(g.next_open_gap.gt(.03).sum()),next_open_gap_gt5pct=int(g.next_open_gap.gt(.05).sum()),ret20_complete=int(g.ret20.notna().sum()),ret60_complete=int(g.ret60.notna().sum())))
 dump('EXECUTION_OBSERVATION_LIMITS.json',exe);dump('BREAKOUT_COMPLETION.json',dict(status='COMPLETE_EXPLORATORY_PENDING_INDEPENDENT_REVIEW',seconds=time.time()-tick,feature_event_rows=len(y),pairs=len(p),note='Signal known after close; next actual observed open is unexecuted benchmark. No PIT ST/halt/limits/exchange calendar/order queue, gap dates are not proved fillable.'))
 print(pd.DataFrame(out).loc[lambda g:g.cohort.eq('entry0'),['period','feature','pairs','ret20_diff','ret60_diff','big60_diff','fail_rebound20_diff']].to_string(index=False));print(pd.DataFrame(rr).to_string(index=False));print('COMPLETE',time.time()-tick)
if __name__=='__main__':main()
