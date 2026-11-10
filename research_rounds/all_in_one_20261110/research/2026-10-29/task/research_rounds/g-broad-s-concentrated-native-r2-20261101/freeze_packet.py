"""Read completed R2 synthetic evidence and freeze hashes; no account events."""
from pathlib import Path
from datetime import datetime,timezone
import json
from decimal import Decimal as D
from native_capital import SyntheticRunner,SELECTED
from imports_native import O,IO,sha,COMPOSITE,contract_guard

run=O/'runs/final-005';result=json.loads((run/'RESULTS.json').read_text());assert result['passed'] and result['tests']==31
parent=json.loads((O/'PARENT_BINDING.json').read_text());assert sha(parent['parent_adapter'])==parent['parent_sha256']=='403da82de9fe6f1bac4ecfa86fe81142792d4098385ed4eba6a3178f64d21c09'
contract_guard();r=SyntheticRunner();binding=r.binding()
for name in ('native_capital.py','native_exit_selected.py','policy.py','imports_native.py','test_native.py','test_revision.py','restore_check.py','restore_revision.py'):
 assert sha(O/name)==sha(run/'source'/name),'source changed after final synthetic tests'
for p in (run/'checkpoints').glob('*.pkl'):SyntheticRunner.restore(p)
IO.write_json(O/'NATIVE_EXIT_SELECTION_SEAMS.json',dict(SELECTED.manifest(),original_source=SELECTED.ORIGINAL,selected_source=SELECTED.TRANSFORMED))
auth=dict(parent_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',contract=COMPOSITE,scope='R2 three independent counterexample repairs plus minimal synthetic close/batch/mapping/restart wiring',historical_paths=0,live_actions=0,production_edits=0,
 recorded_at=datetime.now(timezone.utc).isoformat(),record_timing='transcribed after authorized synthetic implementation and tests; not asserted to predate tests')
IO.write_json(O/'AUTHORIZATION.json',auth)
IO.write_json(O/'SOURCE_FREEZE.json',dict(parent=parent,contract=COMPOSITE,binding=binding,sources={p.name:sha(p) for p in sorted(O.glob('*.py'))},test_result=result,independent_review='pending'))
bridges=[]
def check(v,path):
 if isinstance(v,dict):
  if 'independent_nav_difference' in v:
   for k in ('independent_nav_difference','cash_asset_difference','layer_cash_difference'):assert D(v[k])==0,(path,k,v[k])
   bridges.append(path)
  for k,x in v.items():check(x,path+'/'+k)
 elif isinstance(v,list):
  for i,x in enumerate(v):check(x,path+'/'+str(i))
for p in sorted(run.glob('[0-9][0-9]_*.json')):check(json.loads(p.read_text()),p.name)
IO.write_json(O/'VALIDATION_SUMMARY.json',dict(passed=True,tests=31,historical_paths=0,bridge_snapshots=len(bridges),bridge_paths=bridges,parent_adapter_unchanged=True,source_step_kernel_unchanged=True,
 adverse_cases=['ACT partial union filled to999','fractional exit before-mutation rejection','selected mobile cannot borrow core sellability'],
 failure_history_preserved='runs/lifecycle-003',remaining=['fractional action attribution unsupported and rejected','multi-layer G funding plan fee apportionment unsupported and rejected','multiorder G downgrade subset planning not complete','historical loaders/policy switch importer not implemented']))
paths=[p for p in O.glob('*.py')]+[O/n for n in ('PARENT_BINDING.json','AUDIT_ENTRY.md','NATIVE_EXIT_SELECTION_SEAMS.json','AUTHORIZATION.json','SOURCE_FREEZE.json','VALIDATION_SUMMARY.json')]
paths += [p for p in run.rglob('*') if p.is_file()]+[p for p in (O/'inherited-independent-failures').glob('*.json')]
IO.write_json(O/'INPUT_OUTPUT_SHA256.json',dict(inputs=binding['sources'],outputs={str(p.relative_to(O)):sha(p) for p in sorted(paths)},contract=COMPOSITE,generated_inputs_bound_by_test_source_sha256=sha(O/'test_revision.py')))
print(json.dumps(dict(adapter_sha256=sha(O/'native_capital.py'),source_freeze_sha256=sha(O/'SOURCE_FREEZE.json'),artifact_manifest_sha256=sha(O/'INPUT_OUTPUT_SHA256.json'),tests=31,bridge_snapshots=len(bridges),historical_paths=0),indent=2))
