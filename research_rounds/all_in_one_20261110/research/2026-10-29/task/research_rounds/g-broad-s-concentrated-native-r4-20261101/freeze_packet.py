"""Read completed R4 synthetic evidence and freeze hashes; no account events."""
from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal as D
from collections import defaultdict
import json
from native_capital import SyntheticRunner
from imports_native import O,IO,sha,COMPOSITE,contract_guard
run=O/'runs/final-004';result=json.loads((run/'RESULTS.json').read_text());assert result['passed'] and result['tests']==42
parent=json.loads((O/'PARENT_BINDING.json').read_text());assert sha(parent['parent_adapter'])==parent['parent_sha256']=='9b2f8f238ae60cc46564493c01c05320b418161e252036a5917b9d603be6c58e'
contract_guard();binding=SyntheticRunner().binding()
for name in ('native_capital.py','funding_coverage.py','policy.py','imports_native.py','native_exit_selected.py','test_native.py','test_revision.py','test_k_change.py','test_funding.py','restore_check.py','restore_revision.py'):
 assert sha(O/name)==sha(run/'source'/name),'source changed after synthetic verification'
for p in (run/'checkpoints').glob('*.pkl'):SyntheticRunner.restore(p)
IO.write_json(O/'AUTHORIZATION.json',dict(parent_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',scope=parent['scope'],contract=COMPOSITE,historical_financial_events=0,production_edits=0,recorded_at=datetime.now(timezone.utc).isoformat(),record_timing='transcribed after authorized synthetic work, not asserted to predate tests'))
IO.write_json(O/'SOURCE_FREEZE.json',dict(contract=COMPOSITE,parent=parent,binding=binding,sources={p.name:sha(p) for p in sorted(O.glob('*.py'))},test_result=result,independent_review='pending'))
bridges=[];covers=[]
def check(v,path):
 if isinstance(v,dict):
  if 'independent_nav_difference' in v:
   for k in ('independent_nav_difference','cash_asset_difference','layer_cash_difference'):assert D(v[k])==0,(path,k,v[k])
   bridges.append(path)
  if all(k in v for k in ('assets','allocations','covered','uncovered','raw_cash_need')):
   values={x['asset']:D(x['amount']) for x in v['assets']};assert len(values)==len(v['assets']);used=defaultdict(lambda:D(0))
   for x in v['allocations']:used[x['asset']]+=D(x['amount'])
   assert all(n<=values[k] for k,n in used.items());assert sum(used.values(),D(0))==D(v['covered']);assert D(v['raw_cash_need'])==D(v['covered'])+D(v['uncovered']);covers.append(path)
  for k,x in v.items():check(x,path+'/'+k)
 elif isinstance(v,list):
  for i,x in enumerate(v):check(x,path+'/'+str(i))
for p in sorted(run.glob('[0-9][0-9]_*.json')):check(json.loads(p.read_text()),p.name)
IO.write_json(O/'VALIDATION_SUMMARY.json',dict(passed=True,tests=42,bridge_snapshots=len(bridges),bridge_paths=bridges,coverage_snapshots_checked=len(covers),coverage_not_reused_within_each_snapshot=True,coverage_snapshots_are_not_independent_samples=True,parent_unchanged=True,historical_financial_events=0,
 limitations=['fractional actions rejected','multi-layer financing fee aggregation rejected','multi-order G fallback subset rejected','mandatory/funding-cancel accepted-ACK race rejected','historical loader not implemented']))
paths=[p for p in O.glob('*.py')]+[O/n for n in ('PARENT_BINDING.json','AUDIT_ENTRY.md','AUTHORIZATION.json','SOURCE_FREEZE.json','VALIDATION_SUMMARY.json')]
paths += [p for p in run.rglob('*') if p.is_file()]+list((O/'inherited-independent-failures').glob('*.json'))
IO.write_json(O/'INPUT_OUTPUT_SHA256.json',dict(contract=COMPOSITE,inputs=binding['sources'],outputs={str(p.relative_to(O)):sha(p) for p in sorted(paths)},generated_inputs_bound_by=sha(O/'test_funding.py')))
print(json.dumps(dict(adapter_sha256=sha(O/'native_capital.py'),funding_book_sha256=sha(O/'funding_coverage.py'),source_freeze_sha256=sha(O/'SOURCE_FREEZE.json'),artifact_manifest_sha256=sha(O/'INPUT_OUTPUT_SHA256.json'),tests=42,bridge_snapshots=len(bridges),coverage_snapshots_checked=len(covers),historical_financial_events=0),indent=2))
