"""C20 exact-search technical ceiling 100000 -> 250000. No economic change.
Legacy certificates are verified under their immutable original source view;
new certificates bind this module/entry/explicit transition authorization.
"""
from pathlib import Path
import sys,copy,pickle,json,hashlib
HERE=Path(__file__).resolve().parent;OLD=HERE.parent/'g-s-C-R0-continuous-july-v1-20261102'
sys.path.insert(0,str(OLD));import month_r0 as X
E=X.E;R=X.R;CAP=250000;AUTH=HERE/'SOURCE_TRANSITION_AUTHORIZATION.json'
OLD_RUNTIME='a9fecca4bea21d418f65d27b75d8ce41d346e7f4cb87456ea172e8a4a2ee92de'
OLD_ENTRY='d06695f62dba6bb69796c88f7b428d1735a601d58b9b44ea3b2e0702dd329edc'
AT=E.iso('2025-07-22T15:10:00+08:00');read=X.read;save=X.save;sha=X.sha

def guard():
 E.require(sha(OLD/'month_r0.py')==OLD_RUNTIME and sha(OLD/'run_july.py')==OLD_ENTRY,'original frozen source changed')
 a=read(AUTH);E.require(a['parent_approved'] and a['technical_ceiling']==CAP and a['old_technical_ceiling']==100000,'specific technical authorization required')
 E.require(a['runtime_sha256']==sha(__file__) and a['entry_sha256']==sha(HERE/'recover_c20.py'),'technical recovery source changed')
 E.require(a['scope']=='ONLY_C20_R0_JUL22_OPTIONAL_THEN_JUL31' and a['no_economic_change'],'wrong recovery scope')
 return a

def legacy_view(r,cid):
 a=guard();E.require(cid in a['legacy_certificate_ids'] and cid in r.legacy_certificates,'unregistered legacy certificate')
 E.require(r.authority.certificates[cid]==r.legacy_certificates[cid],'legacy certificate body changed')
 v=object.__new__(X.Runner);v.__dict__.update(r.__dict__)
 E.require(E.digest(v.source_binding())==a['legacy_source_binding_digest'],'legacy source view changed')
 return v

# The frozen RiskBook calls its module-level accessor. Only source selection
# for the EXACT imported legacy IDs is adapted; all original accessor/hash/
# receipt/Q0/floor/source checks still execute. No original file is edited.
_RAW_APPROVED=R.approved_payload

def approved_payload(r,cid,sid,*,full_verify=True):
 if hasattr(r,'legacy_certificates') and cid in r.legacy_certificates:
  return _RAW_APPROVED(legacy_view(r,cid),cid,sid,full_verify=full_verify)
 return _RAW_APPROVED(r,cid,sid,full_verify=full_verify)
R.approved_payload=approved_payload

def economic_view(r):
 x=copy.deepcopy(r.observable(r.last_completed_event));x.pop('new_july_account',None);x.pop('pure_projection_cache',None)
 return dict(observable=x,lifecycle=r.lifecycle,last_stock_state=r.last_stock_state,cursor=r.cursor,goal_intents=r.goal_intents,busy=r._busy_goals,active_intents=r.active_intents,rank_bindings=r.rank_bindings,audit=r.account.audit_log,decisions=r.account.decisions)

def exact250(s,ds,e,bb):
 book=R.M.BatchBook.loads(bb,trusted_sha256=hashlib.sha256(bb.encode()).hexdigest(),account_id=s['account_id'],source_binding=E.digest(s),actual_commitments=json.loads(bb)['body']['lines'])
 # ONLY solver difference: same frozen engine/order, explicit higher loop cap.
 return R.M.BC.solve_C20(s,ds,e,book=book,max_native_checks=CAP)

class Runner(X.Runner):
 def _solve(self,s,ds,e,budget_before):
  E.require(self.mode=='C_BATCH20','technical version is C20 only')
  return X.memo_solve(self,exact250,s,ds,e,budget_before)
 def source_binding(self):
  x=X.Runner.source_binding(self);x.update({str(p):sha(p) for p in [HERE/'budget250.py',HERE/'recover_c20.py',AUTH]});return x
 def validate_grant(self,path):
  a=guard();E.require(Path(path).resolve()==AUTH.resolve(),'specific new technical source authorization required')
  E.require(self.mode=='C_BATCH20' and self.keep_approved_risk and self.branch=='full','wrong financial account');return dict(a,end='2025-07-31')
 def binding(self):
  x=X.Runner.binding(self);x.update(technical_recovery=self.technical_recovery,legacy_certificate_ids=sorted(self.legacy_certificates),technical_ceiling=CAP,legacy_verification='unchanged original source view only for immutable imported IDs; current source for all new IDs')
  return x
 def verify_native(self,cert):
  if cert['certificate_id'] in self.legacy_certificates:return legacy_view(self,cert['certificate_id']).verify_native(cert)
  return super().verify_native(cert)
 def execution_guard(self,day):
  super().execution_guard(day)
  E.require('2025-07-23'<=day<='2025-07-31' and self.technical_recovery['status']=='recovered','must not replay Jul22 necessary phase')
  g=self.technical_recovery.get('restore_gate');E.require(g and sha(g['path'])==g['sha256'] and read(g['path'])['passed'],'cross-process idempotence gate required')
 def retry_technical_optional(self):
  if self.technical_recovery['status']=='recovered':return dict(state='TECHNICAL_RECOVERY_ALREADY_SUCCEEDED')
  guard();E.require(self.last_completed_event==AT,'exact committed necessary cursor only')
  key=AT.isoformat();st=self.close_stages[key];E.require(st['necessary_done'] and st['optional_status']=='failed_exception','original failed optional stage required')
  E.require(self.necessary_digest(AT)==st['necessary_digest'],'necessary phase changed before retry')
  E.require(self.technical_recovery['pure_gate']['sha256']==sha(self.technical_recovery['pure_gate']['path']),'pure gate changed')
  E.require(read(self.technical_recovery['pure_gate']['path'])['passed'],'pure identity gate required')
  proof=E.digest(st['evidence']);E.require(proof==st['evidence_sha256'],'no input/evidence change')
  history=copy.deepcopy(st['attempts']);before_fills=E.digest(self.account.fills);before_trades=E.digest(self.account.trades);before_balance=self.account.bridge(AT)
  backup=pickle.dumps(self)
  try:
   # Explicit new technical generation. Never delete/change prior failed attempts
   # to trick the original same-evidence failed-attempt deduplication.
   self.industry_evidence=copy.deepcopy(st['evidence'])
   result=self.plan(copy.deepcopy(st['prepared_intents']),st['clock'])
   st=self.close_stages[key];E.require(st['attempts']==history,'old failure history changed')
   st['optional_status']='succeeded';st['attempts'].append(dict(input=proof,state=result['state'],technical_generation=sha(AUTH),technical_ceiling=CAP,recovery_from='retained_failed_exception'))
   self.account.pending=copy.deepcopy(st['prepared_intents']);self.last_phase='CLOSE'
   E.require(not any(v['at']==AT and v['phase']=='CLOSE' for v in self.events),'CLOSE financial record already present')
   self.events.append(dict(at=AT,phase='CLOSE',bridge=self.account.bridge(AT)))
   self.lifecycle.append(dict(at=AT,cursor=self.cursor,trace=['optional_C_recovered_only','necessary_CLOSE_not_replayed'],technical_generation=sha(AUTH)))
   self.technical_recovery['status']='recovered';self.technical_recovery['original_failed_attempts']=history;self.technical_recovery['recovered_certificate']=result['certificate']
   E.require(E.digest(self.account.fills)==before_fills and E.digest(self.account.trades)==before_trades,'optional retry executed trades')
   after=self.account.bridge(AT)
   for k in ('nav','available','inventory','fees_cny','quantities','dividend_receivable','sale_receivable'):E.require(after[k]==before_balance[k],'optional retry changed financial '+k)
   self.assert_observers();return result
  except Exception:
   self._restore_optional(backup);raise
 @classmethod
 def restore(cls,path):
  guard();p=Path(path);side=read(p.with_suffix('.provenance.json'));E.require(sha(p)==side['checkpoint_sha256'],'recovery checkpoint bytes changed');r=pickle.loads(p.read_bytes());r.account.owner=r
  E.require(type(r) is cls and r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'actual recovery engine/source binding changed');r.assert_observers()
  # Imported bodies were fully recomputed at the 250k pure gate. Reuse them
  # under immutable CID/source/raw-trusted hashes, do not re-solve old history.
  for cid,c in r.authority.certificates.items():
   if cid in r.legacy_certificates:
    v=legacy_view(r,cid);t=v.trusted[c['trusted_id']]
    E.require(cid==E.digest({k:x for k,x in c.items() if k!='certificate_id'}) and c['trusted_id']==E.digest(dict(s=t['snapshot'],ds=t['demands'],e=t['evidence'],bb=t['budget_before'])) and c['snapshot_hash']==E.digest(t['snapshot']),'legacy trusted proof changed')
   else:r.verify_native(c)
  return r
