"""Isolated dispatch adapter over frozen V3. Synthetic only; no history entry."""
from pathlib import Path
import sys,importlib.util,hashlib,copy
HERE=Path(__file__).resolve().parent;BASE=HERE.parent/'g-s-C-native-synthetic-v3-20261102'
BASE_SHA='363d879d55b87669c6ef3d05a70756d91541c8a2a4f6316942d58945c112e8df'
if hashlib.sha256((BASE/'native_c.py').read_bytes()).hexdigest()!=BASE_SHA:raise ValueError('frozen V3 source changed')
if hashlib.sha256((BASE/'goal_coverage.py').read_bytes()).hexdigest()!='0a672623db2c9b0cf5b7d70045f297c2f5d398190819ff91382219e571d93517':raise ValueError('frozen V3 coordinator changed')
sys.path.insert(0,str(BASE))
spec=importlib.util.spec_from_file_location('frozen_c_v3_dispatch_base',BASE/'native_c.py');E=importlib.util.module_from_spec(spec);sys.modules[spec.name]=E;spec.loader.exec_module(E)
for name in dir(E):
 if not name.startswith('_'):globals()[name]=getattr(E,name)
# Export the local test/output path while the base module retains its own
# __file__/source guards and immutable native functions.
HERE=Path(__file__).resolve().parent
from dispatch_order import creation_record,dispatch_key,freeze_priority

class Account(E.Account):
 def __init__(self,owner):super().__init__(owner);self.dispatch_sequence=0
 def submit_fixed(self,i,at,*,use,role,q,cid=None):
  # Validate the source key before ANY new native reserve/receipt mutation.
  pool='probe' if use=='T' or role=='core' else 'confirmed'
  record=creation_record(i['priority'],use,role,pool,i['sid'],self.dispatch_sequence+1)
  x=super().submit_fixed(i,at,use=use,role=role,q=q,cid=cid)
  if x['q']:
   self.dispatch_sequence+=1;record['original_use']=use;self.supports[x['order_id']]['dispatch']=record
  return x

class Runner(E.Runner):
 def __init__(self,mode='C10'):
  require(mode in ('C10','C_BATCH20'),'mode');self.mode=mode;self.account=Account(self)
  self.f1={};self.f1seq={};self.cursor=0;self.lifecycle=[];self.last_stock_state={};self.last_completed_event=None
  self.budget=None;self.authority=Authority();self.trusted={};self.active=None;self.transitions=[];self.binding_id=None;self.windows={};self.event_ids={};self.action_ids={};self.results=[]
  self.coverage=GoalCoverage();self.goal_intents={};self.local_wait_sids={};self._busy_goals={};self.close_stages={};self._required_close_plan_at=None
 def source_binding(self):
  out=super().source_binding()
  for p in [HERE/'native_c.py',HERE/'dispatch_order.py']:out[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
  return out
 def assert_observers(self):
  super().assert_observers()
  for oid,meta in self.account.supports.items():
   if oid in {o.order_id for o in self.account.buys.values()}:dispatch_key(meta,False)
 def opening(self,intents,at,capacities=None,*,buy_windows=None):
  a=self.account;a.last_cursor=at;a.settle_due(at);checked=a.revalidate_batch(at)
  retained={o.order_id for sid,o in a.buys.items() if o.earliest_at<=at and checked[sid]['status']=='amended'}
  # Existing reserves are fixed burdens. Their immutable native creation
  # sequence precedes new C allocation and remaining-resource trial orders.
  out=[];funded=[(sid,o.order_id) for sid,o in a.buys.items() if o.order_id in retained];done=set(a.buys)
  cert=self.active
  if cert and at<=iso(cert['deadline']):
   self.verify_native(cert)
   for sid in sorted(cert['Q'],key=lambda sid:(freeze_priority(self.active_intents[sid]['priority']),sid)):
    if not cert['Q'][sid] or sid in done:continue
    if any(o['cid']==cert['certificate_id'] and o['sid']==sid for o in self.authority.orders.values()):continue
    i=self.active_intents[sid];use=next(d['use'] for d in self.trusted[cert['trusted_id']]['demands'] if d['sid']==sid)
    x=a.submit_fixed(i,at,use=use,role='mobile',q=cert['Q'][sid],cid=cert['certificate_id']);out.append(x)
    if x['q']:done.add(sid);funded.append((sid,x['order_id']))
  for i in sorted(a.pending,key=lambda i:(freeze_priority(i['priority']),i['sid'])):
   if i['sid'] in done or i['sid'] in self.local_wait_sids or at>i['deadline']:continue
   x=a.submit(i,at,use='T');out.append(x)
   if x['q']:done.add(i['sid']);funded.append((i['sid'],x['order_id']))
  ordered=sorted(funded,key=lambda row:dispatch_key(a.supports[row[1]],row[1] in retained))
  a.native_callbacks.append(dict(kind='entire_C_batch_reserved_before_windows',at=at,orders=ordered,available=a.available,retained=sorted(retained),dispatch_schema='FROZEN_NATIVE_DISPATCH_V1'))
  for sid,oid in ordered:
   if buy_windows is not None:w=buy_windows(sid,at)
   else:w=T.window(sid,a.market.prices[sid]*(ONE+LR.SLIP),at,capacity=(capacities or {}).get(sid,10**8),fees=a.market.fees(sid,at),rule=a.market.quantity(sid,at),eid='buy|'+oid+'|'+at.isoformat(),raw_open=a.market.prices[sid],sellable_at=at+timedelta(days=1),cash_due_at=at)
   if w:self.apply_window('buy',sid,w)
  a.settle_due(at);self.assert_observers();return out
