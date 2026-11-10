"""Persistent planning coverage only. No cash, fills, reserves or NAV here."""
import copy
from decimal import Decimal as D
from imports_native import LR,fees,quantity
Z=D(0);ONE=D(1)

class FundingCoverage:
 def __init__(self):
  self.goals={};self.order_goals={};self.cancel_requests={};self.cancelled_orders={};self.snapshots=[];self.history=[];self.sequence=0
 def goal_id(self,a,sec):
  s=a.policy.scopes[sec];return 'S|'+sec+'|'+s.source+'|'+s.context
 def bind_order(self,order,goals,at):
  self.sequence+=1;self.order_goals[order]=dict(goals=sorted(goals),created_at=at,sequence=self.sequence)
 def assets(self,a,clock):
  rows=[]
  for key,s in sorted(a.settlements.items()):
   if not s.debit:rows.append(dict(asset='AR|'+key,kind='sale_receivable',amount=s.cny_amount,due_at=s.due_at,order=None,pure_funding=False,sequence=-1))
  for sid,o in sorted(a.exits.items()):
   q=o.remaining_target if o.remaining_target is not None else a.quantity(sid)
   p=a.market.prices[sid]*(ONE-LR.SLIP);schedule=fees(clock.earliest_execution_at,a.market.stars[sid]);cost=sum(a._fee(o,schedule,'sell',D(q)*p,shares=q).values(),Z) if q else Z
   amount=max(Z,D(q)*p-cost);linked=self.order_goals.get(o.event_id);pure=a._is_pure_funding_exit(sid)
   rows.append(dict(asset='EXIT|'+o.event_id,kind='pending_exit',sid=sid,order=o.event_id,quantity=q,price=p,incremental_fee=cost,amount=amount,pure_funding=pure,
    cancel_pending=sid in self.cancel_requests,sequence=linked['sequence'] if linked else -1))
  return sorted(rows,key=lambda x:(x['kind']!='sale_receivable',x['pure_funding'],x['sequence'],x['asset']))
 def preview(self,a,items,clock):
  goals=copy.deepcopy(self.goals);resources=a.resources()
  for x in items:
   key=x['goal_id'];s=a.policy.scopes[x['sector']]
   g=goals.setdefault(key,dict(sector=x['sector'],source=s.source,context=s.context,use='S',stock_targets={},priority=x['priority'],created_at=clock.decision_at))
   g['stock_targets'][x['sid']]=dict(target_capital=x['target_capital'],priority=x['priority']);g['priority']=min(g['priority'],x['priority']);g['last_fresh_at']=clock.decision_at
  for key,g in goals.items():
   s=a.policy.scopes.get(g['sector']);authorized=bool(s and s.source==g['source'] and s.context==g['context'] and a.policy.allowed(g['sector'],'S') and g['sector'] in a.policy.k)
   g['status']='authorized' if authorized else 'not_authorized';g['remaining_cash']=Z
   if not authorized:continue
   sector_cap=sum((r['capital'] for r in resources if r['sector']==g['sector']),Z);room=max(Z,a.policy.targets(g['sector'])-sector_cap)
   for sid,target in sorted(g['stock_targets'].items(),key=lambda kv:(kv[1]['priority'],kv[0])):
    if a.funding_stock_I.get(sid,True) is not True or sid in a.exits:continue
    stock=sum((r['capital'] for r in resources if r['sid']==sid),Z);budget=min(room,max(Z,min(target['target_capital'],a.policy.nd*D('.1'))-stock));p=a.market.prices[sid]*(ONE+LR.SLIP)
    rule=quantity(clock.earliest_execution_at,a.market.stars[sid]);q=rule.buy_floor(int(budget/p))
    if not q:continue
    gross=D(q)*p;room-=gross;g['remaining_cash']+=gross+LR.fees(q,p,fees(clock.earliest_execution_at,a.market.stars[sid]),'buy')
  spendable=max(Z,a.available-a.policy.nd*D('.1'));free=spendable;needs={}
  for x in sorted(items,key=lambda x:(x['priority'],x['sid'])):
   used=min(free,x['cash']);free-=used;needs[x['goal_id']]=needs.get(x['goal_id'],Z)+x['cash']-used
  assets=self.assets(a,clock);left={x['asset']:x['amount'] for x in assets};alloc=[];uncovered=Z
  for gid,need in sorted(needs.items(),key=lambda kv:(goals[kv[0]]['priority'],kv[0])):
   rem=need
   for x in assets:
    used=min(rem,left[x['asset']]);rem-=used;left[x['asset']]-=used
    if used:alloc.append(dict(goal=gid,asset=x['asset'],amount=used))
    if not rem:break
   uncovered+=rem
  raw=sum(needs.values(),Z);all_need=max(Z,sum((g['remaining_cash'] for g in goals.values()),Z)-spendable)
  projected=sum((x['amount'] for x in assets if not x.get('cancel_pending')),Z);cancels=[]
  for x in sorted([x for x in assets if x['pure_funding'] and not x.get('cancel_pending')],key=lambda x:(-x['sequence'],x['asset'])):
   linked=self.order_goals[x['order']]['goals'];obsolete=all(goals[g]['status']!='authorized' or not goals[g]['remaining_cash'] for g in linked)
   # Whole-order reduction only. Never invent a partial sell-amend API.
   if obsolete or projected-x['amount']>=all_need:
    cancels.append(dict(sid=x['sid'],order=x['order'],reason='target_obsolete' if obsolete else 'whole_order_excess_cover'));projected-=x['amount']
  return dict(at=clock.decision_at,goals=goals,assets=assets,allocations=alloc,raw_cash_need=raw,covered=raw-uncovered,uncovered=uncovered,cancel_requests=cancels,
   wait_cancel_ack=bool(self.cancel_requests or cancels),spendable_cash=spendable,all_saved_target_need=all_need,coverage_is_spendable_cash=False)
 def commit(self,a,view):
  self.goals=view['goals']
  for request in view['cancel_requests']:a.request_funding_cancel(request['sid'],view['at'],request['reason'])
  self.snapshots.append(copy.deepcopy(view))
 def exported(self):
  return dict(goals=self.goals,order_goals=self.order_goals,cancel_requests=self.cancel_requests,cancelled_orders=self.cancelled_orders,snapshots=self.snapshots,history=self.history,sequence=self.sequence)
