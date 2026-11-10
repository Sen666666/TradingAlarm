"""Target ownership coordinator over ORIGINAL R4 assets/cancel callbacks.

No cash ledger, no expected-proceeds spending, no new grant or expiry credit.
Whole native assets retain their original target owners until actual settlement
or cancel ACK. Only the affected target waits. Unclaimed assets are NOT loaned
to a new certificate before they become actual free cash.
"""
from decimal import Decimal as D
from dataclasses import asdict
import copy

class GoalCoverage:
 def __init__(self):
  self.goals={};self.receivables={};self.settled={};self.sale_events={};self.snapshots=[];self.history=[];self.close_plans={}
 def goal_id(self,a,intent,use):
  scope=intent['sector'] if use=='S' else 'G';s=a.policy.scopes[scope]
  return '|'.join((use,intent['sector'],s.source,str(s.context)))
 def register(self,r,cert,intents,projection):
  a=r.account;mapping={}
  demands=r.trusted[cert['trusted_id']]['demands']
  for d in demands:
   sid=d['sid'];q=cert['Q'].get(sid,0)
   if not q:continue
   gid=self.goal_id(a,intents[sid],d['use']);mapping[sid]=gid
   g=self.goals.setdefault(gid,dict(sector=d['sector'],use=d['use'],authorizations={},created_at=cert['known_at']))
   g['authorizations'][cert['certificate_id']+'|'+sid]=dict(certificate=cert['certificate_id'],sid=sid,quantity=q,receipt=d['receipt_id'],deadline=cert['deadline'],known_at=cert['known_at'],state='original_authorization')
   # Reuse the native R4 registry and bind_order API, NOT its K-based preview.
   a.funding.goals[gid]=copy.deepcopy(g)
  owners=set(mapping.values())
  for part in projection['donors']['rows']:
   oid=a.exits[part['sid']].event_id
   if oid in a.funding.order_goals:
    if set(a.funding.order_goals[oid]['goals'])!=owners:raise ValueError('native funding order already belongs to another target')
   else:a.funding.bind_order(oid,owners,r.account.last_cursor)
  self.close_plans[cert['known_at']]=cert['certificate_id'];self.history.append(dict(kind='bind_C_plan',certificate=cert['certificate_id'],owners=sorted(owners),at=cert['known_at']))
 def sale(self,a,order,f):
  payload=dict(order=order,receipt=f.receipt_id,settlement=f.settlement_id,shares=f.shares)
  if f.receipt_id in self.sale_events:
   if self.sale_events[f.receipt_id]!=payload:raise ValueError('changed native sale ownership callback')
   return
  owners=a.funding.order_goals.get(order,{}).get('goals',[])
  if owners:
   if f.settlement_id not in a.settlements:raise ValueError('sale coverage missing native receivable')
   s=a.settlements[f.settlement_id]
   if s.debit:raise ValueError('sale coverage cannot own debit')
   self.receivables[f.settlement_id]=dict(owners=sorted(owners),origin_order=order,origin_receipt=f.receipt_id,amount=s.cny_amount,due_at=s.due_at)
  self.sale_events[f.receipt_id]=payload
 def settle(self,a,removed,at):
  for sid,s in removed.items():
   if s.debit:continue
   owned=self.receivables.get(sid)
   if owned:
    if sid in self.settled:raise ValueError('settlement ownership released twice')
    self.settled[sid]=dict(at=at,amount=s.cny_amount,owners=owned['owners'],original_receipt=owned['origin_receipt'])
    self.history.append(dict(kind='native_settlement_release',asset='AR|'+sid,at=at,amount=s.cny_amount,owners=owned['owners'],cash_written_by_coordinator=False))
 def check(self,a):
  for sid,asset in self.receivables.items():
   f=next((f for f in a.fills if f.receipt_id==asset['origin_receipt']),None)
   if f is None or f.side!='sell' or f.settlement_id!=sid or f.gross_cny-f.fees_cny!=asset['amount']:raise ValueError('receivable changed from original native sale receipt')
   owners=a.funding.order_goals.get(asset['origin_order'],{}).get('goals',[])
   if sorted(set(asset['owners']))!=asset['owners'] or sorted(owners)!=asset['owners']:raise ValueError('asset owner set changed or duplicated')
   if sid in self.settled:
    if sid in a.settlements:raise ValueError('settled asset still pending in native ledger')
    done=self.settled[sid]
    if done['amount']!=asset['amount'] or done['owners']!=asset['owners'] or done['original_receipt']!=asset['origin_receipt']:raise ValueError('settled coverage body changed')
   elif sid not in a.settlements or a.settlements[sid].cny_amount!=asset['amount']:
    raise ValueError('receivable ownership lost without native settlement')
  for oid,entry in a.funding.order_goals.items():
   if not entry['goals'] or any(g not in self.goals for g in entry['goals']):raise ValueError('unbound native funding goal')
 def reconcile(self,r,clock):
  a=r.account;at=clock.decision_at;self.check(a);closed=[]
  for gid,g in self.goals.items():
   for auth in g['authorizations'].values():
    expired=at.isoformat()>=auth['deadline']
    i=r.goal_intents[auth['certificate']][auth['sid']];scope=i['sector'] if g['use']=='S' else 'G'
    original=r.authority.certificates[auth['certificate']]['receipt_bindings'][auth['sid']]['market_context']
    s=a.policy.scopes.get(scope);valid=bool(s and s.context==original and a.policy.allowed(scope,g['use']) and r.last_stock_state.get(auth['sid'],{}).get('i_valid') is True)
    if expired or not valid:
     auth['state']='expired' if expired else 'original_qualification_ended';closed.append(auth['certificate']+'|'+auth['sid'])
     order=a.buys.get(auth['sid'])
     if order and a.supports[order.order_id].get('C_certificate')==auth['certificate'] and auth['sid'] not in a.cancel_requests:a.request_buy_cancel(auth['sid'])
  # Expired target is NOT a new receipt credit. Withdraw only pure obsolete
  # funding duties; native ACK/fill race and budget observations remain native.
  for sid,o in tuple(a.exits.items()):
   entry=a.funding.order_goals.get(o.event_id)
   if not entry or not a._is_pure_funding_exit(sid):continue
   alive=any(v['state']=='original_authorization' for gid in entry['goals'] for v in self.goals[gid]['authorizations'].values())
   if not alive and sid not in a.funding.cancel_requests:a.request_funding_cancel(sid,at,'original_target_ended')
  assets=a.funding.assets(a,clock);busy={};rows=[]
  if len({v['asset'] for v in assets})!=len(assets):raise ValueError('native coverage asset counted twice')
  for asset in assets:
   if asset['kind']=='pending_exit':owners=a.funding.order_goals.get(asset['order'],{}).get('goals',[])
   else:
    sid=asset['asset'].split('|',1)[1];owners=self.receivables.get(sid,{}).get('owners',[])
   if asset['kind']=='pending_exit' and asset['pure_funding'] and not owners:raise ValueError('pure funding duty has no original target owner')
   for gid in owners:busy.setdefault(gid,[]).append(asset['asset'])
   rows.append(dict(asset,owners=sorted(owners),spendable_cash=False,available_to_new_targets=False))
  self.snapshots.append(dict(at=at,assets=copy.deepcopy(rows),busy=copy.deepcopy(busy),closed_authorizations=closed,actual_available=a.available))
  return busy
 def exported(self):return copy.deepcopy(self.__dict__)
