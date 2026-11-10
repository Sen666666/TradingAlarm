"""Exploratory original all-i_buy queue, cluster repeated stock-days by original I episode."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import json,time,hashlib
import numpy as np,pandas as pd
from numpy.lib.stride_tricks import sliding_window_view
B=Path(__file__).resolve().parent;C=B.parent/'daily_signal_cache_pilot20_v1/full_universe_v1';w=.9**np.arange(20,-1,-1);w/=w.sum()
def dump(n,x):(B/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def extra(file):
 a=pd.read_parquet(C/file,columns=['sid','day','source_row_present','price__close','pvr__u','pvr__b']);a=a.loc[a.source_row_present].reset_index(drop=True)
 if len(a)<25:return pd.DataFrame()
 c=a.price__close;h=c.shift(5).rolling(20,min_periods=20).max();hold=np.full(len(a),np.nan);hold[4:]=(sliding_window_view(c.to_numpy(float),5)>h.to_numpy(float)[4:,None]).mean(axis=1);hold[~np.isfinite(h)]=np.nan
 u=sliding_window_view(a.pvr__u.to_numpy(float),21);b=sliding_window_view(a.pvr__b.to_numpy(float),21);amp=np.full(len(a),np.nan);amp[20:]=(w*.5*u*np.abs(u)*b*((u>0)&(b>0))).sum(axis=1)
 return pd.DataFrame({'sid':a.sid,'day':a.day,'hold5':hold,'amp_up':amp})
def main():
 tic=time.time();x=pd.read_parquet(B/'ALL_BUY_ATTRIBUTIONS.parquet');man=json.loads((C/'CACHE_DATASET.json').read_text());keys={sid:set(g.day)for sid,g in x.groupby('sid')}
 dump('FULLQUEUE_FREEZE.json',dict(status='EXPLORATORY_AFTER_ENTRY_ONLY_RESULT',formula='E_support=E-A_up*(1-P5), unchanged breakout candidate',universe='All original known i_buy with known recorded I episode and complete cache attribution; no first-I restriction. Missing pre2022 left-censored/feature rows excluded and reported.',selection='Original per-date E top20 or top20pct versus same candidates E_support selection. No accounts or new permissions.',evaluation='First require every candidate used by either selected set has full h outcomes on a given date. For each original I episode, average its selected signal-day label. Descriptive method mean is equal episode-weight, not independent stock-day count; episodic selection memberships differ. Daily paired mean difference separately reported. 2022/23 versus seen2024-26 and year.',causal='All feature <= signal close; next observed open benchmark is not verified execution',code_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
 fs=[]
 with ThreadPoolExecutor(max_workers=8)as pool:
  for f in pool.map(extra,list(man['files'])):
   if len(f)and f.sid.iloc[0]in keys:fs.append(f.loc[f.day.isin(keys[f.sid.iloc[0]])])
 x=x.merge(pd.concat(fs,ignore_index=True),on=['sid','day'],validate='one_to_one');x['E_support']=x.E-x.amp_up*(1-x.hold5);missing=int(x.E_support.isna().sum());x=x.loc[x.E_support.notna()];rows=[];daily=[]
 for day,g in x.groupby('day'):
  if len(g)<20:continue
  for cap in ['top20','top20pct']:
   n=20 if cap=='top20'else int(np.ceil(.2*len(g)));base=g.sort_values(['E','sid'],ascending=[False,True]).head(n);alt=g.sort_values(['E_support','sid'],ascending=[False,True]).head(n)
   for h in [20,60]:
    if base['ret'+str(h)].notna().sum()!=n or alt['ret'+str(h)].notna().sum()!=n:continue
    daily.append(dict(day=day,year=int(base.year.iloc[0]),period=base.period.iloc[0],cap=cap,h=h,n=n,diff=alt['ret'+str(h)].mean()-base['ret'+str(h)].mean(),open_diff=alt['nextopen_ret'+str(h)].mean()-base['nextopen_ret'+str(h)].mean(),turnover=1-len(set(base.episode_id)&set(alt.episode_id))/n))
    for name,s in [('E',base),('E_support',alt)]:
     q=s[['sid','day','episode_id','age','year','period','ret'+str(h),'nextopen_ret'+str(h),'big60','fail_rebound20']].copy();q['cap']=cap;q['h']=h;q['ranker']=name;q=q.rename(columns={'ret'+str(h):'ret','nextopen_ret'+str(h):'open_ret'});rows.append(q)
 r=pd.concat(rows,ignore_index=True);r.to_parquet(B/'FULLQUEUE_SELECTED_STOCKDAYS.parquet',index=False,compression='zstd');d=pd.DataFrame(daily);d.to_csv(B/'FULLQUEUE_DAILY_COMPARISONS.csv',index=False)
 out=[]
 for keys,g in r.groupby(['period','cap','h','ranker']):
  e=g.groupby('episode_id').agg(ret=('ret','mean'),open_ret=('open_ret','mean'),big60=('big60','mean'),fail20=('fail_rebound20','mean'),exposures=('day','size'))
  out.append(dict(zip(['period','cap','h','ranker'],keys))|dict(stockdays=len(g),episodes=len(e),stocks=g.sid.nunique(),dates=g.day.nunique(),mean_selected_days_per_episode=e.exposures.mean(),event_equal_ret=e.ret.mean(),event_equal_open_ret=e.open_ret.mean(),event_equal_big60=e.big60.mean(),event_equal_fail20=e.fail20.mean(),daily_exposure_ret=g.ret.mean()))
 pd.DataFrame(out).to_csv(B/'FULLQUEUE_EVENT_SUMMARY.csv',index=False)
 dy=d.groupby(['year','cap','h']).agg(dates=('day','size'),diff=('diff','mean'),open_diff=('open_diff','mean'),turnover=('turnover','mean')).reset_index();dy.to_csv(B/'FULLQUEUE_BY_YEAR.csv',index=False)
 de=d.groupby(['period','cap','h']).agg(dates=('day','size'),diff=('diff','mean'),open_diff=('open_diff','mean'),turnover=('turnover','mean')).reset_index();de.to_csv(B/'FULLQUEUE_DAILY_SUMMARY.csv',index=False)
 dump('FULLQUEUE_COMPLETION.json',dict(status='COMPLETE_EXPLORATORY',extra_missing_rows=missing,selection_universe_rows=len(x),selected_stockday_rows=len(r),elapsed=time.time()-tic));print(pd.DataFrame(out).to_string(index=False));print(de.to_string(index=False));print(dy.to_string(index=False));print('COMPLETE',time.time()-tic)
if __name__=='__main__':main()
