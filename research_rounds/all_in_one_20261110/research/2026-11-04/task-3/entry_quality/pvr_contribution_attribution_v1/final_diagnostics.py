"""Reporting diagnostics; preserves frozen raw research outputs. No new ranker."""
from pathlib import Path
import json,time,hashlib
import numpy as np,pandas as pd
B=Path(__file__).resolve().parent;C=B.parent/'daily_signal_cache_pilot20_v1/full_universe_v1';rng=np.random.default_rng(82914)
def dump(n,x):(B/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 tic=time.time();daily=pd.read_csv(B/'FULLQUEUE_DAILY_COMPARISONS.csv',parse_dates=['day']);r=pd.read_parquet(B/'FULLQUEUE_SELECTED_STOCKDAYS.parquet');x=pd.read_parquet(B/'ALL_BUY_ATTRIBUTIONS.parquet');entry=pd.read_parquet(B/'EVENT_COHORTS_MECHANISM.parquet');entry=entry.loc[entry.cohort.eq('entry0')]
 # Prevent consumption of incomplete cross-horizon auxiliary metrics. Raw prior outputs stay unchanged.
 corrected=[]
 for file in ['COMMON_COMPLETE_RANKING_SUMMARY.csv','YEAR_RANKING.csv','BREAKOUT_RANKING_SUMMARY.csv','BREAKOUT_RANKING_BY_YEAR.csv','FULLQUEUE_EVENT_SUMMARY.csv']:
  q=pd.read_csv(B/file)
  for col in q.columns:
   if 'big60'in col and'h'in q:q.loc[q.h.eq(20),col]=np.nan
  target='REPORTING_'+file;q.to_csv(B/target,index=False);corrected.append(target)
 # Four-quadrant tie exclusion, avoid sid-based arbitrary zero contrasts.
 qp=pd.read_parquet(B/'SUPPLEMENT_PAIRS.parquet');qp=qp.loc[qp.feature_diff.ne(0)];qs=qp.groupby(['period','feature']).agg(pairs=('feature','size'),ret20_n=('ret20','count'),ret20_diff=('ret20','mean'),ret60_n=('ret60','count'),ret60_diff=('ret60','mean'),big60_diff=('big60','mean'),fail_rebound20_diff=('fail_rebound20','mean')).reset_index();qs.to_csv(B/'REPORTING_QUADRANTS_NO_TIES.csv',index=False)
 # Daily paired distribution and month cluster descriptive uncertainty.
 dist=[]
 for keys,g in daily.groupby(['period','cap','h']):
  val=g['diff'];g=g.copy();g['month']=g.day.dt.to_period('M').astype(str);m=g.groupby('month')['diff'].agg(['sum','count']);ix=rng.integers(0,len(m),size=(2000,len(m)));boot=m['sum'].to_numpy()[ix].sum(1)/m['count'].to_numpy()[ix].sum(1)
  z=dict(zip(['period','cap','h'],keys));z.update(dates=len(g),selected_stockdays=int(g.n.sum()),mean=val.mean(),std=val.std(),p05=val.quantile(.05),p25=val.quantile(.25),median=val.median(),p75=val.quantile(.75),p95=val.quantile(.95),win_fraction=(val>0).mean(),loss_fraction=(val<0).mean(),tie_fraction=(val==0).mean(),min=val.min(),max=val.max(),month_boot_lo=np.quantile(boot,.025),month_boot_hi=np.quantile(boot,.975),open_mean=g.open_diff.mean(),turnover=g.turnover.mean());dist.append(z)
 pd.DataFrame(dist).to_csv(B/'FULLQUEUE_DAILY_DISTRIBUTION.csv',index=False)
 # Equal-event aggregation, stock bootstrap (same resampled sids for both methods).
 er=[];ey=[]
 for keys,g in r.groupby(['period','cap','h']):
  ev=g.groupby(['ranker','episode_id','sid']).agg(ret=('ret','mean'),open_ret=('open_ret','mean'),days=('day','size')).reset_index();stat=ev.groupby(['sid','ranker']).agg(s=('ret','sum'),n=('ret','size')).unstack('ranker').fillna(0);nstock=len(stat);draw=rng.integers(0,nstock,size=(2000,nstock))
  avg={}
  for name in ['E','E_support']:
   sm=stat[('s',name)].to_numpy();nn=stat[('n',name)].to_numpy();avg[name]=sm[draw].sum(1)/nn[draw].sum(1)
  boot=avg['E_support']-avg['E'];base=ev.loc[ev.ranker.eq('E')];alt=ev.loc[ev.ranker.eq('E_support')]
  er.append(dict(zip(['period','cap','h'],keys))|dict(base_episodes=len(base),alt_episodes=len(alt),stock_clusters=nstock,base=base.ret.mean(),alternative=alt.ret.mean(),diff=alt.ret.mean()-base.ret.mean(),stock_boot_lo=np.quantile(boot,.025),stock_boot_hi=np.quantile(boot,.975),open_diff=alt.open_ret.mean()-base.open_ret.mean()))
 for keys,g in r.groupby(['year','cap','h','ranker']):
  e=g.groupby('episode_id').agg(ret=('ret','mean'),open_ret=('open_ret','mean'))
  ey.append(dict(zip(['year','cap','h','ranker'],keys))|dict(dates=g.day.nunique(),stockdays=len(g),episodes=len(e),stocks=g.sid.nunique(),event_mean=e.ret.mean(),event_median=e.ret.median(),event_p05=e.ret.quantile(.05),event_p95=e.ret.quantile(.95),open_event_mean=e.open_ret.mean()))
 pd.DataFrame(er).to_csv(B/'FULLQUEUE_EVENT_STOCK_BOOTSTRAP.csv',index=False);pd.DataFrame(ey).to_csv(B/'FULLQUEUE_EVENT_BY_YEAR.csv',index=False)
 # Opportunity coverage anchored once at original I entry, NOT changing with each repeat buy date.
 cov=[]
 for (period,cap),g in r.loc[r.h.eq(60)].groupby(['period','cap']):
  target=entry.loc[entry.period.eq(period)&entry.big60.eq(1)];targetids=set(target.episode_id)
  sets={};early={};known={}
  for name in ['E','E_support']:
   v=g.loc[g.ranker.eq(name)].groupby('episode_id').age.min();sets[name]=set(v.index)&targetids;early[name]=set(v.loc[v<=5].index)&targetids;known[name]=len(v)
  cov.append(dict(period=period,cap=cap,entry_big60_opportunities=len(targetids),base_selected_episodes=known['E'],alt_selected_episodes=known['E_support'],base_large_episode_ever=len(sets['E']),alt_large_episode_ever=len(sets['E_support']),large_lost=len(sets['E']-sets['E_support']),large_added=len(sets['E_support']-sets['E']),base_large_episode_age_le5=len(early['E']),alt_large_episode_age_le5=len(early['E_support']),early_large_lost=len(early['E']-early['E_support']),early_large_added=len(early['E_support']-early['E'])))
 pd.DataFrame(cov).to_csv(B/'FULLQUEUE_FIXED_ENTRY_OPPORTUNITY_COVERAGE.csv',index=False)
 # Full available original candidate counts. Exclusion sources overlap, not additive.
 original=pd.read_csv(C/'ANNUAL_SIGNAL_COVERAGE.csv');counts=x.groupby('year').size();original['attributed_buy_rows']=original.year.map(counts).fillna(0).astype(int);original['unattributed_buy_rows']=original.i_buy_true_stockdays-original.attributed_buy_rows;original.to_csv(B/'ANNUAL_ATTRIBUTION_COVERAGE.csv',index=False)
 # Entry-only counts and horizon-specific date distribution, needed to distinguish from complete buy queue.
 e=pd.read_csv(B/'BREAKOUT_COMMON_DATE_RANKING.csv');e=e.loc[(e.ranker=='E_support')&(e.cap=='top20pct')];e.groupby(['year','h']).agg(dates=('day','size'),selected_events=('n','sum'),diff=('diff','mean'),open_diff=('open_diff','mean'),win_fraction=('diff',lambda v:(v>0).mean()),loss_fraction=('diff',lambda v:(v<0).mean()),median=('diff','median'),p05=('diff',lambda v:v.quantile(.05)),p95=('diff',lambda v:v.quantile(.95))).reset_index().to_csv(B/'ENTRY_SUPPORT_ANNUAL_DISTRIBUTION.csv',index=False)
 # Ex-post representative swapped pairs: median positive / negative 60-observation difference within each of 2022/24/25.
 rr=r.loc[(r.h==60)&(r.cap=='top20pct')];swaps=[]
 for day,g in rr.groupby('day'):
  b=g.loc[g.ranker.eq('E')].set_index('sid');a=g.loc[g.ranker.eq('E_support')].set_index('sid');added=a.loc[sorted(set(a.index)-set(b.index))];lost=b.loc[sorted(set(b.index)-set(a.index))]
  assert len(added)==len(lost)
  for (sidp,p),(sidm,m)in zip(added.iterrows(),lost.iterrows()):swaps.append(dict(day=day,year=int(p.year),promoted=sidp,demoted=sidm,diff=p.ret-m.ret))
 swaps=pd.DataFrame(swaps);chosen=[]
 for year in [2022,2024,2025]:
  for kind in ['benefit','harm']:
   s=swaps.loc[swaps.year.eq(year)&(swaps['diff'].gt(0)if kind=='benefit'else swaps['diff'].lt(0))].copy();med=s['diff'].median();row=s.loc[(s['diff']-med).abs().idxmin()].to_dict();row['kind']=kind;chosen.append(row)
 cases=[];terms=[];cache={};w=.9**np.arange(20,-1,-1);w/=w.sum()
 for caseid,pair in enumerate(chosen):
  for side in ['promoted','demoted']:
   sid=pair[side];day=pd.Timestamp(pair['day']);g=cache.setdefault(sid,pd.read_parquet(C/'artifacts'/f'{sid}.parquet'));g=g.loc[g.source_row_present].reset_index(drop=True);i=int(np.flatnonzero(g.day.eq(day))[0]);a=g.iloc[i-20:i+1];hh=g.price__close.iloc[i-24:i-4].max();p5=float((g.price__close.iloc[i-4:i+1]>hh).mean());amp=w*.5*a.pvr__u.to_numpy()*abs(a.pvr__u.to_numpy())*a.pvr__b.to_numpy();up=amp*((a.pvr__u.to_numpy()>0)&(a.pvr__b.to_numpy()>0));E=float(g.pvr__E.iloc[i]);es=E-up.sum()*(1-p5)
   v=x.loc[x.sid.eq(sid)&x.day.eq(day)].iloc[0].to_dict();v.update(case_id=caseid,kind=pair['kind'],side=side,pair_return60_diff=pair['diff'],A_up=up.sum(),hold5=p5,fixed_resistance=float(hh),E_support=es,E_discount=E-es,score_support=50+50*np.tanh(2*es));cases.append(v)
   for j,(_,row)in enumerate(a.iterrows()):terms.append(dict(case_id=caseid,kind=pair['kind'],side=side,sid=sid,signal_day=day,contribution_day=row.day,age=20-j,weight=w[j],r=row.pvr__r,scale=row.pvr__scale,u=row.pvr__u,b=row.pvr__b,amount=row.price__amount,amount_ref=row.pvr__amount_ref,e=row.pvr__e,d=w[j]*row.pvr__e,price_d=w[j]*row.pvr__u,amount_d=amp[j],up_amount_d=up[j],support_discount=up[j]*(1-p5)))
 pd.DataFrame(cases).to_csv(B/'SUPPORT_BENEFIT_HARM_CASES.csv',index=False);pd.DataFrame(terms).to_csv(B/'SUPPORT_CASE_DAILY_CONTRIBUTIONS.csv',index=False)
 dump('REPORTING_CORRECTIONS.json',dict(auxiliary_horizon='All h20 rows have big60 fields blanked in REPORTING_* outputs. Only h60-complete selections support 60-label conclusions.',corrected_files=corrected,quad_ties='Excluded exact feature ties in REPORTING_QUADRANTS_NO_TIES.csv.',raw_frozen_outputs_preserved=True,comparability='Each baseline-versus-candidate pair uses its own common complete dates, not all-ranker intersection.',label='big60 and fail20 refer different horizons and may overlap; not successful/failed executed trades.',case_selection='Six explanatory swaps selected ex post near median positive/negative 60-bar swap delta for each of 2022,2024,2025. No statistical validation from these cases.'))
 dump('FINAL_DIAGNOSTICS_COMPLETE.json',dict(status='COMPLETE',elapsed=time.time()-tic))
 print(pd.DataFrame(er).to_string(index=False));print(pd.DataFrame(cov).to_string(index=False));print(pd.DataFrame(cases)[['case_id','kind','day','side','sid','score','A_up','hold5','E_discount','ret20','ret60','next_open_gap','next_open_range_zero']].to_string(index=False));print('COMPLETE',time.time()-tic)
if __name__=='__main__':main()
