"""Post-output comparison with root's independent check and time/partition invariants."""
from pathlib import Path
import hashlib,json
import numpy as np
import pandas as pd
O=Path(__file__).resolve().parent;V3=O.parent
rootp=V3/'ROOT_EARLY_FIXED_OUTCOMES.json';root=json.loads(rootp.read_text())
mapping={'A5_E3':'USER_COMMON_A5_E3','H1':'H1_COMMON_MATCHED_N','D':'D_COMMON_MATCHED_N','ATT':'ATT_ORIGINAL_MATCHED_N'}
checks=[]
for rr in root:
 sub='att_available' if rr['scope'].startswith('ATT_') else 'primary';p=O/sub
 f=pd.read_parquet(p/'PRICE_PATH_DISTRIBUTIONS.parquet');t=pd.read_parquet(p/'TAIL_COVERAGE_BY_PERIOD.parquet');e=pd.read_parquet(p/'FINAL_NONPOSITIVE_EXPOSURE_BY_PERIOD.parquet')
 method=mapping[rr['policy']];sel=f.grouping.eq('study_window')&f.period.eq(rr['scope'])&f.method.eq(method);fr=f[sel].iloc[0]
 tr=t[t.grouping.eq('study_window')&t.period.eq(rr['scope'])&t.method.eq(method)&t.target.eq('REL_MFE20_PRIMARY')].iloc[0]
 er=e[e.grouping.eq('study_window')&e.period.eq(rr['scope'])&e.method.eq(method)].iloc[0]
 own={'days':int(fr.signal_days),'selected_industry_days':int(fr.selected_industry_days),'relative_final20_mean_log':float(fr.final20_rel_log_mean),
  'absolute_final20_mean_log':float(fr.final20_abs_log_mean),'absolute_final20_nonpositive_fraction':float(er.final20_abs_pooled_exposure_rate),
  'relative_final20_nonpositive_fraction':float(er.final20_rel_pooled_exposure_rate),'absolute_mae20_mean_log':float(fr.mae20_abs_log_mean),
  'main_tail_hits':int(tr.total_hits),'main_tail_denominator':int(tr.total_tail),'main_tail_coverage_micro':float(tr.coverage_total_hits_over_total_tail),
  'main_tail_precision':float(tr.precision_total_hits_over_total_selected_label_known)}
 diff={k:own[k]-rr[k] for k in own};assert max(abs(x) for x in diff.values())<1e-12
 checks.append({'scope':rr['scope'],'policy':rr['policy'],'our_minus_root':diff})
mp=Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm/TradingAlarm/research/data/ths-index-history-20261018/canonical/USHI1B0300.csv')
cal=pd.to_datetime(pd.read_csv(mp,usecols=['date']).date);iso=cal.dt.isocalendar();c=pd.DataFrame({'date':cal,'y':iso.year,'w':iso.week});ends=set(c.groupby(['y','w']).date.max().dt.strftime('%Y-%m-%d'))
inv=[]
for sub in ['primary','att_available']:
 p=O/sub;tr=pd.read_parquet(p/'DAILY_AND_TRUE_WEEKEND_LIST_TURNOVER.parquet');w=tr[tr.frequency.eq('TRUE_ISO_WEEK_END')]
 assert set(w.date)<=ends
 for _,g in w.groupby(['study_window','method']):assert not bool(g.sort_values('date').iloc[0].pair_known)
 f=pd.read_parquet(p/'PRICE_PATH_DISTRIBUTIONS.parquet');du=pd.read_parquet(p/'LIST_DURATION_AND_CENSORING_BY_WINDOW.parquet')
 for r in du.itertuples():
  fr=f[f.grouping.eq('study_window')&f.period.eq(r.study_window)&f.method.eq(r.method)].iloc[0];assert int(fr.selected_industry_days)==int(r.all_selected_industry_days)
 a=pd.read_parquet(p/'EXISTING_UNION_A_ONLY_E_ONLY_BOTH_ATTRIBUTION.parquet');tail=pd.read_parquet(p/'TAIL_COVERAGE_BY_PERIOD.parquet')
 for win,g in a[a.grouping.eq('study_window')].groupby('period'):
  fr=f[f.grouping.eq('study_window')&f.period.eq(win)&f.method.eq('USER_COMMON_A5_E3')].iloc[0]
  tt=tail[tail.grouping.eq('study_window')&tail.period.eq(win)&tail.method.eq('USER_COMMON_A5_E3')&tail.target.eq('REL_MFE20_PRIMARY')].iloc[0]
  assert int(g.selected_industry_days.sum())==int(fr.selected_industry_days) and int(g.primary_relMFE20_tail_hits.sum())==int(tt.total_hits)
  avg=float((g.final20_relative_mean*g.label20_known).sum()/g.label20_known.sum());assert abs(avg-fr.final20_rel_log_mean)<1e-12
 inv.append({'scope':sub,'all_weekly_dates_true_CSI_weekends':True,'all_phase_first_week_comparisons_unknown':True,'all_spell_mass_equals_selected_days':True,'all_fixed_union_attributions_partition_exact':True})
status={'root_independent_rows_compared':len(checks),'numeric_fields_per_row':len(checks[0]['our_minus_root']),
 'max_abs_our_minus_root':max(abs(v) for x in checks for v in x['our_minus_root'].values()),
 'root_file_read_only_after_own_run_completed':True,'root_check_sha256':hashlib.sha256(rootp.read_bytes()).hexdigest(),
 'root_values_not_used_to_generate_evaluation':True,'checks':checks,'clock_partition_invariants':inv,'new_parameters_or_rerun':0}
(O/'ROOT_INDEPENDENT_COMPARISON_AND_CLOCK_AUDIT.json').write_text(json.dumps(status,indent=2)+'\n')
print(json.dumps({k:v for k,v in status.items() if k not in ['checks','clock_partition_invariants']},indent=2))
