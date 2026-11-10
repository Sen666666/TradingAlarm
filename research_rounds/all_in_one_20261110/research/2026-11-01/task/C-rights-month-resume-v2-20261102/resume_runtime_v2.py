"""Explicit source upgrade of registered ACTION state to original month dispatch."""
from pathlib import Path
import copy,hashlib,json,pickle,sys
O=Path(__file__).resolve().parent;P=O.parent/'C-rights-Jan13-action-v3-20261102'
sys.path.insert(0,str(P));import action_runtime as A
U=A.U;M=U.M;E=A.E;FP=sys.modules['fingerprint'];R=A.R
OLD_ROOT=O.parent/'C-rights-month-resume-20261102'
sys.path.insert(0,str(OLD_ROOT));import continuation_runtime as OLD
sys.path.remove(str(OLD_ROOT))
from legacy_readonly_v2 import verify_old_certificate
sha=A.sha;read=A.read;require=A.require
def guard():
 f=read(O/'SOURCE_FREEZE.json')
 for p,h in f['sources'].items():require(sha(p)==h,'continuation source changed '+p)
 require(sha(O/'IDENTITY.json')==f['identity_sha256'],'continuation identity changed')
 x=read(O/'IDENTITY.json');require(sha(x['parent_registry'])==x['parent_registry_sha256'],'parent ACTION registry changed');return x
def validate(r,path,trusted_sha):
 x=guard();require(trusted_sha and sha(path)==trusted_sha,'explicit continuation grant SHA required');g=read(path);arm=r.action_activation['arm'];branch=r.month_continuation_import['branch']
 require(g.get('parent_approved') is True and g.get('scope')=='C_EXISTING_ACCOUNT_MONTH_CONTINUATION' and g.get('no_account_reset') is True,'unapproved continuation grant')
 require(g['runtime_identity_sha256']==sha(O/'IDENTITY.json') and g['arm']==arm and g['mode']==r.mode and g['window']==r.window=='2022' and g['branch']==branch,'wrong continuation mode/source/branch')
 require(g['base_ACTION_checkpoint_sha256']==x['arms'][arm]['sha256'] and g['input_manifest_sha256']==sha(r.inputs.path)==x['inputs'][branch]['sha256'],'wrong continuation input/parent')
 require(g['days'] and g['days']==sorted(set(g['days'])) and all(d in r.inputs.days for d in g['days']),'grant outside frozen input days')
 require(set(g['phases'])<=set(['ACTION','OPEN','CLOSE']) and g['phases'],'unknown grant phase')
 return g
class ContinuationRunner(A.ActionRunner):
 def __init__(self,*a,**kw):raise RuntimeError('explicit registered ACTION import only')
 def source_binding(self):
  out=super().source_binding()
  for n in ['resume_runtime_v2.py','prepare.py','driver.py','compare_resume_v2.py','CONTRACT.txt','IDENTITY.json','INPUT_FREEZE.json','SOURCE_FREEZE.json','legacy_readonly_v2.py']:
   p=O/n;out[str(p)]=sha(p)
  return out
 def verify_native(self,cert):
  return verify_old_certificate(self,cert,U=U,FP=FP)
 def binding(self):
  out=super().binding();out.update(month_continuation_import=copy.deepcopy(self.month_continuation_import),continuation_grant=copy.deepcopy(self.continuation_grant_record),continuation_grant_history=copy.deepcopy(self.continuation_grant_history))
  validate(self,self.continuation_grant_record['path'],self.continuation_grant_record['sha256']);return out
 def accept_continuation_grant(self,path,*,trusted_sha):
  g=validate(self,path,trusted_sha);before=R.conservation_bytes(self);prior=getattr(self,'continuation_grant_record',None)
  rec=dict(path=str(Path(path).resolve()),sha256=trusted_sha,days=g['days'],phases=g['phases'])
  if prior==rec:return 'already_accepted'
  if prior:require(max(g['days'])>=max(prior['days']),'cannot silently shorten continuation grant')
  self.continuation_grant_record=rec;self.continuation_grant_history.append(dict(old=prior,new=rec,at=str(self.last_completed_event)))
  require(R.conservation_bytes(self)==before,'grant changed financial/strategy state');return 'accepted_no_event'
 def execution_guard(self,day,phase=None):
  # Original ACTION guard remains intact and verifies the retained parent proof.
  A.ActionRunner.execution_guard(self,'2022-01-13')
  g=validate(self,self.continuation_grant_record['path'],self.continuation_grant_record['sha256'])
  require(day in g['days'] and (phase is None or phase in g['phases']),'outside explicit continuation day/phase')
 def corporate_actions(self,day):
  actions=self.inputs.actions(day);seen=self.no_subscription_actions
  proofs=[R.validate_rights(x,day) for x in actions] if actions and all(x.get('classification')==R.KIND for x in actions) else []
  already=bool(proofs) and all(p['event_id'] in seen and seen[p['event_id']]['payload_sha256']==p['payload_sha256'] for p in proofs)
  self.execution_guard(day,None if already else 'ACTION')
  return R.NoSubscriptionRunnerMixin.corporate_actions(self,day)
 def _rights_ordinary_dispatch(self,day):
  self.execution_guard(day,'ACTION');return M.MonthRunner.corporate_actions(self,day)
 def step(self,day,phase):
  require(phase in ['OPEN','CLOSE'],'unknown continuation phase');self.execution_guard(day,phase)
  before=R.conservation_bytes(self);backup=pickle.dumps(self,pickle.HIGHEST_PROTOCOL)
  try:return M.MonthRunner.step(self,day,phase)
  except Exception:
   at=E.iso(day+('T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'));stage=self.close_stages.get(at.isoformat())
   if not (stage and stage.get('necessary_done') and stage.get('optional_status')=='failed_exception' and self.last_completed_event==at):
    prior=pickle.loads(backup);self.__dict__.clear();self.__dict__.update(prior.__dict__);self.account.owner=self
    require(R.conservation_bytes(self)==before,'native step rollback changed financial state')
   raise
 def event(self,at,**kwargs):
  phase='OPEN' if kwargs.get('is_open') else 'CLOSE' if kwargs.get('observations') is not None else None
  require(phase is not None and at==E.iso(at.date().isoformat()+('T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00')),'arbitrary native event forbidden')
  self.execution_guard(at.date().isoformat(),phase)
  return M.P.HistoricalRunner.event(self,at,**kwargs)
 def verify_current(self,rec):
  x=guard();imp=self.month_continuation_import;require(imp['identity_sha256']==sha(O/'IDENTITY.json') and imp['base_ACTION_checkpoint_sha256']==x['arms'][imp['arm']]['sha256'],'continuation origin changed')
  require(type(self.account) is M.MonthAccount and type(self.inputs) is U.RightsMonthInputs and self.mode==x['arms'][imp['arm']]['arm'][5:],'continuation account/input/mode changed')
  require(all(k in self.no_subscription_actions and FP.digest(self.no_subscription_actions[k])==h for k,h in imp['parent_rights_proofs'].items()),'completed rights proof changed')
  require(FP.digest(self.action_log[:imp['parent_action_log_count']])==imp['parent_action_log_sha256'],'old action log prefix changed')
  self.binding();expected=read(rec['fields']);require(sha(rec['fields'])==rec['fields_sha256'] and FP.snapshot(self)==expected,'registered complete continuation state changed')
  self.assert_observers()
  for c in self.authority.certificates.values():self.verify_native(c)
  require(FP.snapshot(self)==expected,'certificate verification changed continuation fields');return True
 @classmethod
 def restore(cls,path,*,registry_sha):
  guard();p=Path(path).resolve();require(p.parent.parent.parent==O/'runs','unregistered continuation directory')
  bankfile=p.parent/'REGISTRY.json';require(registry_sha and sha(bankfile)==registry_sha,'explicit trusted continuation registry SHA required');bank=read(bankfile)
  require(bank['identity_sha256']==sha(O/'IDENTITY.json'),'wrong continuation registry identity')
  matches=[r for r in bank['checkpoints'] if Path(r['checkpoint']).resolve()==p];require(len(matches)==1,'unregistered continuation checkpoint');rec=matches[0]
  require(sha(p)==rec['sha256'] and sha(p.with_suffix('.provenance.json'))==rec['provenance_sha256'],'continuation checkpoint bytes changed')
  side=read(p.with_suffix('.provenance.json'));require(side['checkpoint_sha256']==rec['sha256'],'continuation provenance mismatch')
  with p.open('rb') as f:r=pickle.load(f)
  require(type(r) is cls and r.month_continuation_import['arm']==p.parent.parent.name and r.month_continuation_import['branch']==p.parent.name,'wrong continuation class/branch')
  r.account.owner=r;require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'exact continuation native/source identity required')
  r.verify_current(rec);return r
def import_action(arm,branch):
 x=guard();parent=x['arms'][arm];origin=x['import_sources'][arm+'|'+branch]
 if origin['kind']=='IMPORT':r=OLD.ContinuationRunner.restore(origin['checkpoint'],registry_sha=origin['registry_sha256'])
 else:r=A.ActionRunner.restore(parent['checkpoint'],registry_sha=x['parent_registry_sha256'])
 before=R.conservation_bytes(r);prefix=U.prefix_hashes(r);old_fields=FP.snapshot(r)
 rights=FP.digest(r.no_subscription_actions);log_hash=FP.digest(r.action_log);log_count=len(r.action_log)
 require(r.last_completed_event==A.AT and type(r) in {A.ActionRunner,OLD.ContinuationRunner},'must start immediately after trusted ACTION/IMPORT')
 if branch=='physical' and origin['kind']=='ACTION':
  inputs=U.RightsMonthInputs(x['inputs'][branch]['path']);provider=M.H.HistoricalMarket(inputs);a=r.account
  r.inputs=inputs;a.market.inputs=inputs;a.facts.inputs=inputs;a.market.native.raw=provider.native.raw;a.market.native.actions=provider.native.actions;a.market.native.bundle.manifest_path=inputs.path
 r.__class__=ContinuationRunner
 prior_import=copy.deepcopy(getattr(r,'month_continuation_import',None))
 r.month_continuation_import=dict(previous_import=prior_import,source_checkpoint_sha256=origin['sha256'],version='C_MONTH_RIGHTS_RESUME_2',identity_sha256=sha(O/'IDENTITY.json'),arm=arm,branch=branch,base_ACTION_checkpoint_sha256=parent['sha256'],parent_rights_proof_sha256=rights,parent_rights_proofs={k:FP.digest(v) for k,v in r.no_subscription_actions.items()},parent_action_log_count=log_count,parent_action_log_sha256=log_hash,no_financial_event=True)
 r.continuation_grant_history=copy.deepcopy(getattr(r,'continuation_grant_history',[]));r.continuation_grant_record=getattr(r,'continuation_grant_record',None)
 g=read(O/'INITIAL_GRANTS.json')[arm+'|'+branch];r.accept_continuation_grant(g['path'],trusted_sha=g['sha256'])
 require(R.conservation_bytes(r)==before and U.prefix_hashes(r)==prefix,'thin import changed complete financial/strategy/flow state')
 for c in r.authority.certificates.values():r.verify_native(c)
 require(R.conservation_bytes(r)==before,'import certificate verification changed financial state')
 delta=FP.compare(old_fields,FP.snapshot(r));metadata={'runner.month_continuation_import','runner.continuation_grant_record','runner.continuation_grant_history'}
 require(all(k in metadata or branch=='physical' and (k.startswith('inputs.') or k in {'native.raw','native.actions','native.bundle'}) for k in delta['changed']),'undeclared no-event import field changes '+str(delta['changed']))
 return r,dict(no_event=True,conservation_before=hashlib.sha256(before).hexdigest(),conservation_after=hashlib.sha256(R.conservation_bytes(r)).hexdigest(),prefix_exact=True,complete_field_diff=delta,legacy_certificates=len(r.authority.certificates))
