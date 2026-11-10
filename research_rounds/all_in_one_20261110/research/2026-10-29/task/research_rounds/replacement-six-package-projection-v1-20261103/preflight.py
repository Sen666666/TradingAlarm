"""Original-plan arithmetic identity and all-edge matching degeneration."""
from pathlib import Path
import sys,json,copy,hashlib,traceback
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O));import extract as X
from matching import witness, self_test
J=X.J;B=X.B
def main():
 freeze=X.read(O/'CONTRACT_FREEZE.json');assert X.sha(O/'CONTRACT.txt')==freeze['contract_sha256'];assert X.sha(O/'matching.py')==freeze['matching_source_sha256']
 manifest=X.read(O/'INPUT_MANIFEST.json');assert X.sha(O/'INPUT_MANIFEST.json')==freeze['input_manifest_sha256'];results=[]
 for c in manifest['cases']:
  p=O/c['input'];assert X.sha(p)==manifest['inputs_sha256'][c['input']];x=X.read(p)
  ordered=sorted(x['demands'],key=lambda d:(d['priority'],d['sid']))
  r=X.add_budget_guard(x,B.evaluate(x['snapshot'],ordered,x['certificate']['Q'],x['original_D']))
  assert J.digest(r['validation'])==J.digest(x['original_result']['validation']),'original full guard arithmetic differs'
  assert J.digest(r['donors'])==J.digest(x['original_result']['donors']),'original designated donor arithmetic differs'
  assert J.digest(x['original_result'])==x['certificate']['projection_hash']
  # Same persistent budget, no new book; result is a PURE proposal.
  v=x['trusted'];book=X.budget_book(x)
  book.approve(book.batch['id']+'|complete_target_plan',{str(p['layer']):p['q'] for p in r['donors']['rows']},target_binding=J.digest(dict(Q=x['certificate']['Q'],receipts=[d['receipt_id'] for d in v['demands']])))
  assert book.dumps()==x['original_result']['budget_after'],'original C10/C20 budget arithmetic differs'
  ok,w=witness(J,x['snapshot'],ordered,x['certificate']['Q'],r['donors'],r['validation'],x['scores'],'ALL',True)
  X.save(O/('OFF-'+c['arm']+'-'+c['day']+'.json'),dict(original_Q=x['certificate']['Q'],original_D=x['original_D'],native=r,matching=w,original_plan_identity=True,
   budget_after_exact=True,original_full_projection_digest_checked=True,selector_search_rerun=False,financial_events=0))
  if not ok:raise ValueError(('all-edge resource degeneration failed',c['input'],w))
  results.append(dict(case=x['case'],arm=x['arm'],day=x['day'],passed=True,resource_states=w['checked_resource_states']))
  print('OFF_NATIVE_AND_ALL_EDGE_EXACT',c['arm'],c['day'],w['checked_resource_states'],flush=True)
 X.save(O/'PREFLIGHT.json',dict(passed=True,cases=results,matching_cases=len(self_test()),financial_events=0,contract_sha256=X.sha(O/'CONTRACT.txt')))
if __name__=='__main__':
 try:main()
 except BaseException as e:X.save(O/'PREFLIGHT_ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),financial_events=0));raise
