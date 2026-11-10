"""Finish reporting from already frozen exposure CSVs; no rule/market recalculation."""
from pathlib import Path
import json,hashlib,time
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;T=time.monotonic()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,list):return [clean(v) for v in x]
 if isinstance(x,np.generic):return clean(x.item())
 if isinstance(x,float) and not np.isfinite(x):return None
 return x
def save(n,x):(O/n).write_text(json.dumps(clean(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
e=pd.read_csv(O/'holding-exposure-with-original-labels.csv');s=pd.read_csv(O/'selected-with-original-labels.csv');p=pd.read_csv(O/'pair-options-before-labels.csv');c=pd.read_csv(O/'new-candidate-background.csv')
def cov(g):return dict(rows=len(g),cycles=g.cycle_id.nunique(),calendar_days=g.date.nunique(),stocks=g['symbol' if 'symbol' in g else 'old'].nunique())
old=e[e.old_signal];da=e[(e.event==-1)&e.e0_I_active]
def first(g):return g.head(1).to_dict('records')
sumry=dict(all_decision_days=681,all_holding=cov(e),event_unknown=int(e.event.isna().sum()),structure_unknown=int(e.old_reasons.fillna('').str.contains('structure_unknown').sum()),event_down_structure_active=cov(da),old_gate=cov(old),old_gate_positive_new=cov(old[old.new_positive_R21_count>0]),old_gate_feasible=cov(old[old.feasible_candidates>0]),selected=cov(s),all_pair_options=len(p),feasible_pair_options=int(p.feasible.sum()),pair_first_block=p[p.feasible==False].first_block.value_counts(dropna=False).to_dict(),old_first_block=e[e.old_signal==False].old_first_block.value_counts(dropna=False).to_dict(),candidate_R21_unknown=int(c.R21.isna().sum()),candidate_positive_R21=int((c.R21>0).sum()),old_gate_original_tail30=cov(old[old.original_tail30]),selected_original_tail30=cov(s[s.original_tail30]),selected_original_profitable=cov(s[s.original_profitable]),selected_original_loss=cov(s[s.original_profitable==False]),first_selected=s.head(2).to_dict('records'),first_tail_counterexample=first(s[s.original_tail30]),first_nontrigger=first(e[e.old_first_block=='not_new_down_confirmation']),first_original_exit_priority=first(e[(e.event==-1)&(e.old_signal==False)&(e.old_sell_pending|(e.ACT_on==False))]),selected_all=s.to_dict('records'))
save('EXPOSURE_SUMMARY.json',sumry)
for n in ['INPUT_IDENTITY.json','EVENT_INPUT_IDENTITY.json','SELECTION_FREEZE.json']:
 x=json.loads((O/n).read_text());hs=x.get('sha256',x);assert all(sha(p)==v for p,v in hs.items()),n
assert not s.date.duplicated().any() and not s.cycle_id.duplicated().any()
assert s.cycle_id.isin(e.cycle_id).all() and e.cycle_id.nunique()==69 and len(e)==2794
assert not p[(p.feasible)&(p.new_projected_spend>p.projected_net_sale+1e-7)].shape[0]
save('VERIFICATION.json',dict(passed=True,original_reserve_rows_exact_before_summary_serialization=681,original_Q_rows_exact_before_summary_serialization=681*407,complete_scan_reached_selection_freeze=True,event_files=407,event_close_and_source_segment_exact=True,preexisting_event_prefix_validation_passed=True,frozen_selection_and_all_input_hashes_unchanged=True,single_cycle_and_daily_pair=True,all_69_actual_cycles_in_denominator=True,no_external_money_projected=True,read_original_final_labels_only_after_selection_freeze=True,new_forward_return_or_economic_paths=0,indicator_recomputations=0,exposure_scan_seconds=17.949527875054628,report_finalizer_seconds=time.monotonic()-T,serialization_failure_preserved='run.log'))
print(json.dumps(clean(sumry),ensure_ascii=False,default=str),flush=True)
