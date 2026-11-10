"""Fresh original1m Jan2022, frozen C economics + R0, audited rights composition."""
from pathlib import Path
from dataclasses import asdict
import sys,copy,pickle,json,hashlib
HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-C-R0-continuous-july-v1-20261102'));import month_r0 as J
R=J.R;M=J.M;E=J.E;RISK_SHA=J.RISK_SHA;sha=J.sha;read=J.read;save=J.save;CAP=250000
CONT_PATH=Path('/Users/bytedance/Documents/Codex/2026-11-01/task/C-rights-month-resume-v2-20261102')
sys.path.insert(0,str(CONT_PATH));import resume_runtime_v2 as C
RIGHTS=C.R
class Inputs(RIGHTS.NoSubscriptionInputsMixin,M.MonthInputs):pass
class Account(R.Account,M.MonthAccount):pass
class Runner(R.Runner,C.ContinuationRunner):
 def __init__(self,mode,*,risk_enabled=True,branch='full'):
  E.require(mode in ('C10','C_BATCH20') and type(risk_enabled) is bool and branch in ('full','physical'),'explicit January modes')
  self.keep_approved_risk=risk_enabled;self.risk=R.RiskBook();self._pure_projection_memo=None;self._memo_hits=0;self._memo_misses=0;self.branch=branch
  M.C.F.FixedRunner.__init__(self,mode,'2022');before=E.digest(J.zero_view(self));old=self.inputs;a=self.account
  identity=read(HERE/'INPUT_IDENTITY.json');ref=identity[branch];E.require(sha(ref['path'])==ref['sha256'],'January frozen input changed');inputs=Inputs(ref['path'])
  E.require(inputs.m['files']==old.m['files'],'original Jan4/5 input prefix changed');provider=M.H.HistoricalMarket(inputs)
  a.market.inputs=inputs;a.market.native.raw=provider.native.raw;a.market.native.actions=provider.native.actions;a.market.native.bundle.manifest_path=inputs.path;a.facts.inputs=inputs;self.inputs=inputs;a.__class__=Account;a.owner=self;a._risk_submit=None;a._risk_fill=None
  bank=a.canonical_registry;binding=a.canonical_binding;a.canonical_generations={binding:bank};a.month_generations={d:binding for d in M.P.EXPECTED['2022']};a.old_canonical_binding=binding;a.canonical_old_end=M.P.EXPECTED['2022'][-1]
  self.month_old_inputs=old;self.month_old_certificates={};self.horizon_old_inputs=old;self.horizon_old_certificates={};self.horizon_branch=branch
  self.month_import=dict(kind='new original1m zero-finance; not a Jan13 account import',source_input=str(old.path),month_input=str(inputs.path));self.horizon_import=dict(kind='no parent financial checkpoint')
  self.no_subscription_actions={};self.execution_authorization=None;self.initial_state_hash=before
  E.require(E.digest(J.zero_view(self))==before,'month binding changed original zero-finance/market state');self.assert_observers()
 def industry_input(self,at):
  if at.date().isoformat()<=M.P.EXPECTED['2022'][-1]:
   view=object.__new__(M.C.F.FixedRunner);view.__dict__.update(self.__dict__);view.inputs=self.month_old_inputs;return M.C.F.FixedRunner.industry_input(view,at)
  return M.C.HorizonRunner.industry_input(self,at)
 def _exact(self,s,ds,e,bb):
  cls=R.M.BatchBook if self.mode=='C_BATCH20' else R.M.OffBook
  book=cls.loads(bb,trusted_sha256=hashlib.sha256(bb.encode()).hexdigest(),account_id=s['account_id'],source_binding=E.digest(s),actual_commitments=json.loads(bb)['body']['lines'])
  if self.mode=='C_BATCH20':return R.M.BC.solve_C20(s,ds,e,book=book,max_native_checks=CAP)
  result=R.M.C.solve_C(s,ds,e,max_native_checks=CAP);working=copy.deepcopy(book);working.approve(book.batch['id']+'|complete_target_plan',{str(p['layer']):p['q'] for p in result['donors']['rows']},target_binding=E.digest(dict(Q=result['Q'],receipts=[d['receipt_id'] for d in ds])))
  return dict(result,budget_before=bb,budget_after=working.dumps())
 def _solve(self,s,ds,e,budget_before):return J.memo_solve(self,self._exact,s,ds,e,budget_before)
 def verify_native(self,cert):return R.M.Runner.verify_native(self,cert)
 def source_binding(self):
  x=R.Runner.source_binding(self);x.update({str(p):sha(p) for p in [HERE/'jan_r0.py',HERE/'run_january.py',HERE/'INPUT_IDENTITY.json']});return x
 def binding(self):
  if self.execution_authorization:
   E.require(sha(self.execution_authorization['path'])==self.execution_authorization['sha256'],'January grant changed');self.validate_grant(self.execution_authorization['path'])
  return dict(scope='JAN2022_FRESH_1M_C_ONLY_R0',mode=self.mode,window='2022',branch=self.branch,risk_enabled=self.keep_approved_risk,source=self.source_binding(),engine=E.IO.runner_identity(self),account_class=E.IO._class_identity(type(self.account)),input_loader=E.IO._class_identity(type(self.inputs)),input_manifest=str(self.inputs.path),input_sha256=sha(self.inputs.path),days=self.inputs.days,initial_state_hash=self.initial_state_hash,execution_authorization=self.execution_authorization,technical_ceiling=CAP,rights_semantics='unchanged audited no-subscription native mixin from first original date',economic_delta='only R0 execution switch; no C1/SD/new capital rule')
 def validate_grant(self,path):
  g=read(path);E.require(g.get('parent_approved') is True and g.get('financial_events_authorized') is True,'explicit January root authorization required')
  E.require(g['runtime_sha256']==sha(__file__) and g['entry_sha256']==sha(HERE/'run_january.py') and g['risk_core_sha256']==RISK_SHA and g['input_identity_sha256']==sha(HERE/'INPUT_IDENTITY.json') and g['technical_ceiling']==CAP,'January source/config changed')
  if g['scope']=='JAN2022_TWO_DAY_GATES':E.require(g['end']=='2022-01-05' and self.mode+'|'+self.branch+'|'+('on' if self.keep_approved_risk else 'off') in g['cells'],'wrong prefix cell')
  elif g['scope']=='JAN2022_TWO_R0_MONTHS':
   E.require(self.keep_approved_risk and self.branch=='full' and g['end']=='2022-01-28','only original2 R0 January accounts');gate=read(HERE/'TWO_DAY_GATE.json');E.require(gate['passed'] and sha(HERE/'TWO_DAY_GATE.json')==g['two_day_gate_sha256'],'prefix gates required')
  else:raise ValueError('unknown January scope')
  return g
 def bind_execution(self,path):self.validate_grant(path);self.execution_authorization=dict(path=str(Path(path).resolve()),sha256=sha(path))
 def execution_guard(self,day,phase=None):
  E.require(self.window=='2022' and day in self.inputs.days and '2022-01-04'<=day<='2022-01-28','January only')
  E.require(self.execution_authorization is not None,'no native event before root grant');g=self.validate_grant(self.execution_authorization['path']);E.require(sha(self.execution_authorization['path'])==self.execution_authorization['sha256'] and day<=g['end'],'outside current execution cutoff')
  E.require(phase in (None,'ACTION','OPEN','CLOSE'),'unsupported phase')
 def corporate_actions(self,day):
  old=E.digest(self.risk.__dict__);out=RIGHTS.NoSubscriptionRunnerMixin.corporate_actions(self,day)
  if any(z.get('classification')==RIGHTS.KIND for z in self.inputs.actions(day)):E.require(old==E.digest(self.risk.__dict__),'no-subscription altered approved R0 book')
  return out
 def _rights_ordinary_dispatch(self,day):return C.ContinuationRunner._rights_ordinary_dispatch(self,day)
 def step(self,day,phase):return C.ContinuationRunner.step(self,day,phase)
 def event(self,at,**kwargs):return C.ContinuationRunner.event(self,at,**kwargs)
 def observable(self,at):
  x=R.Runner.observable(self,at);x.update(new_january_account=dict(initial_state_hash=self.initial_state_hash,execution_authorization=self.execution_authorization),pure_projection_cache=dict(hits=self._memo_hits,misses=self._memo_misses),no_subscription_actions=self.no_subscription_actions);return x
 @classmethod
 def restore(cls,path):
  p=Path(path);side=read(p.with_suffix('.provenance.json'));E.require(sha(p)==side['checkpoint_sha256'],'January bytes changed');r=pickle.loads(p.read_bytes());r.account.owner=r
  E.require(type(r) is cls and r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'January actual source/class/input changed');r.assert_observers()
  # Each solution verified on registration. Immutable trusted/cert body hashes
  # checked by original R0/native observers; no replay of finance on restore.
  return r
