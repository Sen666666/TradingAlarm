"""One additional frozen package using the unchanged six-package engine."""
from pathlib import Path
import sys,json,gzip,pickle,hashlib,time,traceback
O=Path(__file__).resolve().parent;R=O.parent;FROZEN=R/'replacement-six-package-projection-v1-20261103'
sys.path.insert(0,str(FROZEN));import project as P
X=P.X;J=P.J;B=P.B
SOURCES={}
def read(p):p=Path(p);SOURCES[str(p.resolve())]=X.sha(p);return json.loads(p.read_text())
def main():
 fm=read(FROZEN/'DELIVERABLE_MANIFEST.json');f=read(FROZEN/'CONTRACT_FREEZE.json')
 for name in ['project.py','matching.py','extract.py','CONTRACT.txt']:
  p=FROZEN/name;assert X.sha(p)==fm['files_sha256'][name];SOURCES[str(p.resolve())]=X.sha(p)
 cp=R/'g-s-C-August-continuation-v1-20261102/runs/C10/2025-08-15-CLOSE.pkl.gz'
 prov=read(cp.with_name('2025-08-15-CLOSE.provenance.json'));payload=gzip.decompress(cp.read_bytes());SOURCES[str(cp.resolve())]=X.sha(cp)
 assert hashlib.sha256(payload).hexdigest()==prov['checkpoint_sha256']
 for p,h in prov['binding']['source'].items():assert X.sha(p)==h
 obj=pickle.loads(payload);c=obj.active;assert c['certificate_id']=='6b5bef52cbbdaa48c486c9c1091d356c51932af85b33930d465450325b913ef6'
 v=obj.trusted[c['trusted_id']];row=next(z for z in obj.results if z['certificate']['certificate_id']==c['certificate_id'])
 assert J.digest(dict(s=v['snapshot'],ds=v['demands'],e=v['evidence'],bb=v['budget_before']))==c['trusted_id']
 assert J.digest(v['snapshot'])==c['snapshot_hash'] and J.digest(row['projection'])==c['projection_hash']
 ss,dd,rank=X.C.transform(v['snapshot'],v['demands'],v['evidence'])
 table=read(R/'replacement-aug18-design-v1-20261102/THREE_BATCHES.json')[0]
 assert table['certificate']==c['certificate_id'] and table['original_Q']==c['Q'] and table['original_D']==c['D']
 scores={z['sid']:dict(PVR=z['PVR'],stock_H1=z['stock_H1'],I_target=z['I_target'],G1_grade=z['G1_grade'],CP1_market_receipt=z['CP1_market_fresh'],name=z['name']) for z in table['rows']}
 assert set(scores)==set(c['D'])|{s for s,q in c['Q'].items() if q}
 x=dict(arm='C10',day='2025-08-15',case=c['certificate_id'],contract_sha256=f['contract_sha256'],trusted=v,certificate=c,original_result=row['projection'],snapshot=ss,demands=dd,rank_binding=rank,scores=scores,
   original_positive_Q={s:q for s,q in c['Q'].items() if q},original_D=c['D'],original_D_parts=row['projection']['donors']['rows'],old_budget_mode=obj.mode,checkpoint_sha256=prov['checkpoint_sha256'],no_account_event=True)
 X.save(O/'INPUT.json',x)
 X.save(O/'ONE_PACKAGE_AUTHORIZATION.json',dict(parent_authorized=True,scope='ONE_AUG15_CLOSE_TO_AUG18_OPEN_STATIC_PACKAGE_ONLY',
   inherited_contract_sha256=f['contract_sha256'],frozen_implementation={n:fm['files_sha256'][n] for n in ['project.py','matching.py','extract.py']},
   input_sha256=X.sha(O/'INPUT.json'),financial_events=0,not_continuous_with_Aug13_hard_projection=True))
 ordered=sorted(dd,key=lambda d:(d['priority'],d['sid']));native=P.native_eval(ss,ordered,c['Q'],c['D'],None)
 assert J.digest(native['donors'])==J.digest(row['projection']['donors']) and J.digest(native['validation'])==J.digest(row['projection']['validation'])
 book=X.budget_book(x);book.approve(book.batch['id']+'|complete_target_plan',{str(z['layer']):z['q'] for z in native['donors']['rows']},target_binding=J.digest(dict(Q=c['Q'],receipts=[d['receipt_id'] for d in v['demands']])))
 assert book.dumps()==row['projection']['budget_after']
 ok,w=P.witness(J,ss,ordered,c['Q'],native['donors'],native['validation'],scores,'ALL',True);assert ok
 X.save(O/'OFF.json',dict(Q=c['Q'],D=c['D'],native=native,matching=w,original_plan_arithmetic_exact=True,budget_after_exact=True,financial_events=0,analysis_only=True,submit_allowed=False))
 print('OFF_FULL_ARITHMETIC_EXACT',w['checked_resource_states'],flush=True)
 # Only output destination is rebound. No policy function/code/data changes.
 P.O=O
 for mode in ['HARD','WEAK']:
  out=O/(mode+'.json')
  if out.exists():r=read(out);assert r['input_sha256']==X.sha(O/'INPUT.json');print('EXISTING_NO_RERUN',mode,flush=True)
  else:
   r=P.solve(x,mode);r.update(input_sha256=X.sha(O/'INPUT.json'),frozen_engine_sha256=fm['files_sha256']['project.py'],inherited_contract_sha256=f['contract_sha256'],analysis_only=True,submit_allowed=False)
   X.save(out,r);print('COMPLETE',mode,'Q/D',sum(q>0 for q in r['Q'].values()),len(r['D']),r['seconds'],flush=True)
  actual=P.native_eval(ss,ordered,r['Q'],r['D'],None);assert actual['validation']['ok'] and J.digest(actual)==J.digest(r['native'])
  ok,proof=P.witness(J,ss,ordered,r['Q'],actual['donors'],actual['validation'],scores,mode,True)
  assert ok and J.digest(proof)==J.digest(r['matching'])
  assert all(q<=c['Q'][s] for s,q in r['Q'].items()) and all(q<=c['D'][s] for s,q in r['D'].items())
 assert all(X.sha(p)==h for p,h in SOURCES.items())
 X.save(O/'VERIFICATION.json',dict(passed=True,plans=3,original_plan_native_and_budget_exact=True,final_native_and_matching_reproduced=True,
   frozen_sources_unchanged=True,sources_sha256=SOURCES,financial_events=0,actual_resource_release=0,
   output_directory_rebinding_only=True,not_a_continuation_of_Aug13_hard_branch=True))
if __name__=='__main__':
 try:main()
 except BaseException as e:X.save(O/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),financial_events=0));raise
