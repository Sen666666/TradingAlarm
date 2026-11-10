"""Reporting-only timing clarification; no market, size, strategy, or account rerun."""
from pathlib import Path
import json,hashlib
import pandas as pd,numpy as np
O=Path(__file__).resolve().parent
H=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str,allow_nan=False)+'\n')
assert not (O/'OLD_OUTCOME_EXIT_CLOCK.csv').exists()
paths=[O/'DAILY_OVERLAP.parquet',O/'RECEIPT_CONDITIONAL_OVERLAP.parquet',O/'OLD_OUTCOME_SURVIVAL_AND_COMPETITION.csv',H,Path(__file__)]
src={str(p):sha(p) for p in paths}
x=pd.read_parquet(paths[0],columns=['window','sid','day','root_day','receipt','active','failed','root_unknown','valid'])
r=pd.read_parquet(paths[1]);z=pd.read_csv(paths[2],low_memory=False)
for c in ['old_signal_day','old_entry_day','old_exit_day','new_root_at_old_signal']:z[c]=pd.to_datetime(z[c],format='mixed')
with np.load(H,allow_pickle=False) as h:cal=pd.DatetimeIndex(h['dates'])
ci={d:i for i,d in enumerate(cal)};groups={k:g for k,g in x.groupby(['window','sid'])};rg={k:g for k,g in r.groupby(['window','sid'])};out=[]
for q in z.to_dict('records'):
 g=groups[(q['window'],q['sid'])];v=g[(g.day>=q['old_signal_day'])&(g.day<q['old_exit_day'])]
 rec=rg.get((q['window'],q['sid']),r.iloc[0:0]);rec=rec[(rec.day>=q['old_signal_day'])&(rec.day<q['old_exit_day'])]
 sr=v[v.root_day.eq(q['new_root_at_old_signal'])];end=sr[sr.failed|sr.root_unknown].sort_values('day')
 first=end.iloc[0] if len(end) else None
 q['first_original_price_root_fail_day']=first.day if first is not None and first.failed else pd.NaT
 q['first_original_price_root_unknown_day']=first.day if first is not None and first.root_unknown else pd.NaT
 sale=cal[ci[first.day]+1] if first is not None and first.failed and ci[first.day]+1<len(cal) else pd.NaT
 q['first_next_common_open_after_root_price_fail']=sale
 q['market_exit_clock_vs_old_exit']='NO_ACTIVE_PRICE_ROOT_AT_OLD_SIGNAL' if not q['new_price_active_at_old_signal'] else 'UNKNOWN_SOURCE_OR_PRICE_BOUNDARY' if first is not None and first.root_unknown else 'SAME_OPEN_AS_OLD_EXIT' if pd.notna(sale) and sale==q['old_exit_day'] else 'EARLIER_OPEN_THAN_OLD_EXIT' if pd.notna(sale) and sale<q['old_exit_day'] else 'LATER_OPEN_THAN_OLD_EXIT' if pd.notna(sale) else 'WINDOW_CENSORED' if q['root_survival_status']=='CENSORED_AT_FIXED_WINDOW_END' else 'NO_FAILURE_BEFORE_OLD_EXIT'
 q['first_new_receipt_in_observed_old_hold']=rec.day.min() if len(rec) else pd.NaT
 q['first_close_size_feasible_new_receipt_in_observed_old_hold']=rec.loc[rec.conditional_unstarted_target_feasible,'day'].min()
 q['any_new_receipt_in_observed_old_hold']=bool(len(rec));q['any_close_size_feasible_new_receipt_in_observed_old_hold']=bool(rec.conditional_unstarted_target_feasible.any())
 q['market_exit_clock_is_actual_new_sale']=False
 out.append(q)
y=pd.DataFrame(out);y.to_csv(O/'OLD_OUTCOME_EXIT_CLOCK.csv',index=False)
summary=[]
for (w,c),g in y.groupby(['window','old_outcome_group']):
 row=dict(window=w,old_outcome_group=c,old_rounds=len(g),any_new_receipt_in_observed_old_hold=int(g.any_new_receipt_in_observed_old_hold.sum()),any_close_size_feasible_new_receipt_in_observed_old_hold=int(g.any_close_size_feasible_new_receipt_in_observed_old_hold.sum()),full_old_hold_visible=int(g.root_survival_observation_scope.eq('FULL_OLD_HOLDING_CLOSE_PATH').sum()))
 for k in ['NO_ACTIVE_PRICE_ROOT_AT_OLD_SIGNAL','UNKNOWN_SOURCE_OR_PRICE_BOUNDARY','SAME_OPEN_AS_OLD_EXIT','EARLIER_OPEN_THAN_OLD_EXIT','LATER_OPEN_THAN_OLD_EXIT','WINDOW_CENSORED','NO_FAILURE_BEFORE_OLD_EXIT']:row[k]=int(g.market_exit_clock_vs_old_exit.eq(k).sum())
 summary.append(row)
s=pd.DataFrame(summary);s.to_csv(O/'OLD_OUTCOME_EXIT_CLOCK_SUMMARY.csv',index=False)
# The primary flat reference is A_UNION_B. 2022 also has a separately executed fast arm.
# Neither historical reference proves the new path is actually flat.
dual=[]
for w,g in r.groupby('window'):
 for stage,h in [('BIRTH',g[g.born]),('ALL_FRONTIER_RECEIPTS',g)]:
  known=h.old_fast_AB_FAST_SMALL_covered
  unique=h.conditional_unique_market_unstarted_candidate
  both=unique&h.old_fast_state_after_old_admission.eq('knownFLAT')
  dual.append(dict(window=w,stage=stage,receipt_stockdays=len(h),old_AB_flat_unique_market_candidates=int(unique.sum()),old_fast_scenario_state_coverage_known=int(known.sum()),both_old_AB_and_fast_flat_unique_market_candidates=int(both.sum()) if bool(known.all()) else None,AB_flat_unique_but_old_fast_held=int((unique&h.old_fast_state_after_old_admission.eq('HELD')).sum()) if bool(known.all()) else None,AB_flat_unique_but_old_fast_pending=int((unique&h.old_fast_state_after_old_admission.eq('PENDING')).sum()) if bool(known.all()) else None,AB_flat_unique_but_old_fast_unknown=int((unique&h.old_fast_state_after_old_admission.eq('UNKNOWN')).sum()) if bool(known.all()) else None,actual_new_empty_position='UNKNOWN_NOT_SIMULATED'))
pd.DataFrame(dual).to_csv(O/'DUAL_OLD_REFERENCE_FLAT_SUMMARY.csv',index=False)
for p,h in src.items():assert sha(p)==h
save(O/'REPORTING_CLOCK_QA.json',dict(passed=True,source_hashes=src,old_report_unchanged=True,new_market_runs=0,new_size_runs=0,new_account_runs=0,scope='Clock alignment prevents a protection breach on the close immediately before the original exit from being called an earlier loss of the path. It does not prove new participation, execution, return, or displacement. Strict active-root survival remains separately recorded.'))
print(s.to_string(index=False));print(pd.DataFrame(dual).to_string(index=False))
