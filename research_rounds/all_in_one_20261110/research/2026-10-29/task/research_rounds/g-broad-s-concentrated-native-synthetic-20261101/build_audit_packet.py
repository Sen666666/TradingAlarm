"""Read completed synthetic outputs; freeze provenance. No account events."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
import json
from native_capital import SyntheticRunner,encode
from imports_native import O,IO,sha,COMPOSITE,contract_guard

run=O/'runs'/'final-010'
result=json.loads((run/'RESULTS.json').read_text());assert result['passed'] and result['tests']==21
binding=SyntheticRunner().binding();contract_guard()
for name in ('native_capital.py','policy.py','imports_native.py','test_native.py','restore_check.py'):
 assert sha(O/name)==sha(run/'source'/name),'source changed after final tests'
for cp in sorted((run/'checkpoints').glob('*.pkl')):
 restored=SyntheticRunner.restore(cp);assert restored.binding()==binding

scope=dict(parent_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',contract=COMPOSITE,
 authorization='latest explicit V2 minimum isolated native synthetic implementation, eight specified scenarios',
 allowed=['generated-price synthetic policy/native lifecycle tests','isolated source files','source/output hashes and independent-audit packet'],
 excluded=['historical economic account paths','production changes','services','live/broker/cron','new market indicators','F1 changes'],
 actual_historical_paths=0,recorded_at=datetime.now(timezone.utc).isoformat(),
 timing='authorization transcribed after synthetic implementation and final tests; no claim this file predates those tests')
IO.write_json(O/'AUTHORIZATION.json',scope)
IO.write_json(O/'SOURCE_FREEZE.json',dict(created_at=datetime.now(timezone.utc).isoformat(),frozen_after_local_synthetic_tests=True,
 binding=binding,new_source_files={p.name:sha(p) for p in sorted(O.glob('*.py'))},local_result=result,independent_review_status='pending'))

cases={p.stem:json.loads(p.read_text()) for p in sorted(run.glob('[0-9][0-9]_*.json'))}
bridges=[]
def walk(value,path):
 if isinstance(value,dict):
  if 'independent_nav_difference' in value:
   for key in ('independent_nav_difference','cash_asset_difference','layer_cash_difference'):assert Decimal(value[key])==0,(path,key,value[key])
   bridges.append(path)
  for k,v in value.items():walk(v,path+'/'+k)
 elif isinstance(value,list):
  for i,v in enumerate(value):walk(v,path+'/'+str(i))
for k,v in cases.items():walk(v,k)
a=cases['01_G90_common_prefix'];b=cases['02_S80_reallocation'];c=cases['06_ACT_once'];d=cases['17_hold_support_not_buy_permit']
summary=dict(tests=21,failures=0,errors=0,historical_paths=0,bridged_state_snapshots=len(bridges),bridge_paths=bridges,
 G_actual_exposure=a['initial_exposure'],G_false_start_actual_loss=a['actual_false_start_loss'],
 S_actual_exposure=b['S_exposure'],B_actual_capital_before_old_exit_fill=b['actual_B_when_old_exits_not_filled'],
 cash_before_sell=b['cash_before_sell'],cash_after_real_settlement=b['cash_after_settlement'],
 B_after_settlement_capital=b['post_settle_B_capital'],B_after_settlement_NAV=b['post_settle_NAV'],
 failed_B_actual_closed_net=b['actual_new_B_closed_net'],old_A_foregone_price_gain_only=b['foregone_A_price_gain_only'],
 old_A_actual_shares_sold=b['sold_valid_A_quantity'],ACT_first_phase_peak=c['later_unlock_phase_peak'],
 ACT_later_NAV=c['later_NAV'],ACT_later_DD=c['later_phase_DD'],S_failed_G_A_true_actual_retained_capital=d['actual_retained_inventory'],
 native_split_failure_preserved='failures/ORIGINAL_PARTIAL_EXIT_SPLIT_REPRO.json',
 independent_review='pending; no historical runner promotion',coverage_entry='AUDIT_ENTRY.md')
IO.write_json(O/'SYNTHETIC_SUMMARY.json',summary)

inputs=dict(binding['sources']);inputs.update({str(p):sha(p) for p in sorted(O.glob('*.py'))})
outputs=[p for p in run.rglob('*') if p.is_file()]
outputs += [O/n for n in ('AUDIT_ENTRY.md','AUTHORIZATION.json','SOURCE_FREEZE.json','SYNTHETIC_SUMMARY.json')]
outputs += [p for p in (O/'failures').rglob('*') if p.is_file()]
IO.write_json(O/'INPUT_OUTPUT_SHA256.json',dict(contract=COMPOSITE,inputs=inputs,outputs={str(p.relative_to(O)):sha(p) for p in sorted(outputs)},
 fixture_inputs='deterministic generated values and exact dated calendar/fee/quantity rules, all bound by source SHA; no historical price/account input loaded',
 unchanged_original_inputs_rechecked=all(sha(p)==s for p,s in binding['sources'].items())))
print(json.dumps(dict(summary=summary,hashes={n:sha(O/n) for n in ('native_capital.py','policy.py','test_native.py','SOURCE_FREEZE.json','INPUT_OUTPUT_SHA256.json','SYNTHETIC_SUMMARY.json','AUDIT_ENTRY.md')}),ensure_ascii=False,indent=2))
