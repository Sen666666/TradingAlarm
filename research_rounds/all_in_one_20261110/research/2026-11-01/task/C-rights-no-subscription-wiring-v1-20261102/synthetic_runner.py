"""Generated native mixed-order fixture only. No history loader/import/restore."""
from pathlib import Path
from datetime import datetime,timedelta,date
from decimal import Decimal
import ast,hashlib,json,sys
HERE=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
ENGINE=W/'g-s-C-native-mixed-order-v1-20261102'
deps=json.loads((HERE/'DEPENDENCIES.json').read_text())
for path,h in deps['original_sources'].items():
 if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=h:raise ValueError('dependency changed '+path)
sys.path.insert(0,str(ENGINE));import native_c as E
from rights_wiring import NoSubscriptionInputsMixin,NoSubscriptionRunnerMixin

# Exercise the real original ordinary support check without constructing its loader.
lp=W/'g-s-readonly-historical-loader-r2-20261101/loader.py'
tree=ast.parse(lp.read_text());klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='HistoricalInputs')
method=next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name=='check_action_support')
class UnsupportedInput(ValueError):pass
ns={'Decimal':Decimal,'UnsupportedInput':UnsupportedInput};exec(compile(ast.Module(body=[method],type_ignores=[]),str(lp)+'::ordinary_check_only','exec'),ns)
class OrdinaryInputs:
 check_action_support=ns['check_action_support']
class FixtureInputs(NoSubscriptionInputsMixin,OrdinaryInputs):
 def __init__(self):self.ids=[];self.days=['2025-07-01','2025-07-02','2025-07-03','2025-07-04'];self.packets={};self.facts={}
 def actions(self,day):return self.packets.get(day,[])
 def rows(self,key,sid,day,exact=False):return self.facts.get((sid,day))
class FixtureMarket(E.Market):
 def refresh(self,at):
  self.refresh_calls=getattr(self,'refresh_calls',0)+1
  for sid in self.inputs.ids:
   f=self.inputs.rows('facts',sid,at.date().isoformat(),True)
   if f:
    self.factors[sid]=E.D(str(f['factor']));self.prices[sid]=E.D(str(f['raw_price']));self.known[sid]=at
    if getattr(self,'factor_fault',False):self.factors[sid]*=2
class SyntheticRightsRunner(NoSubscriptionRunnerMixin,E.Runner):
 def __init__(self,mode='C10'):
  super().__init__(mode);self.inputs=FixtureInputs();self.action_log=[];self.events=[];self.ordinary_calls=[]
  self.account.market.__class__=FixtureMarket;self.account.market.inputs=self.inputs
 def execution_guard(self,day):
  if day not in self.inputs.days:raise ValueError('synthetic fixture date only')
 def _rights_ordinary_dispatch(self,day):
  for a in self.inputs.actions(day):self.inputs.check_action_support(a,[])
  self.ordinary_calls.append(day);return 'original_ordinary_delegate'
 def assert_observers(self):
  super().assert_observers()
  if getattr(self,'observer_fault',False):raise ValueError('synthetic observer refusal')
 def source_binding(self):
  out=super().source_binding()
  for name in ('synthetic_runner.py','DEPENDENCIES.json'):
   p=HERE/name;out[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
  return out

def op(n):return datetime.fromisoformat(['2025-07-01','2025-07-02','2025-07-03','2025-07-04'][n]+'T09:30:00+08:00')
def cl(n):return op(n).replace(hour=15,minute=10)
def fixture(mode='C10',sid='SYN_RIGHTS'):
 r=SyntheticRightsRunner(mode);a=r.account;a.mark(sid,100,cl(0)-timedelta(minutes=1),'SYN_SECTOR',False,95);r.inputs.ids=[sid]
 return r,sid
def packet(r,sid,n,valid=True):
 a=r.account;payload=json.dumps(dict(sid=sid,confirmed=cl(n).isoformat(),synthetic=True),sort_keys=True)
 c=E.N.HistoricalReceipt('synthetic-rights|'+sid+'|'+str(n),sid,cl(n)-timedelta(days=1),cl(n),cl(n),(0,1),source='synthetic_causal_CP1_interface',payload_json=payload,payload_sha256=hashlib.sha256(payload.encode()).hexdigest(),source_binding='synthetic-explicit-input-v1') if valid else None
 if c:a.receipt_registry[c.event_id]=E.digest(E.asdict(c))
 return {sid:dict(known_at=cl(n),close=a.market.prices[sid],i_valid=valid,q=valid,core_event=valid,receipt=c,cp_floor=a.facts.floors[sid],i_floor=a.facts.floors[sid],priority=(0,0,sid),structure=(0,1))}
def close(r,sid,n,valid=True):
 obs={}
 if n==0:
  source=E.F1.Source('synthetic-rights','generated-price','explicit-breadth','frozen-kernel')
  r.f1['G']=E.F1.State('G',source=source,previous_close=100,prior_closes=(100,)*63,prior_abs_returns=(.01,)*63);r.f1seq['G']=0
  obs={'G':E.F1.Observation(cl(n).isoformat(),source,101,.8)}
 return r.event(cl(n),observations=obs,stocks=packet(r,sid,n,valid),next_open=op(n+1),industry_evidence=dict(day=cl(n).date().isoformat(),known_at=cl(n).isoformat(),industry_H1={'SYN_SECTOR':90}))
def generated_event(sid,day='2025-07-03',ratio='0.30',price='20'):
 rr=E.D(ratio);sp=E.D(price)
 return dict(sid=sid,effective_date=day,known_action_date=day,source_id=hashlib.sha256((sid+'|'+day+'|fixture').encode()).hexdigest(),classification='rights_issue_no_subscription',holder_election='do_not_subscribe_no_cash_debit_no_extra_holder_shares',modeling_basis='declared_research_proxy',cash_per_old_share='0',split_ratio='1',volume_split_ratio='1',rights_ratio=str(rr),subscription_price=str(sp),signal_cash_per_old_share=str(-rr*sp),signal_split_ratio=str(1+rr),paid_at=None,new_shares_sellable_at=None)
def install(r,sid,day='2025-07-03',ratio='0.30',price='20'):
 e=generated_event(sid,day,ratio,price);old=r.account.market.prices[sid];oldfactor=r.account.market.factors[sid]
 theoretical=(old-E.D(e['signal_cash_per_old_share']))/E.D(e['signal_split_ratio']);factor=oldfactor*old/theoretical
 r.inputs.packets[day]=[e];r.inputs.facts[sid,day]=dict(factor=str(factor),raw_price=str(theoretical));return e
