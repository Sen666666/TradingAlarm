"""C1 research policy: one frozen confirmed-pool fraction over B_diag."""
from pathlib import Path
from dataclasses import dataclass,asdict
from decimal import Decimal
import sys,inspect,textwrap,copy,shutil
O=Path(__file__).resolve().parent;W=O.parent
sys.path.insert(0,str(W/'q2-normal-continuation-20261031'))
import continuation as E
J,L,BASE,IO=E.J,E.L,E.BASE,E.IO
D=Decimal

@dataclass
class C1State:
 initial_nav:D
 high:D
 decision_nav:D
 drawdown:D=D(0)
 fraction:D=D('.60')
 decision_at:str=None
 mode:str='C1'
 version:str='C1-close-H-live-cap-v1'
 def observe(self,at,nav):
  nav=D(nav);key=at.isoformat();assert nav>=0 and nav.is_finite()
  if self.decision_at==key:
   assert nav==self.decision_nav,'same decision cannot be repriced';return
  assert self.decision_at is None or key>self.decision_at,'decision clock regressed'
  self.high=max(self.high,nav);self.decision_nav=nav;self.drawdown=max(D(0),D(1)-nav/self.high)
  self.fraction=D('.60') if self.mode=='fixed60' else D('.10')+D('.50')*max(D(0),D(1)-self.drawdown/D('.20'))
  self.decision_at=key;self.validate()
 def validate(self):
  assert self.mode in ('C1','fixed60') and self.high>=self.initial_nav>0 and self.high>=self.decision_nav>=0
  dd=max(D(0),D(1)-self.decision_nav/self.high)
  c=D('.60') if self.mode=='fixed60' else D('.10')+D('.50')*max(D(0),D(1)-dd/D('.20'))
  assert self.drawdown==dd and self.fraction==c

REQUEST_OLD=textwrap.dedent(inspect.getsource(BASE.N.Contract.request))
REQUEST_NEW=REQUEST_OLD.replace('(0.10 if pool == \'probe\' else 0.60)','(0.10 if pool == \'probe\' else self.confirmed_fraction())')
assert REQUEST_NEW!=REQUEST_OLD and REQUEST_OLD.count("(0.10 if pool == 'probe' else 0.60)")==1
env=dict(BASE.N.__dict__);exec(compile(REQUEST_NEW,str(O/'generated_request.py'),'exec'),env);request_c1=env['request']
MIGRATE_OLD=textwrap.dedent(inspect.getsource(J.V.Contract.migrate))
MIGRATE_NEW=MIGRATE_OLD.replace('.60*(self.nav-pending_fees)','self.confirmed_fraction()*(self.nav-pending_fees)')
assert MIGRATE_NEW!=MIGRATE_OLD and MIGRATE_OLD.count('.60*(self.nav-pending_fees)')==1
env=dict(J.V.__dict__);exec(compile(MIGRATE_NEW,str(O/'generated_migrate.py'),'exec'),env);migrate_c1=env['migrate']
ROUTE_OLD=(BASE.O/'route_without_account_check.py').read_text()
ROUTE_NEW=ROUTE_OLD.replace("(.10 if pool=='probe' else .60)","(.10 if pool=='probe' else b.confirmed_fraction())")
assert ROUTE_NEW!=ROUTE_OLD and ROUTE_OLD.count("(.10 if pool=='probe' else .60)")==1
env=dict(J.__dict__);exec(compile(ROUTE_NEW,str(O/'generated_route.py'),'exec'),env);route_c1=env['route']

class Budget(BASE.NoAccountBudget):
 request=request_c1
 def confirmed_fraction(self):return float(self.c1.fraction)
 def migrate(self,sector):return migrate_c1(self,sector) if self.expand else False

def enable(a,mode='C1'):
 assert mode in ('C1','fixed60')
 assert not a.trades and not a.layers and not a.buys,'C1 H cannot be silently seeded into an old account'
 a.budget.__class__=Budget
 a.budget.c1=C1State(D(a.initial_cash),D(a.initial_cash),D(a.initial_cash),mode=mode)

def freeze_close(a,at,nav):
 # Called only in original planning after native close NAV, before ACT step.
 # Never assigns account.current_nav, mirror equity, cash, marks or ACT peak.
 a.budget.c1.observe(at,D(nav))

PLANNING_OLD=textwrap.dedent(inspect.getsource(J.Runner.planning))
needle="a.current_nav=a.balance(at,self.market.marks(at,a.positions))['nav'];M.E.risk_policy.step"
assert PLANNING_OLD.count(needle)==1
PLANNING_NEW=PLANNING_OLD.replace(needle,"a.current_nav=a.balance(at,self.market.marks(at,a.positions))['nav'];freeze_close(a,at,a.current_nav);M.E.risk_policy.step")
env=dict(J.__dict__,freeze_close=freeze_close);exec(compile(PLANNING_NEW,str(O/'generated_planning.py'),'exec'),env);planning_c1=env['planning']

class Runner(L.PreparedRunner):
 route=route_c1
 def __init__(self,*args,mode='C1',**kw):
  super().__init__(*args,policies=('B',),**kw)
  self.c1_mode=mode;self.c1_rows=[]
  for a in self.accounts.values():enable(a,mode)
 def planning(self,at):
  planning_c1(self,at)
  for a in self.accounts.values():
   b=a.budget;s=b.c1;assert s.decision_at==at.isoformat() and s.decision_nav==a.current_nav
   fees=sum(o.qty*o.fee_per_share for o in b.orders.values() if o.status in ('open','cancel_pending'))
   capital=b.resources('confirmed')[0];live_nav=b.nav-fees;cap=b.confirmed_fraction()*live_nav
   self.c1_rows.append(dict(at=at,**asdict(s),live_budget_NAV=live_nav,confirmed_cap=cap,confirmed_capital=capital,cap_minus_commitment=cap-capital,over_cap=capital>cap+1e-8,probe_capital=b.resources('probe')[0],pending_fees=fees,ACT=copy.deepcopy(a.risk_state)))
 def checkpoint(self,out,last_event):
  E.env2['checkpoint'](self,out,last_event);out=Path(out);day=str(last_event.date())
  IO.write_json(out/'C1-checkpoint-status.json',J.W.canon(dict(at=last_event,mode=self.c1_mode,accounts={k:dict(NAV=a.current_nav,trades=len(a.trades),C1=asdict(a.budget.c1)) for k,a in self.accounts.items()})))
  if day in {'2022-03-31','2022-06-30','2022-09-30','2022-12-30','2025-09-30','2025-12-31','2026-03-31','2026-06-30'}:
   for suffix in ('pkl','json'):shutil.copyfile(out/('checkpoint.'+suffix),out/('checkpoint-'+day+'.'+suffix))
 def restore(self,path):
  expected=self.c1_mode;at=super().restore(path);assert self.c1_mode==expected
  for a in self.accounts.values():
   assert type(a.budget) is Budget and a.budget.c1.mode==expected;a.budget.c1.validate()
  return at
 def dump_joint(self,path):
  super().dump_joint(path)
  IO.write_json(Path(path)/'C1.json',J.W.canon(dict(mode=self.c1_mode,decisions=self.c1_rows,final={k:asdict(a.budget.c1) for k,a in self.accounts.items()})))

def source_diffs():
 import difflib
 return {name:''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile=name+'_Bdiag',tofile=name+'_C1')) for name,old,new in [('request',REQUEST_OLD,REQUEST_NEW),('migrate',MIGRATE_OLD,MIGRATE_NEW),('route',ROUTE_OLD,ROUTE_NEW),('planning',PLANNING_OLD,PLANNING_NEW)]}

if __name__=='__main__':raise SystemExit('adapter only; no implicit historical run')
