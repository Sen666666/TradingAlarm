from pathlib import Path
from collections import Counter
from decimal import Decimal as D
import json,csv,hashlib
O=Path(__file__).parent
load=lambda n:json.loads((O/n).read_text())
def save(n,x):
 (O/('GATE_'+n+'.json')).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str))
 if isinstance(x,list) and x:
  with (O/('GATE_'+n+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in x for k in r)));w.writeheader();w.writerows(x)
old=load('GATE_PRE_REVIEW_SNAPSHOT.json');actual=load('GATE_ACTUAL_ENTRY_ROWS.json');timing=load('GATE_WAIT_TIMING_FOCUS.json');allrows=load('FILLED_SEED_CLASSIFICATION.json');lookup={r['round_id']:r for r in actual}
compared=['gate_status','CP_state','CP_receipt_day','CP_floor','actual_next_OPEN_gate_pass','gate_via','actual_next_OPEN_check']
changes=[]
for a,b in zip(old['GATE_ACTUAL_ENTRY_ROWS.json'],actual):
 assert a['round_id']==b['round_id']
 for k in compared:
  if a[k]!=b[k]:changes.append(dict(round_id=a['round_id'],field=k,old=a[k],new=b[k]))
timing_fields=['first_G_true_CLOSE','first_reclassified_RESIDUAL_CLOSE','first_original_false_cancellation','blocked_day','first_quote_I_source_and_gate_eligible_OPEN']
timing_changes=[];nt={r['round_id']:r for r in timing}
for a in old['GATE_WAIT_TIMING_FOCUS.json']:
 b=nt[a['round_id']]
 for k in timing_fields:
  if a[k]!=b[k]:timing_changes.append(dict(round_id=a['round_id'],field=k,old=a[k],new=b[k]))
prior=load('STRUCTURE_PRIOR_OUTPUT_SEAL.json');original49={n:hashlib.sha256((O/n).read_bytes()).hexdigest()==h for n,h in prior.items()}
coverage=load('GATE_INPUT_COVERAGE.json');cover_next=dict(sum((Counter(r['input_audit_actual_next_OPEN']) for r in actual),Counter()));cover_wait=dict(sum((Counter(r['input_audit_through_cancel']) for r in timing),Counter()))
qa=dict(formula_changed=False,original49_count=len(prior),original49_unchanged=all(original49.values()),actual_rows_checked=len(actual),actual_fields_compared=compared,actual_differences=changes,waiting_rows_checked=len(old['GATE_WAIT_TIMING_FOCUS.json']),waiting_fields_compared=timing_fields,waiting_differences=timing_changes,signal_through_plan_input_coverage=coverage,next_OPEN_PASS_input_coverage=cover_next,waiting_through_cancel_input_coverage=cover_wait,unknown_receipt_source_factor_Iline_or_quote_inputs_hit=sum(v for a in [coverage["audit"],cover_next,cover_wait] for k,v in a.items() if k not in ["CLOSE_visits","OPEN_visits","CLOSE_original_state_unknown"]),waiting_original_state_unknown_note='Four visits include sector UNKNOWN in the continued hypothetical waiting path; original known false still cancels. CP/source/factor/receipt/I-floor quote boundary issue counts are zero. These are not all original states known.',synthetic_check_count=len(load('GATE_SYNTHETIC_QA.json')['checks']),synthetic_result=load('GATE_SYNTHETIC_QA.json')['result'],diagnostic_source_sha256=hashlib.sha256((O/'GATE_diagnose.py').read_bytes()).hexdigest(),CP_identity_changed_only_by_binding_actual_model_and_ENTRY_CP_namespace=True)
assert not changes and not timing_changes and all(original49.values())
save('REVIEW_EQUIVALENCE_QA',qa)
# Fixed actual-OPEN opportunity sets chosen before this result, all baseline seed rounds.
cohorts={'STARTUP_OPEN_0923_0930':[r for r in allrows if '2024-09-23'<=r['seed_day']<='2024-09-30'], 'PV_OPEN_1023_1029':[r for r in allrows if '2024-10-23'<=r['seed_day']<='2024-10-29' and r['sector51']=='光伏风电设备']}
fixed=[];detail=[]
for label,rs in cohorts.items():
 for r in rs:
  g=lookup.get(r['round_id']);status=g['gate_status'] if g else 'UNMODIFIED_'+r['phase']
  detail.append(dict(cohort=label,round_id=r['round_id'],sid=r['sid'],name=r['name'],sector51=r['sector51'],signal_CLOSE=r['signal_day'],plan_CLOSE=r['plan_day'],actual_OPEN=r['seed_day'],original_phase=r['phase'],status=status,CP_receipt_day=g['CP_receipt_day'] if g else None,CP_floor=g['CP_floor'] if g else None,original_net=r['net'],original_seed_cost=r['seed_cost'],original_final_qty=r['final_qty'],actual_next_OPEN_gate_pass=g['actual_next_OPEN_gate_pass'] if g else None))
 for status in sorted({r['status'] for r in detail if r['cohort']==label}):
  for state in ['ALL','CLOSED','OPEN']:
   a=[r for r in detail if r['cohort']==label and r['status']==status and (state=='ALL' or (not r['original_final_qty'])==(state=='CLOSED'))]
   fixed.append(dict(cohort=label,status=status,state=state,n=len(a),original_net=sum((D(r['original_net']) for r in a),D(0)),original_seed_cost=sum((D(r['original_seed_cost']) for r in a),D(0))))
save('FIXED_OPPORTUNITY_ROWS',detail);save('FIXED_OPPORTUNITY_SUMMARY',fixed)
# Preserve known names regardless of their outcome, including unaffected EVENT entries.
focusnames={'常山北明','拓维信息','银之杰','聚和材料','禾望电气','协鑫集成','钧达股份','爱旭股份','新强联'}
focus=[]
for r in allrows:
 if r['name'] not in focusnames:continue
 g=lookup.get(r['round_id']);focus.append(dict(**r,gate_status=g['gate_status'] if g else 'UNMODIFIED_'+r['phase'],CP_receipt_day=g['CP_receipt_day'] if g else None,CP_floor=g['CP_floor'] if g else None,CP_state=g['CP_state'] if g else None,gate_via=g['gate_via'] if g else None,actual_next_OPEN_gate_pass=g['actual_next_OPEN_gate_pass'] if g else None))
save('NAMED_MAINLINE_ROWS',focus)
print(json.dumps(dict(review=qa,fixed=[r for r in fixed if r['state']=='ALL'],named=focus),ensure_ascii=False,default=str))
