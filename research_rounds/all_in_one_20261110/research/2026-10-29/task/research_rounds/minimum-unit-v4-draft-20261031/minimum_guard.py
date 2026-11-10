"""Synthetic minimum-unit contract only; not a sizing/ledger/execution engine."""
from dataclasses import dataclass,field
from decimal import Decimal as D
from copy import deepcopy

@dataclass
class Holding:
 stock:str; sector:str; pool:str; qty:int; mark:D; floor:D; role:str='core'; sell_pending:bool=False
@dataclass
class Pending:
 stock:str; sector:str; pool:str; qty:int; limit:D; floor:D; fee:D; status:str='open'
@dataclass
class View:
 nav:D=D(1000000)
 holdings:list=field(default_factory=list)
 orders:list=field(default_factory=list)
 noncash_equity:D=D(0)
 consumed:set=field(default_factory=set)
 def __post_init__(self):self.available=self.nav-self.noncash_equity-sum((h.qty*h.mark for h in self.holdings),D(0))-sum((o.qty*o.limit+o.fee for o in self.orders),D(0))
 def resources(self,pool=None,sector=None):
  hs=[h for h in self.holdings if (pool is None or h.pool==pool) and (sector is None or h.sector==sector)]
  os=[o for o in self.orders if o.status in ('open','cancel_pending') and (pool is None or o.pool==pool) and (sector is None or o.sector==sector)]
  return (sum((h.qty*h.mark for h in hs),D(0))+sum((o.qty*o.limit for o in os),D(0)),
   sum((h.qty*max(h.mark-h.floor,D(0)) for h in hs),D(0))+sum((o.qty*max(o.limit-o.floor,D(0)) for o in os),D(0)))
 def cancel(self,stock):
  for o in self.orders:
   if o.stock==stock:o.status='cancel_pending'
 def cancel_ack(self,stock):
  for o in self.orders:
   if o.stock==stock:
    assert o.status=='cancel_pending';self.available+=o.qty*o.limit+o.fee;o.status='cancelled';o.qty=0;o.fee=D(0)
 def acknowledged_full_clear(self,stock):
  # Synthetic same-mark, zero-fee acknowledged sale, not an execution forecast.
  for h in self.holdings:
   if h.stock==stock:self.available+=h.qty*h.mark;h.qty=0;h.sell_pending=False
 def acknowledged_fill(self,stock):
  for o in self.orders:
   if o.stock==stock and o.status=='open':
    self.holdings.append(Holding(stock,o.sector,o.pool,o.qty,o.limit,o.floor,'mobile'))
    self.nav-=o.fee;o.status='filled';o.qty=0;o.fee=D(0)

def check(view,*,stock='A',sector='S',level=0,unit=100,price=D(100),floor=D(99),fee=D(0),
          receipt='new',fresh=True,Q=True,ACT=True,active=True,allow_target_exception=False,reserve=False):
 """Preview min unit; True exception is an explicitly hypothetical test fixture."""
 if price is None or floor is None:return dict(accepted=False,reason='unknown_price_or_floor')
 if price<=0 or floor<0 or price<=floor:return dict(accepted=False,reason='invalid_price_or_protection')
 if not fresh or receipt in view.consumed:return dict(accepted=False,reason='old_or_consumed_receipt')
 if Q is not True or not ACT or not active:return dict(accepted=False,reason='original_permission')
 if any(o.stock==stock and o.status in ('open','cancel_pending') for o in view.orders) or any(h.stock==stock and h.sell_pending for h in view.holdings):return dict(accepted=False,reason='existing_order_responsibility')
 capital=D(unit)*price;risk=D(unit)*(price-floor);target=view.nav*D('.02');above=capital>target
 held=sum(h.qty for h in view.holdings if h.stock==stock)
 pending_fees=sum((o.fee for o in view.orders if o.status in ('open','cancel_pending')),D(0));budget_nav=view.nav-pending_fees-fee
 reasons={};routes=['probe']+(['confirmed'] if level>0 else [])
 for pool in routes:
  pc,pr=view.resources(pool);sc,sr=view.resources(sector=sector);_,ar=view.resources();fail=[]
  fraction=D('.02') if pool=='probe' else (D('.02'),D('.10'),D('.20'))[level]
  if capital+fee>view.available-view.nav*D('.10'):fail.append('cash_and_original_reserve')
  pool_limit=(D('.10') if pool=='probe' else D('.60'))*budget_nav
  if pc+capital>pool_limit:fail.append('pool_capital')
  if pool=='probe' and pr+risk>D('.005')*budget_nav:fail.append('probe_risk')
  if sc+capital>fraction*budget_nav:fail.append('sector_capital')
  if sr+risk>D('.01')*budget_nav:fail.append('sector_risk')
  if ar+risk>D('.03')*budget_nav:fail.append('account_risk')
  if sum((h.qty*h.mark for h in view.holdings if h.stock==stock),D(0))+capital>D('.10')*view.nav:fail.append('stock_capital')
  reasons[pool]=fail
 feasible=next((p for p in routes if not reasons[p]),None)
 policy_reasons=[]
 if above and held:policy_reasons.append('exception_requires_actual_flat')
 if above and not allow_target_exception:policy_reasons.append('target_exception_policy_not_frozen')
 result=dict(accepted=False,above_target=above,target=target,minimum_gross=capital,hard_reasons=reasons,policy_reasons=policy_reasons,minimum_hard_capacity_feasible=feasible is not None)
 if feasible is None:result['reason']='hard_resource_block';return result
 if above and held:result['reason']='exception_requires_actual_flat';return result
 if above and not allow_target_exception:result['reason']='target_exception_policy_not_frozen';return result
 result.update(accepted=True,reason='hypothetical_one_unit_exception' if above else 'original_target_minimum_feasible',pool=feasible,quantity=unit)
 if reserve:
  view.available-=capital+fee;view.orders.append(Pending(stock,sector,feasible,unit,price,floor,fee));view.consumed.add(receipt)
 return result
