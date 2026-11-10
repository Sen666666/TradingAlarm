"""Five independent full-C-domain static plans, account risk6 only off/on."""
from pathlib import Path
import sys,copy,time,traceback,json,hashlib,argparse
O=Path(__file__).resolve().parent;sys.path.insert(0,str(O));import engine as E
X=E.X;J=E.J

def budget_after(x,r):
 raw=x['trusted']['budget_before'];v=x['trusted'];cls=X.A.R.M.OffBook
 b=cls.loads(raw,trusted_sha256=hashlib.sha256(raw.encode()).hexdigest(),account_id=v['snapshot']['account_id'],source_binding=J.digest(v['snapshot']),actual_commitments=json.loads(raw)['body']['lines'])
 b.approve(b.batch['id']+'|complete_target_plan',{str(p['layer']):p['q'] for p in r['donors']['rows']},target_binding=J.digest(dict(Q=r['Q'],receipts=[d['receipt_id'] for d in v['demands']])))
 return b.dumps()

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--day');a=ap.parse_args();f=X.read(O/'AUTHORIZATION_AND_FREEZE.json')
 assert f['parent_authorized'] and X.read(O/'NATIVE_PREVIEW_COMPONENT_GATE.json')['passed']
 assert all(X.sha(p)==h for p,h in f['sources_sha256'].items())
 for day in f['dates']:
  if a.day and a.day!=day:continue
  p=O/('INPUT-'+day+'.json');assert X.sha(p)==f['full_candidate_inputs'][p.name];x=X.read(p);v=x['trusted'];before=J.digest(v)
  for ab in [False,True]:
   mode='NO_AR6' if ab else 'ORIGINAL_6';out=O/(mode+'-'+day+'.json')
   if out.exists():
    old=X.read(out);assert old['input_sha256']==X.sha(p) and old['engine_sha256']==X.sha(O/'engine.py');print('ALREADY_COMPLETE',mode,day,flush=True);continue
   c,patch=E.factory(ab);started=time.perf_counter()
   def progress(tr):
    X.save(O/'PROGRESS.json',dict(day=day,mode=mode,candidate=tr['sid'],q=tr['q'],native_checks_this_candidate=tr.get('native_checks'),seconds=time.perf_counter()-started,financial_events=0))
   X.save(O/'RUNNING.json',dict(day=day,mode=mode,started_utc=__import__('datetime').datetime.now(__import__('datetime').timezone.utc).isoformat(),financial_events=0))
   print('START',mode,day,'all candidates',len(v['demands']),flush=True)
   try:r=c.solve_C(copy.deepcopy(v['snapshot']),copy.deepcopy(v['demands']),copy.deepcopy(v['evidence']),max_native_checks=f['technical_native_check_ceiling'],progress=progress)
   except BaseException as exc:
    X.save(O/('FAILURE-'+mode+'-'+day+'.json'),dict(error=repr(exc),traceback=traceback.format_exc(),technical_budget=f['technical_native_check_ceiling'],input_sha256=X.sha(p),seconds=time.perf_counter()-started,financial_events=0,not_economic_infeasibility=True))
    print('STOPPED',mode,day,repr(exc),flush=True);break
   r=dict(r,budget_before=v['budget_before'],budget_after=budget_after(x,r))
   if not ab:assert J.digest(r)==x['certificate']['projection_hash'] and J.digest(r)==J.digest(x['original_result']),'whole original Q/D/trace/guard/budget identity failed'
   else:
    # Keep source IDs as base-source identifiers, never mislabel changed runtime.
    r['base_source_joint_guard_unchanged_field']=r.pop('source_joint_guard_unchanged');r['runtime_joint_guard_unchanged']=False;r['policy']='C10_NO_AR6_STATIC'
    r['base_algorithm_payload_id']=r.pop('result_id');r['result_id']=J.digest(r)
    assert not any('account_risk6' in why for why in r['validation']['violations'])
   assert r['validation']['ok'] and J.digest(v)==before
   checks=r['validation']['checks'];riskchecks=[z for z in checks if z['constraint']=='account_risk6']
   result=dict(day=day,mode=mode,ablation_enabled=ab,original_full_identity=not ab,input_sha256=X.sha(p),engine_sha256=X.sha(O/'engine.py'),
     result=r,patch_ast_sha256=hashlib.sha256(json.dumps(patch,sort_keys=True).encode()).hexdigest(),
     all_C_candidates=len(v['demands']),original_zero_Q_retained_in_domain=True,old_legal_donor_domain_unchanged=True,
     nominal_risk_measured=True,account6_observations=len(riskchecks),account6_observed_negative_residuals=sum(__import__('decimal').Decimal(z['residual'])<0 for z in riskchecks),
     account6_enforced=not ab,seconds=time.perf_counter()-started,financial_events=0,actual_cash_released=0,actual_risk_released=0,
     conditional_projection_not_fills=True,full_OPEN_not_run=True,analysis_only=True,submit_allowed=False)
   X.save(out,result);print('COMPLETE',mode,day,'Q+',sum(q>0 for q in r['Q'].values()),'D+',len(r['D']),'native checks',r['native_checks'],'seconds',round(result['seconds'],2),flush=True)
 X.save(O/'SOURCE_INTEGRITY.json',dict(all_unchanged=all(X.sha(p)==h for p,h in f['sources_sha256'].items()),financial_events=0))
if __name__=='__main__':
 try:main()
 except BaseException as e:X.save(O/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),financial_events=0));raise
