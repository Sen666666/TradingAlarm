"""Exactly fixed alpha/MA robustness; original gross formulas parameterized."""
from pathlib import Path
from decimal import Decimal as D
import ast,copy,hashlib,inspect,sys,textwrap
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'market_gross_admission_native_v1'))
import gross_adapter as C
import cost15_compat as K
A,N,J,L,IO,P=C.A,C.N,C.J,C.L,C.IO,C.P
FAMILIES={'cost1':{'MA63_G05':(63,'.05',D(1)),'MA63_G20':(63,'.20',D(1)),'MA62_G10':(62,'.10',D(1)),'MA64_G10':(64,'.10',D(1))},'cost15':{'NO60_C15':(None,None,D('1.5')),'MA63_G10_C15':(63,'.10',D('1.5'))}}
TECH_CONTROL={'MA63_G10_TECH':(63,'.10',D(1))}
POLICY='FIXED_MARKET_GROSS_ROBUSTNESS_V1'

# Same reviewed bodies. Only constant alpha becomes each account's fixed alpha.
CONTEXT_OLD=inspect.getsource(C.context)
CONTEXT_NEW=CONTEXT_OLD.replace("info=a.gross_info.state(at))","info=a.gross_info.state(at),alpha=a.robust_alpha)")
DECISION_OLD=inspect.getsource(C.decision);DECISION_NEW=DECISION_OLD.replace('ALPHA*nav',"c['alpha']*nav")
ACCOUNT_OLD=inspect.getsource(C.GrossAccount);ACCOUNT_NEW=ACCOUNT_OLD.replace('ALPHA*','self.robust_alpha*')
assert CONTEXT_NEW!=CONTEXT_OLD and CONTEXT_NEW.replace(',alpha=a.robust_alpha)',')')==CONTEXT_OLD
assert DECISION_NEW.replace("c['alpha']*nav",'ALPHA*nav')==DECISION_OLD
assert ACCOUNT_NEW.replace('self.robust_alpha*','ALPHA*')==ACCOUNT_OLD
env=dict(C.__dict__);env.update(__name__=__name__,__file__=__file__)
exec(compile(CONTEXT_NEW+'\n'+DECISION_NEW+'\n'+ACCOUNT_NEW,str(O/'derived_parameterized_gross.py'),'exec'),env)
context,decision,GrossAccount=env['context'],env['decision'],env['GrossAccount']
route_env=dict(J.__dict__,context=context,snapshot=C.snapshot)
exec(compile(C.NEW_ROUTE,str(O/'derived_route.py'),'exec'),route_env);gross_route=route_env['route']

class Runner(A.Runner):
 def __init__(self,*args,infos,family,fixed_end,labels=None,technical_control=False,**kw):
  assert family in FAMILIES;self.family=family;self._robust_ready=False
  super().__init__(*args,**kw);base=self.accounts['B'];self.accounts={}
  self.arm_config=dict(FAMILIES[family])
  if technical_control:assert family=='cost1';self.arm_config.update(TECH_CONTROL)
  self.active_labels=list(labels or self.arm_config);assert set(self.active_labels)<=set(self.arm_config)
  for label in self.active_labels:
   ma,alpha,cost=self.arm_config[label]
   a=copy.copy(base);a.__dict__=copy.deepcopy({k:v for k,v in base.__dict__.items()if k not in('market','facts')});a.market,a.facts,a.label=base.market,base.facts,label;a.cost_multiplier=cost
   if alpha is not None:a.__class__=GrossAccount;a.robust_alpha=D(alpha);a.gross_info=infos[ma];a.gross_events=[]
   self.accounts[label]=a
  self.fixed_end=fixed_end;self.opportunity_denominators=[];self.integration_policy=POLICY+':'+family+':'+self.rank_mode;self._robust_ready=True;self.assert_native_wiring()
 def assert_native_wiring(self):
  assert self.planning.__func__ is Runner.planning
  assert self.route.__func__ is Runner.route
  expected_open=K.cost_opening if isinstance(self,CostRunner)else J.Runner.opening
  assert self.opening.__func__ is expected_open
  assert self.rank_scores_manifest_sha256==N.SCORES.manifest_sha256
  ready=getattr(self,'_robust_ready',False)
  if ready:assert set(self.accounts)==set(self.active_labels)
  for label,a in self.accounts.items():
   alpha=self.arm_config[label][1]if ready else None
   assert type(a)is(GrossAccount if alpha is not None else J.Account)
   assert not hasattr(a,'capacity_basis')
   budget=N.BASE.NoAccountBudget if getattr(self,'_cap_bootstrap',False)else A.NoConfirmed60Budget
   assert type(a.budget)is budget
   if not getattr(self,'_cap_bootstrap',False):assert a.budget.request.__func__ is P.MOD.Contract.request
   if ready:
    assert a.cost_multiplier==self.arm_config[label][2]
    if alpha is not None:assert a.robust_alpha==D(alpha)and a.gross_info.ma_window==self.arm_config[label][0]
   for name in('sync','cancel_buy','fill_exit','split','assert_budget_view','expire_day_buys'):assert getattr(a,name).__func__ is getattr(J.Account,name)
 def route(self,a,intent,x,at):return P.ROUTES[True](self,a,intent,x,at)if type(a)is J.Account else gross_route(self,a,intent,x,at)
 def planning(self,at):
  first=len(self.opportunities);N.Runner.planning(self,at);rows=self.opportunities[first:]
  self.opportunity_denominators.append(dict(at=at,full_rows=len(rows),retained_role_candidates=sum(bool(x['roles'])for x in rows),accounts=len(self.accounts)))
  self.opportunities[first:]=[x for x in rows if x['roles']]
 def restore(self,path):
  starts=dict(self.episode_starts);end=self.fixed_end;infos={k:a.gross_info for k,a in self.accounts.items()if type(a)is GrossAccount}
  result=A.Runner.restore(self,path);assert self.fixed_end==end
  assert all(k in starts and starts[k]==v for k,v in self.episode_starts.items());self.episode_starts=starts
  for k,p in infos.items():
   old=self.accounts[k].gross_info;assert old.path==p.path and old.sha256==p.sha256 and old.ma_window==p.ma_window and old.expected_closes==p.expected_closes
   assert old.clocks==p.clocks[:len(old.clocks)];self.accounts[k].gross_info=p
  self.assert_native_wiring();return result
 def dump_joint(self,path):
  N.Runner.dump_joint(self,path)
  for label,a in self.accounts.items():
   if type(a)is GrossAccount:IO.write_gzip_jsonl(Path(path)/(label+'-gross-admission-events.jsonl.gz'),a.gross_events,encoder=J.C.encoded)
  IO.write_gzip_jsonl(Path(path)/'opportunity-denominators.jsonl.gz',self.opportunity_denominators,encoder=J.C.encoded)

class CostRunner(Runner):opening=K.cost_opening
