"""Frozen reference engines; cost2 existing-interface adapter only."""
from pathlib import Path
import inspect,textwrap
from initialization_guard import IO
import check_contract as P
BASE=P.BASE;J=P.J;L=BASE.L;O=Path(__file__).resolve().parent

OPENING=textwrap.dedent(inspect.getsource(J.Runner.opening))
assert OPENING.count("self.market.window(sid,at,'sell',1)")==1
assert OPENING.count("self.market.window(sid,at,'buy',1)")==1
OPENING=OPENING.replace("self.market.window(sid,at,'sell',1)","self.market.window(sid,at,'sell',a.cost_multiplier)").replace("self.market.window(sid,at,'buy',1)","self.market.window(sid,at,'buy',a.cost_multiplier)")
environment=dict(J.__dict__);exec(OPENING,environment)

class PressureBase(L.PreparedRunner):
 def __init__(self,*args,cost=2,delay=0,**kwargs):
  if delay:raise ValueError('independent mobile delay policy is not frozen; delay path gated')
  self.pressure_cost=cost;self.pressure_delay=delay
  super().__init__(*args,policies=('B',),**kwargs)
  for a in self.accounts.values():
   a.cost_multiplier=cost;a.delay_events=delay
   if self.reference=='B_diag':BASE.enable(a)
  assert self.planning.__func__ is J.Runner.planning
 opening=environment['opening']
 def checkpoint(self,out,last_event):
  import shutil
  super().checkpoint(out,last_event);out=Path(out);day=str(last_event.date())
  if day in ('2025-09-30','2025-12-31','2026-03-31'):
   for suffix in ('pkl','json'):shutil.copyfile(out/('checkpoint.'+suffix),out/('checkpoint-'+day+'.'+suffix))
 def restore(self,path):
  expected=(self.reference,self.pressure_cost,self.pressure_delay)
  after=super().restore(path)
  assert (self.reference,self.pressure_cost,self.pressure_delay)==expected
  assert all(a.cost_multiplier==expected[1] and a.delay_events==expected[2] for a in self.accounts.values())
  return after
class B3CostRunner(PressureBase):
 reference='B3';route=J.Runner.route
class DiagCostRunner(PressureBase):
 reference='B_diag';route=BASE.Runner.route

def assert_identity(runner,reference):
 assert runner.planning.__func__ is J.Runner.planning
 assert runner.opening.__func__ is PressureBase.opening
 assert runner.route.__func__ is (J.Runner.route if reference=='B3' else BASE.Runner.route)
 assert all(a.cost_multiplier==2 and a.delay_events==0 for a in runner.accounts.values())

def empty(cls):
 r=cls.__new__(cls);r.pressure_cost=2;r.pressure_delay=0
 for n in ['daily','opportunities','funding','stage_events','balance_audit']:setattr(r,n,[])
 r.accounts={};r.source_freeze={};return r
