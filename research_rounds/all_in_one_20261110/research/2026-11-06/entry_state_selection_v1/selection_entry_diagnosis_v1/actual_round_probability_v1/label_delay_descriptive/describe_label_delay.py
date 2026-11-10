"""Descriptive duration and administrative-censoring counts only; no fitting or account execution."""
from pathlib import Path
import pandas as pd,numpy as np,json,hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
O=Path(__file__).resolve().parent;P=O.parent
f=pd.read_csv(P/'ALL_ORIGINAL_ROUNDS_WITH_FORWARD_PREDICTIONS.csv')
days=pd.read_csv(P.parent/'entry_probability_signal_v1/MARKET_CLOCK.csv',index_col=0,parse_dates=True).index
end=days.get_loc(pd.Timestamp('2026-05-15'))
f['observed_duration']=np.where(f.closed,f.close_t-f.entry_t+1,end-f.entry_t+1).astype(int)
assert f.observed_duration.ge(1).all()
curves=[];duration=[]
for cohort,g in list(f.groupby('year'))+[('2022_2025',f[f.year.between(2022,2025)])]:
 if int(cohort) <2022 if isinstance(cohort,(int,np.integer)) else False:continue
 N=len(g);w=g[g.closed&g.y.eq(1)];l=g[g.closed&g.y.eq(0)];c=g[~g.closed]
 maxh=max(252,int(g.observed_duration.max()))
 for h in range(maxh+1):
  nw=int(w.observed_duration.le(h).sum());nl=int(l.observed_duration.le(h).sum());nc=int(c.observed_duration.lt(h).sum())
  curves.append(dict(cohort=str(cohort),duration_sessions=h,births=N,win_events_by_h=nw,loss_events_by_h=nl,censored_before_h=nc,win_cumulative_lower=nw/N,win_cumulative_upper=(nw+nc)/N,loss_cumulative_lower=nl/N,loss_cumulative_upper=(nl+nc)/N,known_still_in_round_fraction=(N-nw-nl-nc)/N,unknown_beyond_observed_fraction=nc/N,closed_winner_duration_CDF=nw/len(w) if len(w) else np.nan,closed_loser_duration_CDF=nl/len(l) if len(l) else np.nan))
 for name,z in [('WIN_CLOSED',w),('LOSS_CLOSED',l),('OPEN_CENSORED',c)]:
  duration.append(dict(cohort=str(cohort),status=name,n=len(z),median_observed_duration=z.observed_duration.median(),p25=z.observed_duration.quantile(.25),p75=z.observed_duration.quantile(.75),p90=z.observed_duration.quantile(.9),max_observed_duration=z.observed_duration.max()))
curves=pd.DataFrame(curves);dur=pd.DataFrame(duration)
curves.to_csv(O/'DURATION_CUMULATIVE_INCIDENCE_BOUNDS.csv',index=False);dur.to_csv(O/'DURATION_BY_OUTCOME.csv',index=False)
curves[curves.duration_sessions.isin([5,10,20,40,60,120,252])].to_csv(O/'DURATION_FIXED_HORIZONS.csv',index=False)
monthly=[]
for month in sorted({str(d.to_period('M')) for d in days if 2023<=d.year<=2025}):
 dt=next(d for d in days if str(d.to_period('M'))==month);cut=days.get_loc(dt)
 # Previous common close: only actually filled entries before today's first open.
 allpast=f[f.entry_t.lt(cut)]
 for window,g in [('ALL_PRIOR_ACTUAL_FILLS',allpast),('PAST504_SIGNAL_DAYS_ACTUAL_FILLS',allpast[allpast.t.ge(cut-504)])]:
  closed=g[g.closed&g.close_t.lt(cut)];pending=g[~(g.closed&g.close_t.lt(cut))]
  for context,gg in [('ALL',g),('NORMAL',g[g.context.eq('NORMAL')])]:
   cc=gg[gg.closed&gg.close_t.lt(cut)];pp=gg[~(gg.closed&gg.close_t.lt(cut))]
   eventual=pp[pp.closed]
   monthly.append(dict(month=month,first_session=str(dt.date()),observable_through_previous_close=str(days[cut-1].date()),window=window,context=context,prior_actual_filled_rounds=len(gg),fully_closed_observable=len(cc),still_open_observable=len(pp),open_fraction=len(pp)/len(gg) if len(gg) else np.nan,closed_observed_winrate=cc.y.mean(),pending_age_median=(cut-pp.entry_t).median(),pending_age_max=(cut-pp.entry_t).max(),pending_eventually_closed_by_source=len(eventual),pending_eventual_winrate_FOR_HINDSIGHT_AUDIT_ONLY=eventual.y.mean(),pending_still_open_at_source=int((~pp.closed).sum())))
monthly=pd.DataFrame(monthly);monthly.to_csv(O/'MONTHLY_OBSERVABLE_OPEN_FRACTIONS_2023_2025.csv',index=False)
# Reconcile conservative prior-close audit with previous model's prior-signal cohort.
old=pd.read_csv(P/'TRAINING_LABEL_DELAY_AUDIT.csv');rec=[]
for month in sorted(old.month):
 dt=next(d for d in days if str(d.to_period('M'))==month);cut=days.get_loc(dt)
 sig=f[f.t.lt(cut)&f.t.ge(cut-504)];not_yet=sig[sig.entry_t.ge(cut)]
 rec.append(dict(month=month,prior_signal_cohort=len(sig),already_filled_before_first_session=int(sig.entry_t.lt(cut).sum()),next_open_first_entries_not_filled_at_previous_close=len(not_yet),these_events=not_yet[['sid','signal_day','entry_day']].to_dict('records')))
(O/'MONTHLY_CLOCK_RECONCILIATION.json').write_text(json.dumps(rec,ensure_ascii=False,indent=2))
plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False,'figure.dpi':130})
fig,axes=plt.subplots(2,2,figsize=(12,8),sharex=True,sharey=True)
for ax,y in zip(axes.flat,[2022,2023,2024,2025]):
 z=curves[(curves.cohort==str(y))&(curves.duration_sessions<=252)]
 ax.step(z.duration_sessions,z.win_cumulative_lower*100,where='post',label='Profitable close',color='#1f77b4',lw=2)
 ax.step(z.duration_sessions,z.loss_cumulative_lower*100,where='post',label='Non-profitable close',color='#c64b4b',lw=2)
 ax.fill_between(z.duration_sessions,z.win_cumulative_lower*100,z.win_cumulative_upper*100,step='post',color='#1f77b4',alpha=.18)
 ax.fill_between(z.duration_sessions,z.loss_cumulative_lower*100,z.loss_cumulative_upper*100,step='post',color='#c64b4b',alpha=.12)
 g=f[f.year.eq(y)]
 ax.set_title(f'{y}: {len(g)} original rounds, {int((~g.closed).sum())} still open at source end')
 ax.set_xlim(0,252);ax.set_ylim(0,100);ax.grid(alpha=.2);ax.set_xlabel('Holding duration (common trading sessions)');ax.set_ylabel('Cumulative share of original round births (%)')
axes[0,0].legend(loc='lower right')
fig.suptitle('Observed profitable / non-profitable closures by duration',fontsize=15)
fig.text(.5,.015,'No fitted model. Shading marks bounds where administrative censoring leaves the outcome unknown. Source ends 2026-05-15.',ha='center',fontsize=9)
fig.tight_layout(rect=[0,.04,1,.96]);fig.savefig(O/'duration_cumulative_incidence.png');plt.close(fig)
fig,axes=plt.subplots(2,1,figsize=(12,7),sharex=True)
for window,label,color in [('ALL_PRIOR_ACTUAL_FILLS','All prior actual fills','#555555'),('PAST504_SIGNAL_DAYS_ACTUAL_FILLS','Prior 504 signal sessions, already filled','#1f77b4')]:
 z=monthly[(monthly.window==window)&monthly.context.eq('ALL')].copy();x=pd.to_datetime(z.first_session)
 axes[0].plot(x,z.open_fraction*100,label=label,color=color,marker='o',ms=3)
 axes[1].plot(x,z.still_open_observable,label=label,color=color,marker='o',ms=3)
axes[0].set_ylabel('Still-open share (%)');axes[0].legend();axes[1].set_ylabel('Still-open round count')
for ax in axes:ax.grid(alpha=.2)
axes[1].set_xlabel('Monthly first session; information cutoff is the previous common close')
fig.suptitle('2023–2025 observable unresolved labels',fontsize=15);fig.tight_layout();fig.savefig(O/'monthly_open_label_fraction.png');plt.close(fig)
meta=dict(status='DESCRIPTIVE_COUNTS_AND_CENSORING_BOUNDS_ONLY',new_models=0,account_runs=0,source_end='2026-05-15',curve_definition='Observed cause-specific cumulative event counts / all original births; bounds add administratively censored-before-h cases. No Kaplan-Meier/Aalen-Johansen fitting or independent-censoring assumption.',monthly_clock='Previous common close before first session: entry_t<cut, closure_t<cut. Next-open entries from previous signals excluded until actually filled.',sources={str(P/'ALL_ORIGINAL_ROUNDS_WITH_FORWARD_PREDICTIONS.csv'):hashlib.sha256((P/'ALL_ORIGINAL_ROUNDS_WITH_FORWARD_PREDICTIONS.csv').read_bytes()).hexdigest()})
(O/'SUMMARY.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2))
(O/'OUTPUT_SHA256.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in O.iterdir() if p.is_file() and p.name!='OUTPUT_SHA256.json'},indent=2))
print('DURATIONS',dur[dur.cohort.isin(['2022','2023','2024','2025'])].to_string(index=False))
print('MONTHLY_WINDOW',monthly.query("window=='PAST504_SIGNAL_DAYS_ACTUAL_FILLS' and context=='ALL'")[['month','prior_actual_filled_rounds','fully_closed_observable','still_open_observable','open_fraction']].to_string(index=False))
print('FIXED',curves[curves.cohort.isin(['2022','2023','2024','2025'])&curves.duration_sessions.isin([20,60,120])][['cohort','duration_sessions','births','win_events_by_h','loss_events_by_h','censored_before_h','win_cumulative_lower','loss_cumulative_lower']].to_string(index=False))
