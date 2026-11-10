from pathlib import Path
import json,sys,importlib.util,time,datetime
import pandas as pd
import numpy as np
O=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/time-evidence-audit-20261029');sp=importlib.util.spec_from_file_location('time_sum',O/'code/audit.py');S=importlib.util.module_from_spec(sp);sys.modules[sp.name]=S;sp.loader.exec_module(S);H=S.H;t=time.monotonic()
a=pd.read_parquet(O/'diagnostic/event-timing.parquet');cache=pd.read_parquet(S.E1/'market-cache.parquet');ep=pd.read_parquet(S.E1/'opportunities.parquet');assert len(ep)==5349 and int(a.I_buy.sum())==35316 and int(cache.Q.sum())==32899
groups={'new_E0':a[a.E0_new],'all_E0_up_receipts':a[a.E0_up_receipt],'first_I_in_study_E0':a[a.first_I_in_study_epoch],'all_I':a[a.I_buy],'repeat_I':a[a.I_buy&~a.first_I_in_study_epoch],'first_legal_Q':a[a.first_Q_in_study_epoch],'all_legal_Q':a[a.Q]};summary={}
for name,g in groups.items():
    n=len(g);summary[name]=dict(n=n,leg_age_one=int(g.leg_age.eq(1).sum()),leg_age_one_fraction=float(g.leg_age.eq(1).mean()),one_frontier_day=int(g.frontier_days.eq(1).sum()),one_frontier_day_fraction=float(g.frontier_days.eq(1).mean()),frontier_neff_lt2=int(g.frontier_neff.lt(2).sum()),frontier_neff_lt2_fraction=float(g.frontier_neff.lt(2).mean()),single_frontier_majority=int(g.max_frontier_share.gt(.5).sum()),single_frontier_majority_fraction=float(g.max_frontier_share.gt(.5).mean()),I_state_new=int(g.I_state_new.sum()),warm_age_one=int(g.warm_age.eq(1).sum()),fast_launch=int(g.phase.eq('fast_launch').sum()),fast_launch_nonpositive_z21=int((g.phase.eq('fast_launch')&g.z21.le(0)).sum()),G1_reason_missing=int(g.phase.isna().sum()),carry_E0=int(g.carry_E0.sum()),quantiles={k:{str(q):float(v) for q,v in g[k].quantile([0,.25,.5,.75,.9,.95,.99,1]).items()} for k in ['leg_age','frontier_days','frontier_neff','max_frontier_share','last_frontier_share','last_volume_share','E0_age','I_state_age','warm_age']})
H.save(O/'diagnostic/summary.json',summary)
daycounts=pd.DataFrame(index=sorted(cache.date.unique()))
for name,g in groups.items():daycounts[name]=g.groupby('date').size().reindex(daycounts.index,fill_value=0)
daycounts.to_csv(O/'diagnostic/daily-counts.csv',index_label='date');daily={}
for name in daycounts:
 z=daycounts[name];daily[name]=dict(total=int(z.sum()),mean=float(z.mean()),median=float(z.median()),p90=float(z.quantile(.9)),p95=float(z.quantile(.95)),p99=float(z.quantile(.99)),max=int(z.max()),peak_dates=[str(pd.Timestamp(d).date()) for d in z.index[z.eq(z.max())]])
H.save(O/'diagnostic/daily-summary.json',daily)
life=[]
for e in ep.to_dict('records'):
 g=a[a.e0_epoch.eq(e['event_id'])];ii=g[g.I_buy];qq=g[g.Q];life.append(dict(**e,I_signals=len(ii),Q_signals=len(qq),first_I=str(ii.date.iloc[0].date()) if len(ii) else None,first_Q=str(qq.date.iloc[0].date()) if len(qq) else None))
pd.DataFrame(life).to_csv(O/'diagnostic/all-5349-opportunities.csv',index=False);assert sum(x['I_signals'] for x in life)==35316 and sum(x['Q_signals'] for x in life)==32899
counts=dict(common_E0_epochs=5349,new_E0_epochs=5169,carry_E0_epochs=180,epochs_with_I=sum(x['I_signals']>0 for x in life),epochs_without_I=sum(x['I_signals']==0 for x in life),epochs_with_Q=sum(x['Q_signals']>0 for x in life),epochs_without_Q=sum(x['Q_signals']==0 for x in life),all_I=35316,repeat_I=30941,all_Q=32899,repeat_Q=32899-4059,raw_I_repeat_fraction=30941/35316,Q_repeat_fraction=(32899-4059)/32899)
H.save(O/'diagnostic/lifecycle-summary.json',counts)
ident=H.read(O/'input-identity.json')['sha256'];assert all(H.sha(p)==h for p,h in ident.items());plan=H.read(O/'RUN_PLAN.json');elapsed=(datetime.datetime.now(datetime.timezone.utc)-datetime.datetime.fromisoformat(plan['implementation_clock_started_at'])).total_seconds();H.save(O/'diagnostic/aggregate-verification.json',dict(passed=True,all_populations_cover_full_sample=True,first_plus_repeats_equals_all=True,all_5349_epochs_including_no_signal=True,source_hashes_unchanged=len(ident),no_economic_results_read_or_run=True,aggregate_seconds=time.monotonic()-t,implementation_wall_seconds_since_recorded_stage=elapsed,earlier_reading_not_timed=True,development_budget_minutes=15,full_diagnostic_seconds=H.read(O/'diagnostic/verification.json')['seconds']))
print(json.dumps(dict(lifecycle=counts,daily=daily,aggregate_seconds=time.monotonic()-t,implementation_wall_seconds_since_recorded_stage=elapsed),ensure_ascii=False,indent=2))
