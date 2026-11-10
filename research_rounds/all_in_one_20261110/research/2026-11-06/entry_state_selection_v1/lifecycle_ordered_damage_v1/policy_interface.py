"""Decision-only research interface; no orders, account loading, or automatic execution.
Native caller supplies legal fresh intents, role-specific floors, fees and share lattice.
Unknown lifecycle remains UNKNOWN; caller must not silently fill it as best or worst.
"""
from dataclasses import dataclass, field
from math import isfinite, exp
from typing import Callable, Iterable

def risk_allowance(*,equity:float,health:float,loss_debt:float,is_add:bool,
                   original_intent_live:bool,fresh_cp:bool=False,
                   old_mark_net:float=0.,old_stress_net:float=0.,
                   frozen_campaign_cap:float=0.) -> float | None:
    """Call at signal close and next permitted OPEN; native eligibility never synthesized.
    For ADD, old_mark_net excludes newly proposed shares and all expected selling fees.
    fresh_cp must refer to a newly issued, unconsumed native receipt ID.
    """
    if not isfinite(health):return None
    if not original_intent_live or equity<=0:return 0.
    if not 0<health<=1 or loss_debt<0:raise ValueError('invalid state')
    if not is_add:return .001*equity*health/(1+loss_debt/(.005*equity))
    if not fresh_cp or old_mark_net<=0:return 0.
    capacity=max(0.,frozen_campaign_cap+old_stress_net)
    return health*min(.0025*equity,.5*old_mark_net,capacity)

def size_at_price(*,price:float,role_floor:float,sigma:float,risk_budget:float|None,
                  share_lattice:Iterable[int],buyfee:Callable[[int,float],float],
                  sellfee:Callable[[int,float],float],cash:float,
                  gross_room:float,signal_qcap:int|None=None) -> int|None:
    """Use prior-known same-coordinate role floor/sigma; OPEN only shrinks qcap.
    No High/Low/Close/Amount of execution day is an argument.
    quantity lattice and costs must come from native dated execution rules.
    """
    if risk_budget is None:return None
    if not all(isfinite(x)for x in [price,role_floor,sigma,risk_budget,cash,gross_room]):return None
    if price<=role_floor or role_floor<=0 or sigma<0 or risk_budget<=0:return 0
    X=role_floor*exp(-2*sigma)*(1-.0005)
    allowed=[]
    for q in share_lattice:
        if q<=0:continue
        if signal_qcap is not None and q>signal_qcap:continue
        cost=q*price+buyfee(q,price)
        R=q*(price-X)+buyfee(q,price)+sellfee(q,X)
        if R<=risk_budget and cost<=cash and q*price<=gross_room:allowed.append(q)
    return max(allowed,default=0)

@dataclass
class SharedTrialBucket:
    """Reusable prior research bucket; not a new predictor or worst-case bound."""
    balance:float
    reservations:dict[str,float]=field(default_factory=dict)
    debts:dict[str,float]=field(default_factory=dict)
    @classmethod
    def initial(cls,equity:float):return cls(.01*equity)
    def day_open(self,prior_equity:float):
        self.balance=min(.01*prior_equity,self.balance+.0001*prior_equity)
    def available(self):return max(0.,self.balance-sum(self.reservations.values()))
    def reserve(self,key:str,principal_risk:float):
        if key in self.reservations:raise ValueError('duplicate obligation')
        if principal_risk<0 or principal_risk>self.available():return False
        self.reservations[key]=principal_risk;return True
    def replace_after_fill(self,key:str,remaining_principal_risk:float):
        if key not in self.reservations:raise KeyError(key)
        if remaining_principal_risk<0:raise ValueError('negative reservation')
        # A realized risk overshoot is retained, never erased to manufacture free credit.
        self.reservations[key]=remaining_principal_risk
    def closed_campaign(self,key:str,sid:str,realized_net:float):
        self.reservations.pop(key)
        self.balance+=realized_net if realized_net<0 else .5*realized_net
        self.debts[sid]=max(0.,self.debts.get(sid,0.)-realized_net)

if __name__=='__main__':
    E=1_200_000
    p=risk_allowance(equity=E,health=.8,loss_debt=0,is_add=False,original_intent_live=True)
    assert p==960
    assert risk_allowance(equity=E,health=.8,loss_debt=6000,is_add=False,original_intent_live=True)==480
    assert risk_allowance(equity=E,health=.8,loss_debt=0,is_add=True,original_intent_live=True,fresh_cp=True,old_mark_net=-1,old_stress_net=1000,frozen_campaign_cap=960)==0
    assert risk_allowance(equity=E,health=.8,loss_debt=0,is_add=True,original_intent_live=True,fresh_cp=True,old_mark_net=4000,old_stress_net=-200,frozen_campaign_cap=960)==608
    kw=dict(role_floor=9.,sigma=.02,risk_budget=960,share_lattice=range(100,10000,100),buyfee=lambda q,p:5.,sellfee=lambda q,p:5.,cash=100000,gross_room=100000)
    q0=size_at_price(price=10.,**kw)
    assert size_at_price(price=11.,signal_qcap=q0,**kw)<=q0
    assert size_at_price(price=9.,signal_qcap=q0,**kw)==0
    assert risk_allowance(equity=E,health=float('nan'),loss_debt=0,is_add=False,original_intent_live=True)is None
    b=SharedTrialBucket.initial(E);assert b.reserve('campaign1',960);assert b.available()==11040
    b.closed_campaign('campaign1','X',-1500);assert b.balance==10500 and b.debts['X']==1500
    assert b.reserve('campaign2',600);b.closed_campaign('campaign2','X',-12000)
    assert b.balance==-1500 and b.available()==0 and b.debts['X']==13500
    b.day_open(E);assert b.balance==-1380
    print('PASS 12 explicit decision, price, no-losing-add, debt and unknown invariants; no account run.')
