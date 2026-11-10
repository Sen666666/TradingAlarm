"""Freeze the completed R3 synthetic repair; no account progression."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
import json
from native_capital import SyntheticRunner
from imports_native import O,IO,sha,COMPOSITE,contract_guard
run=O/'runs/attempt-001';result=json.loads((run/'RESULTS.json').read_text());assert result['passed'] and result['tests']==35
parent=json.loads((O/'PARENT_BINDING.json').read_text());assert sha(parent['parent_adapter'])==parent['parent_sha256']=='61b9d133d592f6e0b2bb97ff0a2c8c811f7fca859f18f78b3862d4da2747d8b8'
contract_guard();binding=SyntheticRunner().binding()
for name in ('native_capital.py','policy.py','imports_native.py','native_exit_selected.py','test_native.py','test_revision.py','test_k_change.py','restore_check.py','restore_revision.py'):
 assert sha(O/name)==sha(run/'source'/name),'source changed since synthetic verification'
for p in (run/'checkpoints').glob('*.pkl'):SyntheticRunner.restore(p)
IO.write_json(O/'AUTHORIZATION.json',dict(parent_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',scope=parent['scope'],contract=COMPOSITE,historical_financial_events=0,production_edits=0,recorded_at=datetime.now(timezone.utc).isoformat(),record_timing='authorization transcribed after synthetic verification, not claimed to predate it'))
IO.write_json(O/'SOURCE_FREEZE.json',dict(contract=COMPOSITE,parent=parent,binding=binding,sources={p.name:sha(p) for p in sorted(O.glob('*.py'))},test_result=result,independent_audit='pending'))
bridges=[]
def check(v,path):
 if isinstance(v,dict):
  if 'independent_nav_difference' in v:
   for key in ('independent_nav_difference','cash_asset_difference','layer_cash_difference'):assert D(v[key])==0,(path,key,v[key])
   bridges.append(path)
  for k,x in v.items():check(x,path+'/'+k)
 elif isinstance(v,list):
  for i,x in enumerate(v):check(x,path+'/'+str(i))
for p in sorted(run.glob('[0-9][0-9]_*.json')):check(json.loads(p.read_text()),p.name)
IO.write_json(O/'VALIDATION_SUMMARY.json',dict(passed=True,tests=35,bridge_snapshots=len(bridges),bridge_paths=bridges,parent_unchanged=True,historical_financial_events=0,unsupported_features_fail_closed=['fractional lot/action attribution','multi-layer funding aggregate-fee planning','multi-order G fallback subset planning']))
paths=[p for p in O.glob('*.py')]+[O/n for n in ('PARENT_BINDING.json','AUDIT_ENTRY.md','AUTHORIZATION.json','SOURCE_FREEZE.json','VALIDATION_SUMMARY.json')]
paths += [p for p in run.rglob('*') if p.is_file()]+list((O/'inherited-independent-failures').glob('*.json'))
IO.write_json(O/'INPUT_OUTPUT_SHA256.json',dict(contract=COMPOSITE,inputs=binding['sources'],outputs={str(p.relative_to(O)):sha(p) for p in sorted(paths)},generated_source_inputs_bound_by=sha(O/'test_k_change.py')))
print(json.dumps(dict(adapter_sha256=sha(O/'native_capital.py'),source_freeze_sha256=sha(O/'SOURCE_FREEZE.json'),artifact_manifest_sha256=sha(O/'INPUT_OUTPUT_SHA256.json'),tests=35,bridge_snapshots=len(bridges),historical_financial_events=0),indent=2))
