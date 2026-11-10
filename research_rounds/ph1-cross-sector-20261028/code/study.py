"""PH1 adapter; original signals, execution engine and Decimal ledger retained."""
from ph_common import *
from decimal import Decimal as D
from dataclasses import replace
import math
import phase_policy

def setup(sector,variant,root,cutoff=None):
 assert variant in VARIANTS
 prior=load('ph_prior_study',SA/'code/study.py')
 R=prior.setup(sector,'AMT',root,cutoff)
 E=sys.modules['experiment'].E
 Parent=R.Account;old_override=E.risk_policy.override
 fast={sid:pd.read_parquet(FAST[sector]/f'{sid}.parquet').loc[:cutoff] for sid in pool(sector).symbol}
 events={sid:pd.read_parquet(O/'events'/sector/f'{sid}.parquet').loc[:cutoff] for sid in pool(sector).symbol}
 risk_sizing=variant.startswith('R_');exit_policy=variant.split('_',1)[1]
 def stamp(day):
  return pd.Timestamp(str(day)[:10]+' 15:00:00',tz='Asia/Shanghai').isoformat() if day is not None and not pd.isna(day) else None

 class Account(Parent):
  def __init__(self,*args,**kw):
   super().__init__(*args,**kw);self.ph_states={};self.ph_seq=0
  def reserve_budget(self,**kw):
   original_budget=D(kw['gross_budget_cny']);quote=kw['quote'];at=kw['clock'].decision_at;sid=quote.security_id
   planned=None
   if risk_sizing:
    floor_signal=self.facts.floor(sid,at,self.mode);factor=self.facts.factor(sid,at)
    if floor_signal is None or quote.raw_price<=floor_signal/factor:
     self.log('ph_risk_reject',at,sid=sid,reason='support_invalid');self.counts['ph_risk_reject_support']+=1;return False,'ph_risk_support_invalid'
    price=quote.raw_price*(1+D('.0005')*self.cost_multiplier);cap=int(original_budget/price)
    q=quote.quantity.buy_floor(self.risk_cap(quote,cap,price,floor_signal/factor,self.current_nav*D('.01')))
    if not q:
     self.log('ph_risk_reject',at,sid=sid,reason='minimum_quantity');self.counts['ph_risk_reject_minimum']+=1;return False,'ph_risk_minimum_quantity'
    kw['gross_budget_cny']=min(original_budget,q*price);kw['target_shares_cap']=min(kw.get('target_shares_cap',q),q)
    planned=dict(reference_price=price,target_shares=q,original_budget=original_budget,nominal_loss=self.loss(quote,q,price,floor_signal/factor),R_a=self.current_nav*D('.01'))
   ok,oid=super().reserve_budget(**kw)
   if ok and planned:
    self.log('ph_risk_reservation',at,sid=sid,order_id=oid,variant=variant,**planned)
   return ok,oid
  def fill_buy(self,sid,w):
   order=self.buys.get(sid)
   if order is None:return None
   z=self.intents[order.order_id];quote=replace(order.quote,fees=w.fees,quantity=w.quantity)
   floor=D(z['floor_signal'])/self.facts.factor(sid,w.at)
   if risk_sizing and w.raw_open>floor:
    remaining_budget=max(D(0),D(z['budget'])-order.local_notional)
    cap=min(order.remaining_shares,int(remaining_budget/w.execution_price))
    q=self.risk_cap(quote,cap,w.execution_price,floor,D(z['risk_budget']),order)
    if not order.submitted_remaining:q=w.quantity.buy_floor(q)
    if not q:
     self.log('ph_risk_open_reject',w.at,sid=sid,order_id=order.order_id,reason='risk_or_amount_below_minimum');self.counts['ph_risk_open_reject']+=1;self.cancel_buy(sid);self.rearm.add(sid);return None
    if q<order.remaining_shares:
     self.log('ph_risk_open_cap',w.at,sid=sid,order_id=order.order_id,previous=order.remaining_shares,shares=q)
     order.remaining_shares=q;order.submitted_remaining=min(order.submitted_remaining,q)
   filled=super().fill_buy(sid,w)
   if not filled:return filled
   if risk_sizing:
    nominal=self.loss(quote,0,w.execution_price,floor,order)
    assert nominal<=D(z['risk_budget'])+D('1e-8')
    assert order.local_notional<=D(z['budget'])+D('1e-8')
    self.log('ph_risk_fill_check',w.at,sid=sid,order_id=order.order_id,variant=variant,filled_shares=order.filled_shares,gross=order.local_notional,buy_fees=sum(order.fees_local.values(),D(0)),nominal_loss=nominal,R_a=z['risk_budget'],budget=z['budget'],floor_raw=floor)
   if variant!='A_E0' and sid not in self.ph_states:
    self.ph_seq+=1
    state=dict(phase='E0' if exit_policy=='E0' else 'TRIAL',P=float(z['floor_signal']),L_star=None,E_entry=float(z['floor_signal']),entry_at=w.at.isoformat(),entry_segment=str(self.facts.row(sid,w.at).segment_id),cycle_id=f'{sid}:{self.ph_seq}',order_id=order.order_id,R_a=str(z['risk_budget']),Loss_fill=str(self.loss(quote,0,w.execution_price,floor,order)))
    self.ph_states[sid]=state
    self.log('ph_cycle_start',w.at,sid=sid,variant=variant,quantity=self.quantity(sid),**state)
   elif variant!='A_E0':
    self.ph_states[sid]['Loss_fill']=str(self.loss(quote,0,w.execution_price,floor,order))
    self.log('ph_cycle_fill',w.at,sid=sid,variant=variant,quantity=self.quantity(sid),**self.ph_states[sid])
   return filled
  def fill_exit(self,sid,w):
   result=super().fill_exit(sid,w)
   if sid in self.ph_states and not self.quantity(sid):
    s=self.ph_states.pop(sid);self.log('ph_cycle_end',w.at,sid=sid,variant=variant,**s)
   return result

 def override(a,stocks,clock,mode,Fact):
  if exit_policy=='E0':return old_override(a,stocks,clock,mode,Fact)
  at=clock.decision_at;day=pd.Timestamp(at.date());result=[]
  for s in stocks:
   sid=s.security_id
   if not a.quantity(sid):
    result.append(s);continue
   assert sid in a.ph_states,(sid,at,'held without phase')
   state=a.ph_states[sid];f=a.facts.f[sid];today=day in f.index
   row=a.facts.row(sid,at);up=bool(row.i_target);on=bool(a.risk_state['on']);locked=sid in a.exits
   assert str(row.segment_id)==state['entry_segment'],(sid,at,'held across undefined source segment')
   if not today and on and up and not locked:
    result.append(s);continue
   j=f.index.searchsorted(day,side='right')-1
   er=events[sid].loc[day] if today else None;fr=fast[sid].loc[day] if day in fast[sid].index else None
   obs=dict(at=at.isoformat(),close=float(row.close),E=float(row.i_floor),E_prev=float(f.iloc[j-1].i_floor) if j>0 else None,E_up=bool(er is not None and er['event']==1),pivot=float(er['pivot']) if er is not None and np.isfinite(er['pivot']) else None,pivot_at=stamp(er['pivot_date']) if er is not None else None,F_up=bool(fr is not None and fr['event']==1),F_pivot=float(fr['pivot']) if fr is not None and np.isfinite(fr['pivot']) else None,F_pivot_at=stamp(fr['pivot_date']) if fr is not None else None,risk_on=on,original_up=up,exit_pending=locked)
   # On missing observations only already known structural/account/locked exits apply.
   if not today:obs.update(E_up=False,F_up=False)
   out=phase_policy.step(state,obs,'F' if exit_policy=='F' else 'PH')
   a.ph_states[sid]=out['state'];diag=out['diagnostic']
   a.log('ph_checkpoint',at,sid=sid,variant=variant,cycle_id=state['cycle_id'],quantity=a.quantity(sid),observed=today,mature=diag['handoff'],obs=obs,state_before=state,state_after=out['state'],**diag)
   if diag['exit_required']:
    s=replace(s,trend_up=Fact(False,at,at,source_id='ph1_'+str(diag['exit_reason'])))
   result.append(s)
  return old_override(a,tuple(result),clock,mode,Fact)
 R.Account=Account;E.risk_policy.override=override
 return R

def main(sector,variant,stage):
 root=O/sector/variant;root.mkdir(parents=True,exist_ok=True)
 link=root/'execution-rules-v2.json'
 if not link.exists():link.symlink_to(PRIOR/'execution-rules-v2.json')
 if stage=='economic':
  assert read(O/'admission.json')['passed']
  for path,h in read(O/'freeze.json')['sha256'].items():assert sha(path)==h,path
 end='2024-03-13' if stage=='short' else '2026-06-30' if stage=='prefix' else END
 R=setup(sector,variant,root,end if stage=='prefix' else None)
 R.run(root/({'short':'technical/short-v2','prefix':'technical/prefix','economic':'accounts-v2'}[stage]),modes=['S'],stresses=['base','cost2','delay1'],start='2023-12-29',end=end,cutoff=end if stage=='prefix' else None,technical=stage!='economic')
if __name__=='__main__':main(*sys.argv[1:])
