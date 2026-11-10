"""Summarize completed synthetic outputs; never execute accounts."""
from pathlib import Path
import json,hashlib
from decimal import Decimal
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
results={d:json.loads((ROOT/d/'RESULTS.json').read_text()) for d in ['audit-native','audit-regression-off','audit-regression-on']}
assert all(v['passed'] and not v['errors'] and not v['failures'] and v['historical_account_events']==0 for v in results.values())
expected='b447dcb43fa72e5d25ef79f15b21de3c8e5cd41ef64eee5fa86085f2418caeb7'
assert sha(ROOT/'native_risk.py')==expected
for d,r in results.items():
 if 'source' in r:assert r['source'][str(ROOT/'native_risk.py')]==expected
bridge=[];risk_states=0;fill_receipts=set()
for d in results:
 for p in (ROOT/d).rglob('*.json'):
  x=json.loads(p.read_text())
  if not isinstance(x,dict) or 'state' not in x:continue
  b=x['state']['account']['balance']
  for field in ['independent_nav_difference','cash_asset_difference','layer_cash_difference']:assert Decimal(b[field])==0,(p,field)
  bridge.append(str(p.relative_to(ROOT)))
  rb=x['state'].get('approved_risk',{})
  if rb.get('approvals'):risk_states+=1
  fill_receipts.update(rb.get('fills',{}))
old={}
prior=ROOT.parent/'g-s-C-approved-risk-execution-readonly-20261102'
for fn in ['SOURCE_READS.json','SOURCE_FUNCTION_HASHES.json']:
 for p,h in json.loads((prior/fn).read_text()).items():
  actual=sha(p);assert actual==h,('old source/data changed',p,h,actual);old[p]=actual
assert sha(prior/'ARTIFACT_SHA256.json')=='34447308ab7684e5a66226c953695cd7eb7ef4b18177b8c80a23112ef5d4ca39'
for d,r in results.items():
 if 'source' in r:
  for p,h in r['source'].items():
   if Path(p).is_absolute():assert sha(p)==h,('run source now changed',d,p)
summary=dict(scope='isolated native synthetic only; no historical financial event',adapter_sha256=expected,
 new_cases=results['audit-native']['tests'],unchanged_regressions_off=results['audit-regression-off']['tests'],unchanged_regressions_on=results['audit-regression-on']['tests'],
 assertions_are_not_independent_market_samples=True,financial_bridge_state_files=len(bridge),risk_observer_state_files=risk_states,
 full_suite_seconds={k:v['seconds'] for k,v in results.items()},
 original_files_verified_unchanged=old,prior_analysis_index=sha(prior/'ARTIFACT_SHA256.json'),
 native_price_scenarios=json.loads((ROOT/'audit-native/03_PRICE_SCENARIOS.json').read_text()),
 historical_saved_row_arithmetic=json.loads((ROOT/'audit-native/15_saved_arithmetic.json').read_text()),
 native_state_files=bridge,created_at=datetime.now(timezone.utc).isoformat())
(ROOT/'VERIFICATION.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k not in ['original_files_verified_unchanged','native_price_scenarios','native_state_files']},ensure_ascii=False))
