from pathlib import Path
import sys,copy
from unittest.mock import patch
O=Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1/price_entry_generation_dynamic_v1');sys.path.insert(0,str(O))
import release as r
H='a'*64
code={n:H for n in r.REQUIRED_CODE};inputmap={'ORIGINAL_INPUT':H}
a=dict(explicit_root_authorized=True,scope=r.SCOPE,windows=['2022','2024'],authorization_evidence='FICTITIOUS_GUARD_TEST_ONLY',protocol_sha256=H,implementation_audit_sha256=H,code_sha256=code,input_sha256=inputmap)
review=dict(pre_economic_checks_passed=True,reviewed_code_sha256=code,reviewed_input_sha256=inputmap,market_tape_seal_sha256=H)
paths={str(O/'ROOT_ENTRY_GATE_AUTHORIZATION.json'):a,str(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json'):review,str(O/'FREEZE_CODE_SHA256.json'):code,str(O/'FREEZE_INPUT_SHA256.json'):inputmap,str(r.SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json'):{'input_sha256':inputmap},str(O/'market_tape/SEAL.json'):{'fixture.parquet':H},str(O/'TEST_QA.json'):{'passed':True}}
cases=[]
def trial(label,mutate=None,badhash=None,missing=False,oldfail=False):
 data=copy.deepcopy(paths)
 if mutate:mutate(data)
 def sh(p):return 'b'*64 if badhash is not None and str(p)==badhash else H
 with patch.object(Path,'exists',return_value=not missing),patch.object(r,'read',side_effect=lambda p:data[str(p)]),patch.object(r,'sha',side_effect=sh),patch.object(r,'verify_original',side_effect=AssertionError('OLD_DRIFT') if oldfail else None):
  try:r.require_release('2022')
  except (AssertionError,PermissionError):blocked=True
  else:blocked=False
 assert blocked==(label!='valid_synthetic_fixture'),label
 cases.append({'case':label,'blocked':blocked})
auth=str(O/'ROOT_ENTRY_GATE_AUTHORIZATION.json');aud=str(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json')
trial('valid_synthetic_fixture')
trial('missing_actual_authorization',missing=True)
trial('explicit_false',lambda d:d[auth].update(explicit_root_authorized=False))
trial('wrong_scope',lambda d:d[auth].update(scope='OTHER'))
trial('wrong_windows',lambda d:d[auth].update(windows=['2022']))
trial('empty_evidence',lambda d:d[auth].update(authorization_evidence=''))
trial('protocol_drift',badhash=str(O/'PROTOCOL.md'))
trial('audit_hash_drift',badhash=str(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json'))
trial('audit_not_pass',lambda d:d[aud].update(pre_economic_checks_passed=False))
trial('code_map_drift',lambda d:d[aud].update(reviewed_code_sha256={}))
trial('input_map_drift',lambda d:d[aud].update(reviewed_input_sha256={}))
trial('code_bytes_drift',badhash=str(O/'entry_gate.py'))
trial('input_bytes_drift',badhash='ORIGINAL_INPUT')
trial('missing_original_input',lambda d:d[str(r.SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json')].update(input_sha256={'ORIGINAL_INPUT':H,'MISSING_ORIGINAL':H}))
trial('tape_bytes_drift',badhash=str(O/'market_tape/fixture.parquet'))
trial('tape_seal_drift',badhash=str(O/'market_tape/SEAL.json'))
trial('tests_not_pass',lambda d:d[str(O/'TEST_QA.json')].update(passed=False))
trial('old_code_input_output_drift',oldfail=True)
assert not (O/'ROOT_ENTRY_GATE_AUTHORIZATION.json').exists() and not list(O.glob('ENTRY_GATE_RUN_ONCE_*.json'))
print('PASS_INDEPENDENT_RELEASE_GUARD_MATRIX',cases,'economic_calls=0, actual_authorization_files_created=0')

import json,hashlib
out=dict(status='PASS_INDEPENDENT_RELEASE_GUARD_MATRIX',cases=cases,economic_calls=0,actual_authorization_files_created=0,all_tests_in_memory_mocks_only=True,release_sha256=hashlib.sha256((O/'release.py').read_bytes()).hexdigest(),fixture_recovery='Earlier missing-original-input fixture reused the same dictionary for authorization and original plan; replaced the original-plan object to represent a genuine omission. Production code never changed.')
with (O/'independent_audit/RELEASE_GUARD_AUDIT.json').open('x') as f:json.dump(out,f,indent=2);f.write('\n')
