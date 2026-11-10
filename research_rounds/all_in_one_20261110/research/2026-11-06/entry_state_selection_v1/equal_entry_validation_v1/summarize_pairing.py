"""Descriptive paired and clustered diagnostics for one frozen ranking. No tuning."""
from pathlib import Path
import numpy as np,pandas as pd,json,hashlib
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/equal_entry_validation_v1')
d=pd.read_parquet(O/'SELECTED_SAME_PATH_LABELS.parquet');cand=pd.read_parquet(O/'ALL_ORIGINAL_I_BUY_WITH_STATES.parquet');entry=pd.read_parquet(O/'FIXED_ORIGINAL_I_ENTRY_LABELS.parquet')
domain=[]
for y,g in cand.groupby('year'):
 domain.append(dict(year=int(y),original_i_buy=len(g),pvr_known=int(g.pvr_known.sum()),root_known=int(g.original_epoch.notna().sum()),original_roots=g.original_epoch.nunique(),stocks=g.sid.nunique(),dates=g.day.nunique(),fresh_day0=int(g.stratum.eq('FRESH_DAY0').sum()),confirmed=int(g.stratum.eq('CONFIRMED').sum()),prebreak=int(g.stratum.eq('PREBREAK').sum()),other_unknown=int(g.stratum.eq('OTHER_OR_UNKNOWN').sum())))
pd.DataFrame(domain).to_csv(O/'ANNUAL_ORIGINAL_DOMAIN.csv',index=False)
weights=[]
for(y,s),g in d.groupby(['year','strategy']):
 for role,q in g.groupby('selection_role'):
  weights.append(dict(year=int(y),strategy=s,role=role,rows=len(q),fraction_of_slots=len(q)/len(g),implied_average_notional_per_date=q.slot_weight.sum()/g.day.nunique()))
pd.DataFrame(weights).to_csv(O/'ACTUAL_SLOT_WEIGHTS.csv',index=False)
summ=[];strata=[];bs=[];replacements=[];rootouts=[];kept_days={}
for h,net,mae in [('20','net20','mae20'),('60','net60','mae60'),('I','I_net','I_mae')]:
 complete=d.groupby('day')[net].apply(lambda x:x.notna().all());good=set(complete[complete].index);kept_days[h]=good
 q=d[d.day.isin(good)].copy();q['weighted_net']=q[net]*q.slot_weight;q['weighted_mae']=q[mae]*q.slot_weight
 per=q.groupby(['day','strategy']).agg(basket_net=('weighted_net','sum'),basket_mae=('weighted_mae','sum'),selected=('sid','size')).reset_index()
 p=per.pivot(index='day',columns='strategy',values='basket_net').reset_index();p['delta']=p.STATE_5F_15V-p.BASE_PVR;p['year']=p.day.str[:4].astype(int)
 p.to_csv(O/('PAIRED_DAILY_'+h+'.csv'),index=False)
 for y in sorted(d.year.unique()):
  yy=q[q.year.eq(y)];pp=p[p.year.eq(y)];all_dates=d[d.year.eq(y)].day.nunique()
  root=yy[yy.original_epoch.notna()].groupby(['strategy','sid','original_epoch'])[net].mean().reset_index()
  root['horizon']=h;root['reporting_year']=y;rootouts.append(root.rename(columns={net:'mean_net'}))
  a=root[root.strategy.eq('BASE_PVR')];b=root[root.strategy.eq('STATE_5F_15V')]
  same=a[['original_epoch',net]].merge(b[['original_epoch',net]],on='original_epoch',suffixes=('_base','_alt'))
  A=yy[yy.strategy.eq('BASE_PVR')];B=yy[yy.strategy.eq('STATE_5F_15V')]
  summ.append(dict(horizon=h,year=int(y),all_rank_dates=all_dates,paired_complete_dates=len(pp),excluded_dates=all_dates-len(pp),selected_stockdays_each=len(A),base_roots=len(a),alt_roots=len(b),shared_roots=len(same),base_daily_basket_net=A.weighted_net.sum()/len(pp)if len(pp)else np.nan,alt_daily_basket_net=B.weighted_net.sum()/len(pp)if len(pp)else np.nan,daily_difference=pp.delta.mean(),base_root_net=a[net].mean(),alt_root_net=b[net].mean(),root_difference=b[net].mean()-a[net].mean(),shared_root_difference=(same[net+'_alt']-same[net+'_base']).mean(),base_mean_mae=A[mae].mean(),alt_mean_mae=B[mae].mean(),base_support_risk=A.support_risk.mean(),alt_support_risk=B.support_risk.mean(),base_risk_known_fraction=A.support_risk.notna().mean(),alt_risk_known_fraction=B.support_risk.notna().mean()))
  for (st,phase),gg in yy.groupby(['strategy','stratum']):
   rr=gg[gg.original_epoch.notna()].groupby('original_epoch')[net].mean()
   strata.append(dict(horizon=h,year=int(y),strategy=st,stratum=phase,stockdays=len(gg),roots=len(rr),root_mean_net=rr.mean(),mean_mae=gg[mae].mean(),mean_support_risk=gg.support_risk.mean(),flat_entry_posthoc=int(gg.entry_flat_posthoc.sum()),gap_gt3pct=int(gg.entry_gap.gt(.03).sum())))
 # Exact replacement attribution of paired same-date equal-slot baskets.
 for day,g in q.groupby('day'):
  a=g[g.strategy.eq('BASE_PVR')].set_index('sid');b=g[g.strategy.eq('STATE_5F_15V')].set_index('sid');added=b.index.difference(a.index);removed=a.index.difference(b.index)
  dd=(b.loc[added,net].sum()-a.loc[removed,net].sum())/20
  obs=float(p.loc[p.day.eq(day),'delta'].iloc[0])
  assert abs(dd-obs)<1e-12
  replacements.append(dict(horizon=h,day=day,added=len(added),removed=len(removed),common=len(a.index.intersection(b.index)),added_mean_net=b.loc[added,net].mean(),removed_mean_net=a.loc[removed,net].mean(),exact_basket_diff=dd))
 # Global I-root mean then same sampled stock clusters for both estimators.
 root=q[q.original_epoch.notna()].groupby(['strategy','sid','original_epoch'])[net].mean().reset_index()
 sidstats=root.groupby(['sid','strategy'])[net].agg(['sum','count']).unstack('strategy').fillna(0)
 for st in ['BASE_PVR','STATE_5F_15V']:
  for col in ['sum','count']:
   if(col,st)not in sidstats:sidstats[(col,st)]=0
 a_sum=sidstats[('sum','BASE_PVR')].to_numpy();a_n=sidstats[('count','BASE_PVR')].to_numpy();b_sum=sidstats[('sum','STATE_5F_15V')].to_numpy();b_n=sidstats[('count','STATE_5F_15V')].to_numpy()
 n=len(sidstats);rng=np.random.default_rng(20261106);draw=rng.multinomial(n,np.ones(n)/n,size=1000)
 boot=(draw@b_sum)/(draw@b_n)-(draw@a_sum)/(draw@a_n)
 observed=b_sum.sum()/b_n.sum()-a_sum.sum()/a_n.sum()
 drop=(b_sum.sum()-b_sum)/(b_n.sum()-b_n)-(a_sum.sum()-a_sum)/(a_n.sum()-a_n)
 influence=observed-drop;imax=int(np.nanargmax(influence))
 # Month blocks for paired daily mean, weighted by date counts after resampling.
 pp=p.assign(month=p.day.str[:7]).groupby('month').delta.agg(['sum','count'])
 ix=rng.integers(0,len(pp),size=(1000,len(pp)));bm=pp['sum'].to_numpy()[ix].sum(axis=1)/pp['count'].to_numpy()[ix].sum(axis=1)
 monthly_drop=(p.delta.sum()-pp['sum'])/(len(p)-pp['count']);bestmonth=(p.delta.mean()-monthly_drop).idxmax()
 bs.append(dict(horizon=h,global_base_roots=int(a_n.sum()),global_alt_roots=int(b_n.sum()),stock_clusters=n,event_root_difference=observed,stock_cluster_lo=np.quantile(boot,.025),stock_cluster_hi=np.quantile(boot,.975),paired_daily_difference=p.delta.mean(),paired_monthblock_lo=np.quantile(bm,.025),paired_monthblock_hi=np.quantile(bm,.975),largest_positive_stock_influence=str(sidstats.index[imax]),root_difference_without_that_stock=drop[imax],largest_positive_month_influence=bestmonth,daily_difference_without_that_month=float(monthly_drop.loc[bestmonth])))
pd.DataFrame(summ).to_csv(O/'PAIRED_ANNUAL_RESULTS.csv',index=False)
pd.DataFrame(strata).to_csv(O/'STATE_STRATUM_RESULTS.csv',index=False)
pd.DataFrame(bs).to_csv(O/'CLUSTERED_AND_LEAVE_ONE_DIAGNOSTICS.csv',index=False)
pd.DataFrame(replacements).to_csv(O/'EXACT_REPLACEMENT_ATTRIBUTION.csv',index=False)
pd.concat(rootouts,ignore_index=True).to_parquet(O/'YEAR_I_ROOT_CLUSTER_MEANS.parquet',index=False)
# Fixed original-entry opportunity labels; independent of which day either ranker selected.
cov=entry[['sid','day','original_epoch','year','complete60','big60','ret60','mfe60','mae60','entry_open','entry_flat_posthoc']].copy()
early=d[d.original_age_obs.le(5)&d.original_epoch.notna()]
for st in ['BASE_PVR','STATE_5F_15V']:
 g=early[early.strategy.eq(st)]
 sig=g.groupby('original_epoch').day.min();px=g[g.open_known].groupby('original_epoch').day.min()
 cov[st+'_early_signal_day']=cov.original_epoch.map(sig);cov[st+'_early_open_proxy_day']=cov.original_epoch.map(px)
cov['base_captured']=cov.BASE_PVR_early_open_proxy_day.notna();cov['alt_captured']=cov.STATE_5F_15V_early_open_proxy_day.notna()
cov.to_parquet(O/'FIXED_ENTRY_COVERAGE_BY_ROOT.parquet',index=False)
coverage=[]
for y,g in cov.groupby('year'):
 known=g[g.complete60];big=known[known.big60];a=big.base_captured;b=big.alt_captured
 coverage.append(dict(year=int(y),original_entry_ready_i_buy_pvr=len(g),complete_entry60=len(known),big60_roots=len(big),base_early_capture=int(a.sum()),alt_early_capture=int(b.sum()),lost=int((a&~b).sum()),added=int((~a&b).sum()),retained=int((a&b).sum()),alt_over_base_capture=b.sum()/a.sum()if a.sum()else np.nan))
pd.DataFrame(coverage).to_csv(O/'EARLY_BIG_OPPORTUNITY_COVERAGE.csv',index=False)
cov[cov.big60&(cov.base_captured!=cov.alt_captured)].to_csv(O/'LOST_AND_ADDED_BIG_ROOTS.csv',index=False)
# Loss-to-opportunity diagnostic on one explicitly shared fixed-entry complete60 cohort.
risk=[]
eligible_roots=set(cov[cov.complete60].original_epoch);bigroots=set(cov[cov.big60].original_epoch)
for st in ['BASE_PVR','STATE_5F_15V']:
 q=d[d.strategy.eq(st)&d.day.isin(kept_days['20'])&d.original_epoch.isin(eligible_roots)].copy()
 q['net20_R']=q.net20/q.support_risk
 rr=q.groupby('original_epoch').agg(net=('net20','mean'),R=('net20_R','mean'),risk_known=('support_risk',lambda x:x.notna().mean()))
 captured=set(q[q.original_age_obs.le(5)&q.open_known].original_epoch)&bigroots
 risk.append(dict(strategy=st,selected_roots=len(rr),roots_R_known=int(rr.R.notna().sum()),early_big_captured_within_paired20=len(captured),sum_negative_root_net=-rr.net.clip(upper=0).sum(),negative_notional_return_per_big=-rr.net.clip(upper=0).sum()/len(captured)if len(captured)else np.nan,sum_negative_root_R=-rr.R.clip(upper=0).sum(),negative_R_per_big=-rr.R.clip(upper=0).sum()/len(captured)if len(captured)else np.nan,warning='Structural S risk proxy only; unknown risk excluded from R numerator. Not realized account risk or a stop guarantee.'))
pd.DataFrame(risk).to_csv(O/'LOSS_PER_BIG_DIAGNOSTIC.csv',index=False)
# Execution warnings retain all ranked selections; never tradeability filters.
execrows=[]
for(y,st),g in d.groupby(['year','strategy']):
 execrows.append(dict(year=int(y),strategy=st,selected_stockdays=len(g),open_unknown=int((~g.open_known).sum()),entry_flat_posthoc=int(g.entry_flat_posthoc.sum()),entry_flat_up_posthoc=int(g.entry_flat_up_posthoc.sum()),entry_flat_down_posthoc=int(g.entry_flat_down_posthoc.sum()),gap_gt3pct=int(g.entry_gap.gt(.03).sum()),gap_gt5pct=int(g.entry_gap.gt(.05).sum()),I_right_censored=int(g.I_right_censored.sum()),I_interrupted_knowledge=int(g.I_interrupted_knowledge.sum()),I_exit_missing_open=int(g.I_exit_missing_open.sum()),I_exit_flat_down_posthoc=int(g.I_exit_flat_down_posthoc.sum()),I_exit_gap_ltminus3=int(g.I_exit_gap.lt(-.03).sum()),worst_I_exit_gap=g.I_exit_gap.min()))
pd.DataFrame(execrows).to_csv(O/'EXECUTION_WARNINGS.csv',index=False)
print('ANNUAL');print(pd.DataFrame(summ).to_string(index=False));print('CLUSTER');print(pd.DataFrame(bs).to_string(index=False));print('COVERAGE');print(pd.DataFrame(coverage).to_string(index=False));print('RISK');print(pd.DataFrame(risk).to_string(index=False))
(O/'SUMMARY_COMPLETION.json').write_text(json.dumps(dict(status='COMPLETE_DESCRIPTIVE_PAIRED_PRICES_NOT_PORTFOLIO',ranking_variants=2,candidate_variants=1,K=20,fee_sensitivity=.005,account_runs=0,parameter_searches=0),indent=2))
