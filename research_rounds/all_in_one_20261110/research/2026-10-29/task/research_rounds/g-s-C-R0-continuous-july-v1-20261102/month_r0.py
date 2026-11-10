"""New1m July accounts, original C economics + frozen C R0 execution flag.
Preparation constructs native accounts only; finance needs a NEW explicit grant.
"""
from pathlib import Path
from dataclasses import asdict
from decimal import getcontext
import sys,copy,pickle,json,hashlib
HERE=Path(__file__).resolve().parent;W=HERE.parent
RISK=W/'g-s-C-approved-risk-native-v1-20261102';RISK_SHA='b447dcb43fa72e5d25ef79f15b21de3c8e5cd41ef64eee5fa86085f2418caeb7'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
if sha(RISK/'native_risk.py')!=RISK_SHA:raise ValueError('frozen R0 source changed')
sys.path.insert(0,str(RISK));import native_risk as R
if 'native_c' in sys.modules and sys.modules['native_c'] is not R.M:raise ValueError('fresh process required; mixed module already loaded differently')
sys.modules['native_c']=R.M
sys.path.insert(0,str(W/'g-s-C-month-continuation-20261102'));import month_runtime as M
E=M.E

def read(p):return json.loads(Path(p).read_text())
def save(p,x):E.IO.write_json(p,x,encoder=E.encode)
def decimal_semantics():
 c=getcontext();return dict(prec=c.prec,rounding=c.rounding,Emin=c.Emin,Emax=c.Emax,clamp=c.clamp,traps={str(k):v for k,v in c.traps.items()})
def memo_solve(owner,original,s,ds,e,bb):
 """Memoize ONLY an immutable pure projection. Every native guard still runs.
 No caching live _preview/resources, quantity amendments, cash or fills.
 """
 token=E.digest(dict(mode=owner.mode,source=owner.source_binding(),decimal=decimal_semantics(),s=s,ds=ds,e=e,bb=bb))
 m=getattr(owner,'_pure_projection_memo',None)
 if m and m['token']==token:
  E.require(E.digest(m['value'])==m['value_hash'],'pure projection memo changed')
  owner._memo_hits=getattr(owner,'_memo_hits',0)+1
  return copy.deepcopy(m['value'])
 v=original(s,ds,e,bb);owner._memo_misses=getattr(owner,'_memo_misses',0)+1
 owner._pure_projection_memo=dict(token=token,value=copy.deepcopy(v),value_hash=E.digest(v))
 return v

def zero_view(r):
 a=r.account;warm=E.iso(r.inputs.m['warm_through']+'T15:10:00+08:00')
 return dict(balance=a.bridge(warm),policy=a.policy.exported(),f1={k:asdict(v) for k,v in r.f1.items()},f1seq=r.f1seq,cursor=r.cursor,
   pending=a.pending,buys=a.buys,exits=a.exits,layers=a.layers,fills=a.fills,trades=a.trades,core_epoch=a.core_epoch,
   consumed=a.policy.consumed,losses=a.policy.losses,authority=r.authority.__dict__,budget=r.budget,last_completed=r.last_completed_event,
   goal_coverage=r.coverage.exported(),last_stock_state=r.last_stock_state,canonical_binding=a.canonical_binding,canonical_registry=a.canonical_registry)

class Account(R.Account,M.MonthAccount):pass
class Runner(R.Runner,M.MonthRunner):
 def __init__(self,mode,*,risk_enabled=True,branch='full'):
  E.require(mode in ('C10','C_BATCH20'),'only the two original reference modes')
  E.require(type(risk_enabled) is bool and branch in ('full','physical'),'explicit gate config');self.branch=branch
  M.guard();self.keep_approved_risk=risk_enabled;self.risk=R.RiskBook();self._pure_projection_memo=None;self._memo_hits=0;self._memo_misses=0
  # ORIGINAL fresh1m factory, not an old financial checkpoint/account import.
  M.C.F.FixedRunner.__init__(self,mode,'2025_26')
  before=E.digest(zero_view(self));old=self.inputs;a=self.account
  rec=read(HERE/'INPUT_IDENTITY.json');E.require(sha(rec['month_manifest'])==rec['month_manifest_sha256'],'full month input changed')
  mp=rec['month_manifest'] if branch=='full' else rec['physical_manifest'];mh=rec['month_manifest_sha256'] if branch=='full' else rec['physical_manifest_sha256'];E.require(sha(mp)==mh,'branch manifest changed')
  inputs=M.MonthInputs(mp);E.require(inputs.m['files']==old.m['files'],'initial source numeric prefix changed')
  provider=M.H.HistoricalMarket(inputs)
  a.market.inputs=inputs;a.market.native.raw=provider.native.raw;a.market.native.actions=provider.native.actions;a.market.native.bundle.manifest_path=inputs.path;a.facts.inputs=inputs;self.inputs=inputs
  a.__class__=Account;a._risk_submit=None;a._risk_fill=None;a.owner=self
  oldbank=a.canonical_registry;oldbinding=a.canonical_binding
  a.canonical_generations={oldbinding:oldbank};a.month_generations={d:oldbinding for d in M.P.EXPECTED['2025_26']}
  a.old_canonical_binding=oldbinding;a.canonical_old_end=M.P.EXPECTED['2025_26'][-1]
  self.month_old_inputs=old;self.month_old_certificates={};self.horizon_old_inputs=old;self.horizon_old_certificates={}
  self.horizon_branch='full';self.horizon_import=dict(kind='zero-finance fullmonth input binding',parent_financial_account=None)
  self.month_import=dict(kind='fresh original1m; no account checkpoint import',old_input=str(old.path),month_input=str(inputs.path),old_numeric_prefix_preserved=True)
  self.execution_authorization=None;self.initial_state_hash=before
  E.require(E.digest(zero_view(self))==before,'fullmonth binding changed original initial finance/market state')
  self.assert_observers()
 def industry_input(self,at):
  if at.date().isoformat()<=M.P.EXPECTED['2025_26'][-1]:
   view=object.__new__(M.C.F.FixedRunner);view.__dict__.update(self.__dict__);view.inputs=self.month_old_inputs
   return M.C.F.FixedRunner.industry_input(view,at)
  return M.C.HorizonRunner.industry_input(self,at)
 def _solve(self,s,ds,e,budget_before):
  return memo_solve(self,super()._solve,s,ds,e,budget_before)
 def source_binding(self):
  x=R.Runner.source_binding(self)
  x.update({str(p):sha(p) for p in [HERE/'month_r0.py',HERE/'run_july.py',HERE/'INPUT_IDENTITY.json']})
  return x
 def binding(self):
  if self.execution_authorization is not None:
   E.require(sha(self.execution_authorization['path'])==self.execution_authorization['sha256'],'bound monthly grant changed')
   self.validate_grant(self.execution_authorization['path'])
  return dict(scope='NEW_ORIGINAL1M_C10_OR_C20_PLUS_R0_JULY_ONLY',branch=self.branch,risk_enabled=self.keep_approved_risk,mode=self.mode,window=self.window,start='2025-07-01',end='2025-07-31',
   source=self.source_binding(),engine=E.IO.runner_identity(self),account_class=E.IO._class_identity(type(self.account)),input_loader=E.IO._class_identity(type(self.inputs)),
   input_manifest=str(self.inputs.path),input_sha256=sha(self.inputs.path),days=self.inputs.days,initial_state_hash=self.initial_state_hash,
   canonical_prefix='Jul1/2 original initial generation; Jul3+ original as-of generation',execution_authorization=self.execution_authorization,
   economic_delta='C trusted stock authorization R0 execution only',non_economic_memo='exact full immutable projection inputs/source/mode/decimal semantics; no native guard skipped')
 def validate_grant(self,path):
  g=read(path);E.require(g.get('parent_approved') is True and g.get('financial_events_authorized') is True,'new monthly root grant required')
  E.require(g['runtime_sha256']==sha(__file__) and g['entry_sha256']==sha(HERE/'run_july.py') and g['risk_core_sha256']==RISK_SHA and g['input_identity_sha256']==sha(HERE/'INPUT_IDENTITY.json'),'new identity binding changed')
  if g['scope']=='SAME_RUNNER_JULY_TWO_DAY_GATES_ONLY':
   E.require(g['start']=='2025-07-01' and g['end']=='2025-07-02','wrong prefix dates')
   key=self.mode+'|'+self.branch+'|'+('on' if self.keep_approved_risk else 'off')
   E.require(key in g['cells'],'unapproved prefix cell')
  elif g['scope']=='TWO_NEW1M_R0_JULY_PATHS_ONLY':
   E.require(self.keep_approved_risk and self.branch=='full' and self.mode in g['modes'] and g['start']=='2025-07-01' and g['end']=='2025-07-31','wrong month/economic scope')
   gates=read(HERE/'TWO_DAY_GATE.json');E.require(gates['passed'] and g['two_day_gate_sha256']==sha(HERE/'TWO_DAY_GATE.json'),'formal two-day gates required')
  else:raise ValueError('unknown authorization scope')
  return g
 def bind_execution(self,path):
  self.validate_grant(path);self.execution_authorization=dict(path=str(Path(path).resolve()),sha256=sha(path))
 def execution_guard(self,day):
  E.require(day in self.inputs.days and '2025-07-01'<=day<='2025-07-31','outside July input scope')
  E.require(self.execution_authorization is not None,'PREPARATION ONLY: finance not approved')
  g=self.execution_authorization;E.require(sha(g['path'])==g['sha256'],'grant changed');a=self.validate_grant(g['path']);E.require(day<=a['end'],'outside current grant cutoff')
 def step(self,day,phase):
  self.execution_guard(day);return M.H.HistoricalRunner.step(self,day,phase)
 def corporate_actions(self,day):
  self.execution_guard(day)
  # Reuse ORIGINAL C preflight, including refusing unsubmitted concrete Q splits.
  return M.P.HistoricalRunner.corporate_actions(self,day)
 def observable(self,at):
  x=R.Runner.observable(self,at);x.update(new_july_account=dict(initial_state_hash=self.initial_state_hash,execution_authorization=self.execution_authorization),pure_projection_cache=dict(hits=self._memo_hits,misses=self._memo_misses))
  return x
 @classmethod
 def restore(cls,path):
  p=Path(path);side=read(p.with_suffix('.provenance.json'));E.require(sha(p)==side['checkpoint_sha256'],'monthly checkpoint bytes changed')
  r=pickle.loads(p.read_bytes());E.require(type(r) is cls and r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'monthly source/account/input/policy identity mismatch')
  r.account.owner=r;r.assert_observers()
  for c in r.authority.certificates.values():r.verify_native(c)
  return r
