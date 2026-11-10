"""R1 research policy over frozen B_diag; original signals/execution untouched."""
from pathlib import Path
from types import SimpleNamespace
import inspect,sys,textwrap
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'account-risk-ablation-20261031'))
import adapter as BASE
J=BASE.J;L=BASE.L;D=J.D

def annotate_candidate(self,a,i,source_Q):
 """Defer only a new, flat mobile opportunity; this is not a funded order."""
 if not self.r1_enabled or i['role']!='mobile' or source_Q is not True:return
 if not a.risk_state['on'] or a.quantity(i['sid']) or i['sid'] in a.buys or i['sid'] in a.exits:return
 s=a.budget.sectors.get(self.sector_by_sid[i['sid']])
 if not s or not s.active or s.level<1:return
 full=D('.02')*a.current_nav
 # Never mistake a cash/risk/stock/sector-clipped remainder for the full target.
 if i['budget']!=full:return
 i['R1_decision_nav']=a.current_nav;i['R1_full_target']=full;i['R1_max_gross']=full*2
 if i['cap']==0:i['R1_deferred_unfunded_intent']=True

def preview_with_r1(self,a,i,op,factor,rule,schedule):
 x,why=J.LR.preview(i,op,factor,rule,schedule)
 if x is not None or not self.r1_enabled:return x,why
 if why!='open_minimum_exceeds_frozen_contract' or 'R1_full_target' not in i:return x,why
 if a.quantity(i['sid']) or i['sid'] in a.buys or i['sid'] in a.exits:return None,'R1_actual_position_or_order_responsibility'
 s=a.budget.sectors.get(self.sector_by_sid[i['sid']])
 if not s or not s.active or s.level<1:return None,'R1_confirmed_required'
 p=op*(D(1)+J.LR.SLIP);minimum_gross=D(rule.buy_minimum)*p
 # All prices here are the original opening-known preview, NOT a future fill.
 if minimum_gross<=i['R1_full_target']:return None,'R1_full_target_not_below_minimum'
 if minimum_gross>i['R1_max_gross']:return None,'R1_one_unit_exceeds_four_percent_decision_NAV'
 trial=dict(i,budget=i['R1_max_gross'],cap=rule.buy_minimum,R1_exception=True,
  R1_open_preview_gross=minimum_gross,R1_minimum_quantity=rule.buy_minimum)
 x,why=J.LR.preview(trial,op,factor,rule,schedule)
 if why:return x,why
 assert x['maxq']==rule.buy_minimum
 i.update(trial);x['i']=i
 self.r1_previews.append(dict(at=str(i['clock'].earliest_execution_at),signal_at=str(i['clock'].decision_at),sid=i['sid'],CP1_id=i['CP1_id'],decision_NAV=i['R1_decision_nav'],full_target=i['R1_full_target'],max_gross=i['R1_max_gross'],opening_preview_price=p,minimum_quantity=rule.buy_minimum,minimum_gross=minimum_gross))
 return x,None

def record_r1(self,a,i,x,at,q,pool):
 if not i.get('R1_exception'):return
 self.r1_reservations.append(dict(at=at,signal_at=i['clock'].decision_at,sid=i['sid'],CP1_id=i['CP1_id'],budget_order=i['budget_order'],quantity=q,pool=pool,decision_NAV=i['R1_decision_nav'],full_target=i['R1_full_target'],max_gross=i['R1_max_gross'],preview_gross=D(q)*x['price'],preview_price=x['price'],floor_raw=x['floor']))

def method_source(fn):
 lines=textwrap.dedent(inspect.getsource(fn)).splitlines()
 return lines[0]+'\n'+'\n'.join(' '+line for line in lines[1:])+'\n'

def route_source(base):
 source=(BASE.O/'route_without_account_check.py').read_text() if base is BASE.Runner.route else method_source(base)
 old="  routes=['probe']\n  if role=='mobile' and b.expand and s.level>0:\n   if b.migrate(sector):a.pools_from_model();routes.append('confirmed')"
 new="""  if i.get('R1_exception'):
   if role!='mobile' or not b.expand or s.level<1:return None,'R1_confirmed_required'
   if a.quantity(sid) or sid in a.buys or sid in a.exits:return None,'R1_actual_position_or_order_responsibility'
   if maxq!=rule.buy_minimum:return None,'R1_not_exactly_one_minimum_unit'
   if rule.buy_minimum*x['price']>i['R1_max_gross']:return None,'R1_one_unit_exceeds_four_percent_decision_NAV'
   if not b.migrate(sector):return None,'R1_confirmed_unfunded'
   a.pools_from_model();routes=['confirmed']
  else:
   routes=['probe']
   if role=='mobile' and b.expand and s.level>0:
    if b.migrate(sector):a.pools_from_model();routes.append('confirmed')"""
 assert source.count(old)==1
 source=source.replace(old,new)
 old="i.update(budget_order=bid,pool=pool);return(q,pool),None"
 new="i.update(budget_order=bid,pool=pool);self.record_r1(a,i,x,at,q,pool);return(q,pool),None"
 assert source.count(old)==1
 return source.replace(old,new)

def compile_function(source):
 env=dict(J.__dict__);exec(source,env);return env[source.split('def ',1)[1].split('(',1)[0]]

PLANNING=method_source(J.Runner.planning)
needle="     if role=='core':LR.resize_core(i,a.current_nav,self.facts.factor(sid,at))\n     if not i.get('size_reject') and i['cap']>0:a.pending.append(i)"
replacement="     if role=='core':LR.resize_core(i,a.current_nav,self.facts.factor(sid,at))\n     if role=='mobile':self.annotate_candidate(a,i,continuing[sid].q)\n     if (not i.get('size_reject') and i['cap']>0) or i.get('R1_deferred_unfunded_intent'):a.pending.append(i)"
assert PLANNING.count(needle)==1
PLANNING=PLANNING.replace(needle,replacement)
OPENING=method_source(J.Runner.opening)
needle="x,why=LR.preview(i,D(str(raw.loc[day].open)),self.facts.factor(sid,at),self.market.quantity(sid,at),self.market.fees(sid,at))"
replacement="x,why=self.preview_with_r1(a,i,D(str(raw.loc[day].open)),self.facts.factor(sid,at),self.market.quantity(sid,at),self.market.fees(sid,at))"
assert OPENING.count(needle)==1
OPENING=OPENING.replace(needle,replacement)
ROUTE_DIAG=route_source(BASE.Runner.route)
ROUTE_ORIGINAL_ACCOUNT_CHECK=route_source(J.Runner.route)

class Runner(BASE.Runner):
 def __init__(self,*args,r1_enabled=True,**kwargs):
  self.r1_enabled=r1_enabled;self.r1_previews=[];self.r1_reservations=[]
  super().__init__(*args,**kwargs)
 annotate_candidate=annotate_candidate
 preview_with_r1=preview_with_r1
 record_r1=record_r1
 planning=compile_function(PLANNING)
 opening=compile_function(OPENING)
 route=compile_function(ROUTE_DIAG)

# Only the synthetic fixture uses this original-account-cap route. History uses
# Runner above, which inherits precisely the frozen B_diag account policy.
route_with_original_account_check=compile_function(ROUTE_ORIGINAL_ACCOUNT_CHECK)

def save_source_views():
 for name,source in [('planning_r1.py',PLANNING),('opening_r1.py',OPENING),('route_r1_diag.py',ROUTE_DIAG),('route_r1_original_account_fixture.py',ROUTE_ORIGINAL_ACCOUNT_CHECK)]:
  (O/name).write_text(source)

