"""Research-only partial actions; original reservation arithmetic, fills and admission."""
from pathlib import Path
import sys,importlib.util,math
from decimal import Decimal as D
from dataclasses import dataclass,replace
from collections import defaultdict
O=Path(__file__).resolve().parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
def load(name,p):
 sp=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(sp);sys.modules[name]=m;sp.loader.exec_module(m);return m
P=load('partial_role_original',RR/'pvr-act-comparison-20261027/code/experiment.py');P.setup('RS');E=P.E;L=E.ledger;A=E.admission;Parent=E.Account
sys.path.insert(0,str(O.parent/'rearm-risk-boundary-design-20261030'));from risk_boundary_v2 import RiskBoundary,NegativeReceipt
ns=dict(vars(L));exec(compile((O/'restore_reservation_kernel.py').read_text(),str(O/'restore_reservation_kernel.py'),'exec'),ns);reserve_kernel=ns['reserve_budget']
RESTORE_BUDGET_STATUS='FROZEN_ORIGINAL_PER_ORDER15_NO_HOLDING_CEILING'

@dataclass(frozen=True)
class FreshI:
 event_id:str
 symbol:str
 known_at:object
 native_i_buy:bool=True

class RoleAccount(Parent):
 def __init__(self,*args,roles_enabled=True,context=None,**kw):
  super().__init__(*args,**kw);self.roles_enabled=roles_enabled;self.role_context=context or (lambda sid,at:f'{sid}|synthetic-E0');self.roles={};self.role_orders={};self.role_events=[];self.consumed_i=set();self.full_signals=set();self.group_cash=defaultdict(D);self.group_dividend=defaultdict(D)
 def check_roles(self):
  if not self.roles_enabled:return
  for sid in set(self.positions)|set(self.roles):
   r=self.roles.get(sid);assert r is not None and r['K']+r['R']==self.quantity(sid),(sid,'role/physical mismatch');assert r['K']>=0 and 0<=r['R']<=r['cap']
 def reserve_budget(self,**kw):
  result=super().reserve_budget(**kw)
  if self.roles_enabled and result[0]:self.role_orders[result[1]]=dict(kind='initial',group=self.role_context(kw['quote'].security_id,kw['clock'].decision_at))
  return result
 def fill_buy(self,sid,window):
  order=self.buys.get(sid);meta=self.role_orders.get(order.order_id) if order else None;z=self.intents.get(order.order_id) if order else None;fill=super().fill_buy(sid,window)
  if self.roles_enabled and fill:
   assert meta;kind=meta['kind'];r=self.roles.get(sid)
   if kind=='initial':
    if r is None:r=dict(K=0,R=0,cap=0,frozen=False,controller=None,group=meta['group'],floor=float(z['floor_signal']),cycle=fill.receipt_id,risk_flat_at=None);self.roles[sid]=r
    assert not r['frozen'],'An initial fill after first role decision needs explicit interface review'
    q=self.quantity(sid);r['R']=window.quantity.sell_floor(q//2,q);r['K']=q-r['R'];r['cap']=r['R']
   else:
    assert r is not None;r['R']+=fill.shares;assert r['R']<=r['cap']
    if r['controller'] is None or r['controller'].phase=='CLOSED':r['controller']=self.new_controller(sid,fill.receipt_id,float(z['floor_signal']))
   self.group_cash[r['group']]-=fill.gross_cny+fill.fees_cny;self.sync(sid);self.role_events.append(dict(kind='actual_role_buy',at=window.at,sid=sid,action=kind,K=r['K'],R=r['R'],cap=r['cap'],group=r['group'],receipt=fill))
  self.check_roles();return fill
 def new_controller(self,sid,cid,floor):
  r=self.roles[sid];return RiskBoundary(cycle_id=cid,symbol=sid,source_id=r['group'],unit_id=r['group'],shares=r['R'],e0_floor=floor,buy_pending=sid in self.buys)
 def sync(self,sid):
  r=self.roles[sid];c=r['controller']
  if c:c.sync_execution(shares=r['R'],buy_pending=sid in self.buys,exit_order_pending=sid in self.exits)
 def close_risk(self,sid,clock,quote,price,*,negative_id=None,sigma=.02,floor=8,factor=1,full_exit=False,event_known=True,floor_known=True):
  if not self.roles_enabled:return None
  self.check_roles();r=self.roles[sid];r['frozen']=True
  if full_exit:self.full_signals.add(sid);self.request_exit(quote,clock)
  if not r['R']:return dict(note='risk_role_empty_no_repeat_sale')
  if r['controller'] is None:r['controller']=self.new_controller(sid,r['cycle'],r['floor'])
  self.sync(sid);bar=clock.decision_at.date().toordinal();neg=NegativeReceipt(negative_id,sid,r['group'],bar) if negative_id else None
  result=r['controller'].on_close(bar=bar,raw_close=price,factor=factor,unit_id=r['group'],negative=neg,sigma=sigma,updated_floor=floor,floor_known=floor_known,event_feed_known=event_known,original_exit=full_exit)
  if r['controller'].exit_locked and r['controller'].exit_reason=='risk_boundary' and sid not in self.exits:self.request_risk_trim(quote,clock)
  self.role_events.append(dict(kind='role_close',at=clock.decision_at,sid=sid,diagnostic=result));return result
 def request_risk_trim(self,quote,clock):
  sid=quote.security_id;r=self.roles[sid]
  if not r['R'] or sid in self.exits:return
  shares=quote.quantity.sell_floor(r['R'],self.quantity(sid))
  if shares<=0:self.role_events.append(dict(kind='trim_quantity_blocked',at=clock.decision_at,sid=sid));return
  L.SectorAccount.request_exit(self,quote,clock);ex=self.exits[sid];ex.remaining_target=shares;ex.purpose='risk_trim';self.sync(sid)
  self.role_events.append(dict(kind='risk_trim_request',sid=sid,at=clock.decision_at,shares=shares))
 def request_exit(self,quote,clock):
  sid=quote.security_id
  if self.roles_enabled and sid in self.exits and self.exits[sid].purpose=='risk_trim':
   if sid not in self.full_signals:return  # Original admission sees a latched partial order, not a new full-exit fact.
   self.exits[sid].remaining_target=None;self.exits[sid].purpose='structure_exit';self.role_events.append(dict(kind='upgrade_full_exit',sid=sid,at=clock.decision_at,shares=self.quantity(sid)))
  super().request_exit(quote,clock)
 def fill_exit(self,sid,window):
  order=self.exits.get(sid);purpose=order.purpose if order else None;fill=super().fill_exit(sid,window)
  if self.roles_enabled and fill:
   r=self.roles[sid];risk=min(r['R'],fill.shares);r['R']-=risk;r['K']-=fill.shares-risk
   if purpose=='risk_trim':assert risk==fill.shares,'Partial action cannot silently consume core'
   self.group_cash[r['group']]+=fill.gross_cny-fill.fees_cny;self.sync(sid);self.role_events.append(dict(kind='actual_role_sell',at=window.at,sid=sid,action=purpose,K=r['K'],R=r['R'],group=r['group'],receipt=fill))
   if purpose=='risk_trim' and not r['R'] and sid not in self.exits:r['risk_flat_at']=window.at
   if not self.quantity(sid):del self.roles[sid];self.full_signals.discard(sid)
  self.check_roles();return fill
 def split(self,**kw):
  r=self.roles.get(kw['sid']);old=dict(r) if r else None;super().split(**kw)
  if self.roles_enabled and old:
   ratio=D(kw['ratio']);r['K']=int(D(old['K'])*ratio);r['R']=int(D(old['R'])*ratio);r['K']+=self.quantity(kw['sid'])-r['K']-r['R'];r['cap']=int(D(old['cap'])*ratio);self.sync(kw['sid']);self.check_roles()
 def accrue_dividend(self,**kw):
  super().accrue_dividend(**kw)
  if self.roles_enabled:
   r=self.roles[kw['sid']];assert kw['currency']=='CNY','Only the authorized A-share role contract is integrated';n=D(kw['net_local']);risk=n*D(r['R'])/self.quantity(kw['sid']);self.group_dividend[r['group']]+=n;self.role_events.append(dict(kind='role_dividend',at=kw['ex_at'],sid=kw['sid'],risk=risk,core=n-risk,event_id=kw['event_id']))
 def restore(self,quote,clock,budget,receipt):
  sid=quote.security_id;r=self.roles[sid];floor=self.facts.floor(sid,clock.decision_at,self.mode)
  if sid in self.buys or sid in self.exits or r['R']>=r['cap']:return False,'role_or_order_occupied'
  cap=r['cap']-r['R'];budget=min(budget,D(cap)*quote.read_price(clock.decision_at)*quote.fx.read(clock.decision_at));ok,oid=reserve_kernel(self,quote=quote,clock=clock,gross_budget_cny=budget,purpose='risk_restore',target_shares_cap=cap,candidate_id=receipt.event_id)
  if ok:
   self.role_orders[oid]=dict(kind='risk_restore',group=r['group']);self.intents[oid]=dict(sid=sid,decision_at=clock.decision_at,floor_signal=floor,risk_budget=self.current_nav*D('.01'),nav=self.current_nav,budget=self.buys[sid].budget_cny);self.log('entry_contract',clock.decision_at,order_id=oid,mode=self.mode,**self.intents[oid]);self.counts['buy_orders']+=1
  return ok,oid

def commit_roles(a,*,clock,securities,sectors,quotes,marks,receipts=None,previous=(),bootstrap=False,completed_exits=(),ACT_on=True):
 factory=lambda **kw:A.decide(clock=clock,variant='S0',securities=securities,sectors=sectors,**kw)
 if not a.roles_enabled:return L.commit_cutoff(a,decision_factory=factory,clock=clock,quotes=quotes,marks=marks,previous=previous,bootstrap=bootstrap,completed_exits=completed_exits)
 # Caller supplies the original ACT override facts; do not create a second ACT state.
 if not ACT_on and any(s.trend_up.read(clock) is True or s.buy_allowed.read(clock,for_execution=True) is True for s in securities):raise ValueError('Original ACT override facts required before role admission')
 stocks={s.security_id:s for s in securities};groups={g.sector_id:g for g in sectors};a.full_signals={sid for sid,s in stocks.items() if s.trend_up.read(clock) is False};d=factory(previous=previous,occupied=a.occupancy(clock.decision_at),bootstrap=bootstrap,completed_exits=completed_exits);resolved={e.security_id:e for e in d.eligibility};receipts=receipts or {};restore_ids=[]
 if ACT_on:
  for sid,r in a.roles.items():
   receipt=receipts.get(sid)
   if not receipt or not receipt.native_i_buy or receipt.symbol!=sid or not receipt.event_id:continue
   if receipt.known_at>clock.decision_at or receipt.known_at.date()!=clock.session_date:continue
   if r['risk_flat_at'] is None or receipt.known_at<=r['risk_flat_at']:continue
   if (sid,receipt.event_id) in a.consumed_i or resolved[sid].q is not True:continue
   if sid in a.buys or sid in a.exits or r['R']>=r['cap'] or (r['controller'] and r['controller'].exit_locked and r['R']>0):continue
   restore_ids.append(sid);a.consumed_i.add((sid,receipt.event_id))
 if not restore_ids:return L.commit_cutoff(a,decision_factory=factory,clock=clock,quotes=quotes,marks=marks,previous=previous,bootstrap=bootstrap,completed_exits=completed_exits)
 # Actual original admission and acknowledgement handle all exits/cancellations.
 a.apply_decision(replace(d,selected=()),clock=clock,quotes=quotes,marks=marks)
 newids=[m.security_id for m in d.memories if m.waiting and resolved[m.security_id].q is True and m.security_id not in {o.security_id for o in a.occupancy(clock.decision_at)}];fallback=[];priority=A._priority(set(newids)|set(restore_ids),stocks,groups,resolved,clock,'S0',fallback,'joint-role');accepted=[];rejected=[];blocked=set()
 for sid in priority:
  if sid not in restore_ids:
   memory=tuple(replace(m,waiting=False) if m.security_id in blocked else m for m in d.memories);current=factory(previous=memory,occupied=a.occupancy(clock.decision_at),bootstrap=False,completed_exits=())
   if sid not in current.selected:
    rejected.append((sid,next((why for s,why in current.rejected if s==sid),'not_selected_by_original_admission')));blocked.add(sid);continue
   ack=a.apply_decision(replace(current,selected=(sid,),exit_requests=(),cancel_buys=(),continue_buys=(),pause_buys=()),clock=clock,quotes=quotes,marks=marks);accepted.extend(ack.accepted);rejected.extend(ack.rejected);blocked.update(s for s,_ in ack.rejected);continue
  occ=a.occupancy(clock.decision_at);scount=defaultdict(int)
  for p in occ:scount[p.sector_id]+=1
  if len(occ)>6 or len(scount)>3 or any(n>2 for n in scount.values()):rejected.append((sid,'existing_resources_outside_contract'));continue
  quote=quotes.get(sid)
  if quote is None:rejected.append((sid,'decision_quote_unknown'));continue
  bal=a.balance(clock.decision_at,marks);a.current_nav=bal['nav'];pending=sum((o.remaining_budget_cny for o in a.buys.values()),D(0));own=a.quantity(sid)*marks[sid].cny_price(clock.decision_at);ownpending=sum((o.remaining_budget_cny for i,o in a.buys.items() if i==sid),D(0));budget=min(D('.15')*bal['nav'],max(D(0),D('.90')*bal['nav']-bal['inventory']-pending),a.available)
  r=a.roles[sid];gap=r['cap']-r['R'];ok,why=a.restore(quote,clock,budget,receipts[sid]);target=a.buys[sid].target_shares if ok else 0;a.role_events.append(dict(kind='restore_budget_check',at=clock.decision_at,sid=sid,contract_status=RESTORE_BUDGET_STATUS,reference_target=r['cap'],actual_risk_shares=r['R'],gap=gap,own_mark_value=own,mark_known_at=marks[sid].known_at,own_pending_gross=ownpending,total_pending_gross=pending,nav=bal['nav'],available=a.available if not ok else bal['available'],original_per_order_cap=D('.15')*bal['nav'],holding_value_not_a_budget_deduction=True,total_exposure_headroom=max(D(0),D('.90')*bal['nav']-bal['inventory']-pending),selected_budget=budget,submitted_target=target,truncated_reference_shares=gap-target,reason=None if ok else why));(accepted if ok else rejected).append(sid if ok else (sid,why))
 final=factory(previous=d.memories,occupied=a.occupancy(clock.decision_at),bootstrap=False,completed_exits=())
 a.check_roles();return L.CutoffAck(tuple(accepted),tuple(rejected),a.occupancy(clock.decision_at),final.memories,(d,final))
