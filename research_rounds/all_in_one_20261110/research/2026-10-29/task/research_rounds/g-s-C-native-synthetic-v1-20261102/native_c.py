"""Isolated C10/C_BATCH20 native synthetic binding. No historical entry point.

Prices/I/Q/canonical-equivalent receipts/ranking are explicit causal fixtures.
F1, Decimal ledger, execution, fees, settlement and lot selection are ORIGINAL.
Projection outputs stay analysis_only. A separate recomputed C certificate is
the only authority for new confirmed orders. Budget is NOT a cash ledger.
"""
from pathlib import Path
from datetime import datetime,timedelta
from dataclasses import asdict
from decimal import Decimal as D
from fractions import Fraction as F
import sys,copy,json,pickle,hashlib,inspect

HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-historical-native-prefix-20261101'))
import native_capital as N
from imports_native import T,LR,F1,IO,quantity,fees
from policy import Policy,UnknownRisk
from native_capital import HistoricalReceipt
sys.path.insert(0,str(W/'g-s-C-batch20-projection-r2-20261102'))
import c_batch20 as BC
from batch_book import BatchBook
C=BC.C;B=C.B;J=C.J;Z=D(0);ONE=D(1)

def digest(x):return J.digest(x)
def encode(x):
 if isinstance(x,F):return str(x)
 return N.encode(x)
def iso(x):return datetime.fromisoformat(x)
def require(v,msg):
 if not v:raise ValueError(msg)

class Market(N.FixtureMarket):
 def quantity(self,sid,at):return quantity(at,self.stars[sid])
 def fees(self,sid,at):return fees(at,self.stars[sid])
 def lag(self,at,count):return at+timedelta(days=count)

class CPolicy(Policy):
 def targets(self,sector):
  return self.nd*(D('.8') if self.allowed(sector,'S',holding=True) else D('.2') if self.allowed('G','G',holding=True) else D('.02') if self.allowed(sector,'T',holding=True) else Z)
 def choose_k(self,*args):
  # Intentional removal of old A's equal guaranteed allocation. No K state is
  # created and no target depends on the number of eligible industries.
  require(not self.k,'legacy K cannot enter C');return {}

class OffBook(BatchBook):
 """Same lifecycle/records; only the approval predicate is disabled."""
 def preview(self,requests):
  p=super().preview(requests);p['unbounded_original_ok']=p['ok'];p['ok']=True;p['predicate_enabled']=False;return p

class Authority:
 """Receipt-bound quantity authority; no cash or accounting model."""
 def __init__(self):self.certificates={};self.orders={};self.events={}
 def accept(self,cert):
  require(cert['certificate_id']==digest({k:v for k,v in cert.items() if k!='certificate_id'}),'certificate body hash')
  cid=cert['certificate_id']
  if cid in self.certificates:require(self.certificates[cid]==cert,'changed certificate');return
  self.certificates[cid]=copy.deepcopy(cert)
 def bind(self,cid,sid,oid,q,receipt):
  c=self.certificates[cid]
  require(not any(o['cid']==cid and o['sid']==sid for o in self.orders.values()),'receipt cannot create another order after cancel/fill')
  require(oid not in self.orders and receipt==c['receipt_bindings'][sid]['event_id'] and 0<q<=c['Q'][sid],'native reserve certificate binding')
  self.orders[oid]=dict(cid=cid,sid=sid,receipt=receipt,initial=F(q),remaining=F(q),filled=F(0),cancelled=F(0),ratio=F(1))
 def fill(self,oid,q,event):
  o=self.orders[oid];x=dict(oid=oid,q=q)
  if event in self.events:require(self.events[event]['oid']==oid and self.events[event]['q']==q,'changed fill payload');return
  n=F(q)/o['ratio'];require(0<n<=o['remaining'],'fill exceeds certified remaining')
  o['remaining']-=n;o['filled']+=n;self.events[event]=dict(x,anchor_q=n)
 def reconcile_remaining(self,oid,raw_remaining):
  o=self.orders[oid];n=F(raw_remaining)/o['ratio'];require(0<=n<=o['remaining'],'amend cannot grow authorization')
  o['cancelled']+=o['remaining']-n;o['remaining']=n
 def split(self,sid,ratio):
  for o in self.orders.values():
   if o['sid']==sid:o['ratio']*=F(str(ratio))
 def check(self,a):
  for oid,o in self.orders.items():
   require(o['initial']==o['remaining']+o['filled']+o['cancelled'],'certificate quantity conservation')
   require(all(o[k]>=0 for k in ('initial','remaining','filled','cancelled')),'negative authorization')
   c=self.certificates[o['cid']];require(o['initial']<=c['Q'][o['sid']],'certificate cap')
   native=a.buys.get(o['sid']);actual=native.remaining_shares if native and native.order_id==oid else 0
   require(F(actual)==o['remaining']*o['ratio'],'actual native remaining mismatch')
   require(o['receipt']==c['receipt_bindings'][o['sid']]['event_id'],'receipt identity')
   require(sum((v['anchor_q'] for v in self.events.values() if v['oid']==oid),F(0))==o['filled'],'observed fill anchor conservation')
  for eid,v in self.events.items():
   f=next((f for f in a.fills if f.receipt_id==eid),None);require(f is not None and f.side=='buy' and f.shares==v['q'],'actual fill receipt mismatch')
   require(eid in a.inventory_map and a.capital_meta[a.inventory_map[eid]['layer']]['order']==v['oid'],'actual selected lot/order callback mismatch')
  for oid,m in a.supports.items():
   if m.get('C_certificate'):require(oid in self.orders,'missing actual authorization mapping')

class Account(N.CapitalAccount):
 def __init__(self,owner):
  market=Market();super().__init__('C_NATIVE_SYNTHETIC',market=market,facts=N.FixtureFacts(market));self.policy=CPolicy();self.owner=owner
  self.receipt_registry={};self.retained={}
 def receipt_verified(self,c):
  return (isinstance(c,N.HistoricalReceipt) and c.source=='synthetic_causal_CP1_interface' and c.source_binding=='synthetic-explicit-input-v1'
   and self.receipt_registry.get(c.event_id)==digest(asdict(c)) and c.payload_sha256==hashlib.sha256(c.payload_json.encode()).hexdigest())
 def _current_holding_support(self,sec):
  s=self.policy.scopes.get(sec);g=self.policy.scopes.get('G')
  if s and s.support and s.mature:return dict(use='S',context=s.context,fraction=D('.8'))
  if g and g.support:return dict(use='G',context=g.context,fraction=D('.2'))
  if s and s.support:return dict(use='T',context=s.context,fraction=D('.02'))
  return dict(use=None,context=None,fraction=Z)
 def funding_reductions(self,intents,clock):return self.owner.plan(intents,clock)
 def _preview(self,i,use,role,at,*,exclude_order=None,cap=None):
  sid=i['sid'];p=self.market.prices[sid]*(ONE+LR.SLIP);rule=self.market.quantity(sid,at);schedule=self.market.fees(sid,at);nd=self.policy.nd
  if not i['i_valid'] or not i['stock_q']:return dict(q=0,why=['stock_I_Q'],use=use,role=role)
  scope='G' if use=='G' else i['sector'];permission_use=use
  # G can support a small trial too; its role/quantity/probe risk do not expand.
  if use=='T' and not self.policy.allowed(scope,'T') and self.policy.allowed('G','G'):scope='G';permission_use='G'
  if not self.policy.allowed(scope,permission_use):return dict(q=0,why=['permission'],use=use,role=role)
  if sid in self.exits or any(e.sid==sid and e.remaining for e in self.policy.locks.values()) or (sid in self.buys and self.buys[sid].order_id!=exclude_order):return dict(q=0,why=['native_responsibility'],use=use,role=role)
  if not exclude_order and role=='mobile':
   c=i['receipt'];valid=isinstance(c,HistoricalReceipt) and c.sid==sid and self.receipt_verified(c) and c.scale=='21' and c.structure==i['epoch'] and c.start<=c.end<=c.confirmed==i['clock'].decision_at<at and c.event_id not in self.policy.consumed
   if not valid:return dict(q=0,why=['fresh_CP1'],use=use,role=role)
  if not exclude_order and role=='core' and (not i['core'] or self.quantity(sid) or self.core_epoch.get(sid)==i['epoch']):return dict(q=0,why=['core_eligibility_or_epoch'],use=use,role=role)
  floor=i['I_floor']/self.facts.factor(sid,at)
  if role=='mobile':floor=max(floor,D(i['cp_floor'])/self.facts.factor(sid,at))
  if self.market.prices[sid]<=floor:return dict(q=0,why=['gap_at_or_below_actual_floor'],use=use,role=role)
  try:rows=self.resources(exclude_order=exclude_order)
  except UnknownRisk as e:return dict(q=0,why=['UNKNOWN:'+str(e)],use=use,role=role)
  tot=self.totals(rows);sec=[r for r in rows if r['sector']==i['sector']];stock=[r for r in rows if r['sid']==sid];trial=[r for r in rows if r['pool']=='probe']
  # Source/price evidence authorizes purposes, never creates cash or floor credit.
  target=nd*D('.02') if use=='T' else (nd*D('.20') if use=='G' else self.policy.targets(i['sector']))
  if use=='T':
   if self.policy.allowed(i['sector'],'S'):target=self.policy.targets(i['sector'])
   elif self.policy.allowed('G','G'):target=nd*D('.20')
  if target<=0:return dict(q=0,why=['K_inactive'],use=use,role=role)
  pool='probe' if use=='T' or role=='core' else 'confirmed'
  budget=min(nd*D('.1'),max(Z,target-sum((r['capital'] for r in sec),Z)))
  if use=='T' or role=='core':budget=min(budget,nd*D('.02'))
  upper=min(int(budget/p),cap if cap is not None else 10**9)
  current=self.nav(at);oldreserve=Z
  if exclude_order:
   o=self.buys[sid];oldreserve=o.remaining_budget_cny+o.fee_reserved_cny
  avail=self.available+oldreserve
  other_pending_fees=sum((o.fee_reserved_cny for o in self.buys.values() if o.order_id!=exclude_order),Z)
  def reasons(n):
   gross=D(n)*p;fee=(sum(self._fee(self.buys[sid],schedule,'buy',gross,shares=n).values(),Z) if exclude_order else LR.fees(n,p,schedule,'buy'));bn=current-other_pending_fees-fee;pr=D(n)*max(Z,p-floor);f=[]
   if gross+fee>avail-max(Z,nd*D('.1')):f.append('cash_reserve10')
   if tot['capital']+gross>bn*D('.9'):f.append('account_capital90')
   if sum((r['capital'] for r in sec),Z)+gross>target:f.append('industry_target')
   if sum((r['capital'] for r in stock),Z)+gross>nd*D('.1'):f.append('stock10')
   if sum((r['risk'] for r in sec),Z)+pr>bn*D('.05'):f.append('sector_risk5')
   if tot['risk']+pr>bn*D('.06'):f.append('account_risk6')
   if pool=='probe':
    if sum((r['capital'] for r in trial),Z)+gross>bn*D('.1'):f.append('probe_capital10')
    if sum((r['risk'] for r in trial),Z)+pr>bn*D('.005'):f.append('probe_risk.5')
   if role=='core' and LR.protection_risk(n,p,floor,schedule)>nd*D('.0025'):f.append('core_risk.25')
   return f
  if exclude_order:
   upper=min(upper,int(self.buys[sid].remaining_budget_cny/p))
  if exclude_order and self.buys[sid].filled_shares:
   # A continuing original partial remainder uses matching granularity.
   q=0;lo=0;hi=upper//rule.fill_step
   while lo<hi:
    mid=(lo+hi+1)//2
    if not reasons(mid*rule.fill_step):lo=mid
    else:hi=mid-1
   q=lo*rule.fill_step
  else:q=LR.maximum_quantity(rule,upper,lambda n:not reasons(n))
  return dict(q=q,why=[] if q else (['target_minimum'] if upper<rule.buy_minimum else reasons(rule.buy_minimum)),use=use,scope=scope,permission_use=permission_use,role=role,pool=pool,p=p,floor=floor,budget=budget,limit=p,schedule=schedule,minimum=rule.buy_minimum,step=rule.buy_step,actual_nav=current,decision_nav=nd)
 def submit_fixed(self,i,at,*,use,role,q,cid=None):
  require(at<=i['deadline'],'original deadline')
  if use!='T':
   require(cid is not None and cid in self.owner.authority.certificates,'confirmed order requires trusted C authority')
   c=self.owner.authority.certificates[cid];self.owner.verify_native(c)
   require(i['sid'] in c['Q'] and 0<q<=c['Q'][i['sid']] and c['receipt_bindings'][i['sid']]['event_id']==i['receipt'].event_id,'fixed order not certified')
   require(not any(o['cid']==cid and o['sid']==i['sid'] for o in self.owner.authority.orders.values()),'certificate/receipt already submitted')
  x=self._preview(i,use,role,at,cap=q)
  if not x['q']:self.rejections.append(dict(at=at,sid=i['sid'],route=x));return x
  q=x['q'];meta=dict(i,kind='core' if role=='core' else 'add',floor=x['floor']*self.facts.factor(i['sid'],at),budget=x['budget'],cap=q,score=i.get('score'),reason='C_'+use,risk_budget=self.policy.nd*D('.0025'))
  oid=self.reserve_quantity(meta,q,x['p'],x['schedule'],at)
  g=self._preview(i,'G',role,at,exclude_order=oid,cap=q)
  backup=min(q,g['q']);gs=self.policy.scopes.get('G')
  self.supports[oid]=dict(sector=i['sector'],pool=x['pool'],role=role,use=use,scope=x['scope'],permission_use=x['permission_use'],context=self.policy.scopes[x['scope']].context,
   limit=x['p'],deadline=i['deadline'],priority=i['priority'],receipt=i['receipt'],quantity=q,g_backup=backup,g_context=gs.context if gs else None,
   g_original_gross=D(backup)*x['p'],g_original_fee=LR.fees(backup,x['p'],x['schedule'],'buy'),created_at=at,original_intent=i,C_certificate=cid)
  if role=='mobile':require(i['receipt'].event_id not in self.policy.consumed,'receipt used');self.policy.consumed.add(i['receipt'].event_id)
  if cid:self.owner.authority.bind(cid,i['sid'],oid,q,i['receipt'].event_id)
  x['order_id']=oid;return x
 def submit(self,i,at,*,use=None):
  # Only original small-trial/core fallback calls this path; confirmed orders
  # must arrive via the trusted fixed C plan, never a fresh full route.
  if use not in (None,'T'):raise ValueError('confirmed admission requires C authority')
  x=self.route(i,at,use='T')
  if not x['q']:self.rejections.append(dict(at=at,sid=i['sid'],route=x));return x
  return self.submit_fixed(i,at,use='T',role=x['role'],q=x['q'])
 def revalidate(self,sid,at):
  x=super().revalidate(sid,at);o=self.buys.get(sid)
  if o and o.order_id in self.owner.authority.orders:self.owner.authority.reconcile_remaining(o.order_id,o.remaining_shares)
  return x
 def ack_buy_cancel(self,sid):
  o=self.buys.get(sid);oid=o.order_id if o else None
  x=super().ack_buy_cancel(sid)
  if oid in self.owner.authority.orders:self.owner.authority.reconcile_remaining(oid,0)
  return x
 def fill_buy(self,sid,w):
  o=self.buys.get(sid);oid=o.order_id if o else None;f=super().fill_buy(sid,w)
  if f:
   if oid in self.owner.authority.orders:self.owner.authority.fill(oid,f.shares,f.receipt_id)
   z=self.layers[-1];self.owner.add_layer(z)
  return f
 def fill_exit(self,sid,w):
  old=len(self.trades);f=super().fill_exit(sid,w)
  if f:
   require(len(self.trades)==old+1,'native trade callback count')
   for p in self.trades[-1]['parts']:
    if self.owner.budget:
     self.owner.budget.observe_fill(str(p['layer']),p['shares'],w.execution_price,f.receipt_id+'|'+str(p['layer']),source_binding=self.owner.budget.source_binding,at=w.at.isoformat())
  return f
 def trim(self,lot_id,qty,clock,reason='allocation_trim'):
  opportunity=reason=='actionable_S_funding'
  z=next(z for z in self.layers if z['id']==lot_id);row=getattr(self.owner,'_close_packet',{}).get(z['sid'],{})
  current_close=getattr(self.owner,'_close_at',None)==clock.decision_at
  if opportunity:
   require(self.owner.active is not None and self.owner.budget is not None,'no approved funding plan')
   approved=next((p['q'] for p in self.owner.results[-1].get('projection',{}).get('donors',{}).get('rows',[]) if p['layer']==lot_id),0)
   require(0<qty<=approved and self.owner.budget.lines[str(lot_id)]['opp']>=qty,'funding duty not covered by certified joint plan')
  if not opportunity:
   if reason=='ACT_pause':valid=current_close and not self.policy.act['on'] and self.policy.incident is not None
   elif reason=='I_structure_exit':valid=current_close and row.get('i_valid') is False
   elif reason=='CP1_old_line_exit':valid=current_close and z['kind']=='add' and row.get('close') is not None and D(str(row['close']))<=self.raw_floor(z)
   elif reason=='remaining_support_target':
    sec=self.capital_meta[lot_id]['sector'];old=getattr(self.owner,'_close_support_before',{}).get(sec);new=self._current_holding_support(sec)
    valid=current_close and old is not None and old['fraction']>new['fraction']
   else:valid=False
   require(valid,'no independent as-of mandatory evidence; rank/target is not exemption')
   old=sum(e.remaining for e in self.policy.locks.values() if e.lot==lot_id and e.remaining)
   require(not (old>qty and any(set(self.exit_duties[e.eid]['reasons'])=={'actionable_S_funding'} for e in self.policy.locks.values() if e.lot==lot_id and e.remaining)), 'UNSUPPORTED partial mandatory upgrade of larger funding union; atomic reject')
  super().trim(lot_id,qty,clock,reason)
  if not opportunity and self.owner.budget:
   b=self.owner.budget;key=str(lot_id);pid=digest(dict(layer=key,qty=qty,at=str(clock.decision_at),reason=reason))
   b.proofs[pid]=dict(kind='ACT_exit' if reason=='ACT_pause' else 'original_protection_failure' if reason in ('I_structure_exit','CP1_old_line_exit') else 'original_price_support_failure',layer=key,qty=qty,known_at=clock.decision_at.isoformat(),relative_ratio=b.lines[key]['relative_ratio'])
   b.mandatory(key,qty,pid,at=clock.decision_at.isoformat())
 def split(self,**kw):
  # Native preflight (including all pending/locks) is before mutation; outer
  # event transaction makes observer refusal atomic too.
  sid=kw['sid'];r=kw['ratio'];eid=kw['event_id'];payload=digest(kw)
  if eid in self.owner.action_ids:require(self.owner.action_ids[eid]==payload,'changed corporate action identity');return
  require(eid not in self.action_events,'native action exists without observer binding')
  super().split(**kw)
  if self.owner.budget:
   for key,z in self.owner.budget.lines.items():
    if z['sid']==sid:self.owner.budget.observe_split(key,r,at=kw['at'].isoformat(),source_binding=self.owner.budget.source_binding)
  self.owner.authority.split(sid,r)
  self.owner.action_ids[eid]=payload

class Runner(N.SyntheticRunner):
 def __init__(self,mode='C10'):
  require(mode in ('C10','C_BATCH20'),'unknown mode');self.mode=mode
  self.account=Account(self);self.f1={};self.f1seq={};self.cursor=0;self.lifecycle=[];self.last_stock_state={};self.last_completed_event=None
  self.budget=None;self.authority=Authority();self.trusted={};self.active=None;self.transitions=[];self.binding_id=None;self.windows={};self.event_ids={};self.action_ids={};self.results=[]
 def add_layer(self,z):
  if self.budget:
   key=str(z['id']);require(key not in self.budget.lines,'duplicate layer callback')
   self.budget.lines[key]=dict(layer=key,sid=z['sid'],qty=z['qty'],opp=0,mandatory=0,relative_ratio='1',cancel_pending=False)
 def _duties(self):
  a=self.account;out={}
  for z in a.layers:
   key=str(z['id']);active=[e for e in a.policy.locks.values() if e.lot==z['id'] and e.remaining and not a.exit_duties[e.eid].get('funding_suspended')]
   opp=sum(e.remaining for e in active if set(a.exit_duties[e.eid]['reasons'])=={'actionable_S_funding'})
   mandatory=sum(e.remaining for e in active if set(a.exit_duties[e.eid]['reasons'])!={'actionable_S_funding'})
   # Native tranches are disjoint. A mandatory upgrade covers their union.
   out[key]=dict(qty=z['qty'],opp=opp,mandatory=mandatory)
  return out
 def assert_observers(self):
  self.account.assert_lot_bridge();self.authority.check(self.account)
  if not self.budget:return
  require(self.binding_id==self.budget.source_binding,'persistent budget snapshot binding')
  batch=self.budget.batch
  if batch:
   approved=batch['approved'];require(len(approved)==len(set(approved)),'duplicate batch authorization')
   require(sum((D(self.budget.plans[p]['charge']) for p in approved),Z)==D(batch['new']),'persistent New charge mismatch')
   carry=sum((D(max(0,z['opp']-z['mandatory']))*D(batch['marks'][k]) for k,z in batch['frozen_lines'].items() if z['opp']>z['mandatory']),Z)
   require(carry==D(batch['carry']) and D(batch['limit'])==D(batch['NAV'])*D('.2'),'frozen Carry/NAV budget mismatch')
  actual=self._duties()
  for key,b in self.budget.lines.items():
   n=actual[key];require(b['qty']==n['qty'],'budget/native stock quantity')
   require(max(b['opp'],b['mandatory'])==n['opp']+n['mandatory'],'budget/native responsibility union')
   require(max(0,b['opp']-b['mandatory'])==n['opp'],'budget/native healthy opportunity responsibility')
 def advance_snapshot(self,old_binding,s):
  require(self.budget and old_binding==self.binding_id==self.budget.source_binding,'previous snapshot binding mismatch')
  self.assert_observers();require(s['account_id']==self.budget.account_id,'different account')
  if self.transitions:require(iso(s['at'])>=iso(self.transitions[-1]['at']),'snapshot clock replay')
  # snapshot is rebuilt here from the actual native provider; caller cannot
  # supply an arbitrary target/price/account view and rebind the book.
  live=self.provider(s['at'],self._provider_intents,self._provider_evidence)[0]
  require(digest(live)==digest(s),'snapshot not actual native provider')
  new=digest(s);self.transitions.append(dict(old=old_binding,new=new,at=s['at'],native_fills=digest([asdict(f) for f in self.account.fills]),native_actions=sorted(self.account.action_events),native_commitments=digest(self._duties()),previous_event_chain=digest(self.event_ids)))
  self.budget.source_binding=new;self.binding_id=new
 def _init_or_bind(self,s,intents,e):
  self._provider_intents=intents;self._provider_evidence=e
  if self.budget is None:
   cls=BatchBook if self.mode=='C_BATCH20' else OffBook
   self.budget=cls(s['account_id'],digest(s),[dict(layer=str(z['id']),sid=z['sid'],qty=z['qty'],opp=0,mandatory=0,relative_ratio='1') for z in self.account.layers])
   self.binding_id=digest(s)
   # The very first native batch may already contain independent exits only
   # when created in this close. Register their original trusted evidence.
   for key,n in self._duties().items():
    require(not n['opp'],'cannot initialize over preexisting opportunity duties')
    if n['mandatory']:
     pid='initial|'+key;self.budget.proofs[pid]=dict(kind='original_protection_failure',layer=key,qty=n['mandatory'],known_at=s['at'],relative_ratio='1')
     self.budget.mandatory(key,n['mandatory'],pid,at=s['at'])
  else:self.advance_snapshot(self.binding_id,s)
  marks={str(z['id']):z['mark'] for z in s['lots']}
  self.budget.begin(s['at'],s['decision_nav'],marks)
 def provider(self,at,intents,evidence):
  at=iso(at) if isinstance(at,str) else at;a=self.account;a.last_cursor=at;a.assert_lot_bridge();a.resources()
  require(iso(evidence['known_at'])<=at,'future industry evidence')
  bal=a.balance(at,a.market.marks(at,a.positions));rows=[];lots=[];resources={r['id']:r for r in a.resources() if r['kind']=='lot'}
  priorities={i['sid']:list(i['priority']) for i in intents};held={z['sid'] for z in a.layers if z['qty'] and a.capital_meta[z['id']]['role']=='mobile'}
  for sid in held:
   row=self.last_stock_state.get(sid)
   require(row is not None and isinstance(row.get('priority'),(tuple,list)),'UNKNOWN held-stock original priority')
   if sid in priorities:require(priorities[sid]==list(row['priority']),'same-stock priority mismatch')
   priorities[sid]=list(row['priority'])
  for z in a.layers:
   if not z['qty']:continue
   sid=z['sid'];m=a.capital_meta[z['id']];r=resources[z['id']];locks=[v for v in a.policy.locks.values() if v.lot==z['id'] and v.remaining]
   sellable=sum(l.shares for l in a.positions[sid].lots if a._mapped_layer(l)==z['id'] and l.sellable_at<=at)
   eligible=(m['role']=='mobile' and not locks and sid not in a.exits and sid not in a.buys and self.last_stock_state.get(sid,{}).get('i_valid') is True and a._current_holding_support(m['sector'])['use'] is not None)
   p=a.market.prices[sid];f=a.raw_floor(z);qr=asdict(a.market.quantity(sid,at));fs=asdict(a.market.fees(sid,at))
   row=dict(id=z['id'],sid=sid,sector=m['sector'],role=m['role'],pool=m['pool'],qty=z['qty'],mark=p,capital=r['capital'],risk=r['risk'],reserve=Z)
   rows.append(row);lots.append(dict(row,floor=f,fees=fs,quantity=qr,purpose=m['purpose'],holding_S=a.policy.allowed(m['sector'],'S',holding=True),locked_capital=sum((D(v.remaining)*p for v in locks),Z),
    donor_eligible=eligible,B_donor_eligible=eligible,sellable_qty=sellable,rank_key=priorities.get(sid),fifo=z['id']))
  for sid,o in a.buys.items():
   m=a.supports[o.order_id];rr=next(r for r in a.resources() if r['id']==o.order_id)
   rows.append(dict(rr,qty=o.remaining_shares,mark=a.market.prices[sid]))
  # No approximate coverage restorer: unresolved old planned purchases need
  # an explicit native goal reconciler before NEW certificates. Keep the old
  # order/exit/carry intact and return WAIT in plan(), never infer cash.
  active_need=any(o.remaining_shares for o in a.buys.values())
  old_funding=any(n['opp'] for n in self._duties().values())
  unsettled=bal['sale_receivable']>0
  pending_goals=bool(self.active and at<iso(self.active['deadline']) and any(q and not any(o['cid']==self.active['certificate_id'] and o['sid']==sid for o in self.authority.orders.values()) for sid,q in self.active['Q'].items()))
  registry={};ds=[];clock=intents[0]['clock'] if intents else T.admission.Clock(at,at+timedelta(days=1),at.date());deadline=clock.earliest_execution_at.replace(hour=15,minute=10)
  for i in intents:
   c=i['receipt'];sid=i['sid'];sec=i['sector']
   if not (i['stock_q'] and i['i_valid'] and c and a.receipt_verified(c) and c.event_id not in a.policy.consumed and c.confirmed==at and c.structure==i['epoch']):continue
   if sid in a.buys or sid in a.exits or any(v.sid==sid and v.remaining for v in a.policy.locks.values()):continue
   use='S' if a.policy.allowed(sec,'S') else 'G' if a.policy.allowed('G','G') else None
   if use is None:continue
   p=a.market.prices[sid];f=max(i['I_floor'],D(i['cp_floor']))/a.facts.factor(sid,at);rule=a.market.quantity(sid,clock.earliest_execution_at)
   if p<=f:continue
   maximum=rule.buy_floor(int(a.policy.nd*D('.1')/(p*(ONE+LR.SLIP))))
   binding=dict(event_id=c.event_id,sid=sid,source=c.source,source_binding=c.source_binding,payload_sha256=c.payload_sha256,start=c.start.isoformat(),end=c.end.isoformat(),confirmed=c.confirmed.isoformat(),deadline=i['deadline'].isoformat(),structure=list(c.structure),scale=c.scale,market_context=a.policy.scopes[sec if use=='S' else 'G'].context)
   registry[c.event_id]=digest(binding)
   ds.append(dict(sid=sid,sector=sec,mark=p,floor=f,quantity=asdict(rule),fees=asdict(a.market.fees(sid,clock.earliest_execution_at)),max_q=maximum,role='mobile',pool='confirmed',use=use,industry_target=a.policy.nd*(D('.8') if use=='S' else D('.2')),
    priority=list(i['priority']),eligible=True,receipt_valid=True,known_at=at.isoformat(),price_known_at=a.market.known[sid].isoformat(),receipt_id=c.event_id,receipt_binding=binding,deadline=i['deadline'].isoformat()))
  s=dict(account_id='synthetic-C-account',target_id='C|'+at.isoformat(),receipt_registry=registry,other_saved_goal_need=Z,analysis_only=False,at=at.isoformat(),deadline=deadline.isoformat(),nav=bal['nav'],decision_nav=a.policy.nd,
   available=a.available,pending_fees=sum((o.fee_reserved_cny for o in a.buys.values()),Z),lots=lots,rows=rows,assets=[],targets={sec:a.policy.targets(sec) for sec in a.policy.scopes if sec!='G'})
  wait=active_need or pending_goals or old_funding or unsettled
  return s,ds,dict(wait=wait,reason='WAIT_NATIVE_OLD_GOAL_RECONCILIATION' if wait else None)
 def _solve(self,s,ds,e,budget_before):
  cls=BatchBook if self.mode=='C_BATCH20' else OffBook
  book=cls.loads(budget_before,trusted_sha256=hashlib.sha256(budget_before.encode()).hexdigest(),account_id=s['account_id'],source_binding=digest(s),actual_commitments=json.loads(budget_before)['body']['lines'])
  if self.mode=='C_BATCH20':return BC.solve_C20(s,ds,e,book=book)
  result=C.solve_C(s,ds,e)
  working=copy.deepcopy(book);working.approve(book.batch['id']+'|complete_target_plan',{str(p['layer']):p['q'] for p in result['donors']['rows']},target_binding=digest(dict(Q=result['Q'],receipts=[d['receipt_id'] for d in ds])))
  return dict(result,budget_before=budget_before,budget_after=working.dumps())
 def verify_native(self,cert):
  require(cert['certificate_id']==digest({k:v for k,v in cert.items() if k!='certificate_id'}),'certificate hash')
  v=self.trusted[cert['trusted_id']];require(cert['mode']==self.mode and cert['source_binding']==self.source_binding(),'C policy/source binding')
  s,ds,e,bb=v['snapshot'],v['demands'],v['evidence'],v['budget_before']
  require(cert['trusted_id']==digest(dict(s=s,ds=ds,e=e,bb=bb)),'trusted input body changed')
  require(cert['snapshot_hash']==digest(s) and cert['target_id']==s['target_id'] and cert['known_at']==s['at'] and cert['deadline']==s['deadline'],'certificate envelope clock/target/snapshot')
  result=self._solve(s,ds,e,bb)
  require(digest(result)==cert['projection_hash'] and cert['Q']==result['Q'] and cert['D']==result['D'],'trusted C recomputation mismatch')
  require(cert['receipt_bindings']=={d['sid']:d['receipt_binding'] for d in ds},'receipt binding changed')
  # Original projection is retained byte-semantically; its analysis-only flag
  # is not turned into an execution permission.
  require(result['analysis_only'] and not result['submit_allowed'],'projection classification changed')
  return result
 def plan(self,intents,clock):
  e=self.industry_evidence;s,ds,wait=self.provider(clock.decision_at,intents,e)
  self._init_or_bind(s,intents,e)
  if wait['wait']:self.results.append(dict(at=s['at'],state=wait['reason']));return dict(state=wait['reason'],reductions=[])
  before=self.budget.dumps();result=self._solve(s,ds,e,before)
  tid=digest(dict(s=s,ds=ds,e=e,bb=before));self.trusted[tid]=dict(snapshot=copy.deepcopy(s),demands=copy.deepcopy(ds),evidence=copy.deepcopy(e),budget_before=before)
  cert=dict(schema='C_NATIVE_AUTHORITY_V1',mode=self.mode,target_id=s['target_id'],known_at=s['at'],deadline=s['deadline'],snapshot_hash=digest(s),trusted_id=tid,source_binding=self.source_binding(),Q=result['Q'],D=result['D'],receipt_bindings={d['sid']:d['receipt_binding'] for d in ds},projection_hash=digest(result))
  cert['certificate_id']=digest(cert);self.verify_native(cert);self.authority.accept(cert)
  # Budget-after is the SAME persistent book, restored with exact byte/hash
  # checks; it retains all previous batch/plan/event state, not new_book().
  cls=BatchBook if self.mode=='C_BATCH20' else OffBook
  self.budget=cls.loads(result['budget_after'],trusted_sha256=hashlib.sha256(result['budget_after'].encode()).hexdigest(),account_id=s['account_id'],source_binding=digest(s),actual_commitments=json.loads(result['budget_after'])['body']['lines'])
  self.active=cert;self.active_intents={i['sid']:copy.deepcopy(i) for i in intents}
  for sid,info in result['C_rank_binding']['stock_priority'].items():
   if sid in self.active_intents:
    self.active_intents[sid]['original_priority']=tuple(info['original_key']);self.active_intents[sid]['priority']=tuple(info['C_key'])
  self.results.append(dict(at=s['at'],certificate=cert,projection=result))
  for part in result['donors']['rows']:self.account.trim(part['layer'],part['q'],clock,'actionable_S_funding')
  self.assert_observers();return dict(state='NATIVE_BOUND',certificate=cert['certificate_id'],reductions=result['donors']['rows'])
 def source_binding(self):
  paths=[Path(__file__),Path(N.__file__),Path(C.__file__),Path(BC.__file__),Path(B.__file__),Path(J.__file__),Path(inspect.getsourcefile(BatchBook)),Path(inspect.getsourcefile(Policy)),Path(N.SELECTED.__file__)]
  paths += [Path(inspect.getsourcefile(c)) for c in N.C.Account.__mro__ if c is not object]
  paths += [Path(inspect.getsourcefile(F1.step)),Path(inspect.getsourcefile(T.QuantityRule)),Path(inspect.getsourcefile(LR.fees)),Path(N.IO.__file__),Path(N.__file__).with_name('imports_native.py'),Path(N.__file__).with_name('funding_coverage.py')]
  im=sys.modules['imports_native'];paths += [im.RULES_PATH,im.BASE,im.V2,im.MANIFEST]
  return {str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(set(paths))}
 def planning(self,at,observations,stock_packet=None,*,next_open=None,industry_evidence=None):
  require(industry_evidence is not None,'industry evidence required');self.industry_evidence=copy.deepcopy(industry_evidence)
  self._close_at=at;self._close_packet=copy.deepcopy(stock_packet or {})
  self._close_support_before={sec:self.account._current_holding_support(sec) for sec in set(self.account.market.sectors.values())}
  # Original scheduler supplies original F1/ACT/line/canonical order. K and
  # funding hooks above are the only replaced tail of that scheduler.
  x=super().planning(at,observations,stock_packet,next_open=next_open);self.assert_observers();return x
 def opening(self,intents,at,capacities=None,*,buy_windows=None):
  a=self.account;a.last_cursor=at;a.settle_due(at);a.revalidate_batch(at)
  out=[];funded=[];done=set(a.buys)
  cert=self.active
  if cert and at<=iso(cert['deadline']):
   self.verify_native(cert)
   for sid in sorted(cert['Q'],key=lambda sid:(self.active_intents[sid]['priority'],sid)):
    if not cert['Q'][sid] or sid in done:continue
    if any(o['cid']==cert['certificate_id'] and o['sid']==sid for o in self.authority.orders.values()):continue
    i=self.active_intents[sid];use=next(d['use'] for d in self.trusted[cert['trusted_id']]['demands'] if d['sid']==sid)
    x=a.submit_fixed(i,at,use=use,role='mobile',q=cert['Q'][sid],cid=cert['certificate_id']);out.append(x)
    if x['q']:done.add(sid);funded.append((sid,x['order_id']))
  # Original independent core/trial path, after confirmed C reservations.
  for i in sorted(a.pending,key=lambda i:(i['priority'],i['sid'])):
   if i['sid'] in done or at>i['deadline']:continue
   x=a.submit(i,at,use='T');out.append(x)
   if x['q']:done.add(i['sid']);funded.append((i['sid'],x['order_id']))
  for sid,o in a.buys.items():
   if sid not in {s for s,_ in funded}:funded.append((sid,o.order_id))
  a.native_callbacks.append(dict(kind='entire_C_batch_reserved_before_windows',at=at,orders=funded,available=a.available))
  for sid,oid in funded:
   if buy_windows is not None:w=buy_windows(sid,at)
   else:w=T.window(sid,a.market.prices[sid]*(ONE+LR.SLIP),at,capacity=(capacities or {}).get(sid,10**8),fees=a.market.fees(sid,at),rule=a.market.quantity(sid,at),eid='buy|'+oid+'|'+at.isoformat(),raw_open=a.market.prices[sid],sellable_at=at+timedelta(days=1),cash_due_at=at)
   if w:self.apply_window('buy',sid,w)
  a.settle_due(at);self.assert_observers();return out
 def apply_window(self,side,sid,w):
  key=side+'|'+w.event_id;payload=digest(asdict(w))
  if key in self.windows:require(self.windows[key]==payload,'same window changed');return None
  backup=pickle.dumps(self)
  try:
   f=self.account.fill_buy(sid,w) if side=='buy' else self.account.fill_exit(sid,w)
   self.assert_observers();self.windows[key]=payload;return f
  except Exception:
   prior=pickle.loads(backup);self.__dict__.clear();self.__dict__.update(prior.__dict__);self.account.owner=self;raise
 def event(self,at,*,event_id=None,industry_evidence=None,**kwargs):
  event_id=event_id or at.isoformat();payload=digest(dict(at=at,industry_evidence=industry_evidence,kwargs={k:v for k,v in kwargs.items() if not callable(v)}))
  if event_id in self.event_ids:require(self.event_ids[event_id]==payload,'changed native event identity');return self.account.bridge(at)
  backup=pickle.dumps(self)
  try:
   if kwargs.get('observations') is not None:
    self.industry_evidence=industry_evidence
    require(industry_evidence is not None,'industry evidence required')
   # Parent event calls self.planning; preserve its explicit evidence argument.
   obs=kwargs.pop('observations',None);stocks=kwargs.pop('stocks',None)
   require(self.last_completed_event is None or at>self.last_completed_event,'event clock replay')
   a=self.account;a.last_cursor=at;a.settle_due(at)
   for action in kwargs.pop('actions',()):require(action['at']==at,'misdated action');a.split(**action)
   for p in kwargs.pop('payments',()):require(p['at']==at and p['payment_known_at']<=at,'future payment');a.pay_dividend(**p)
   for sid in kwargs.pop('cancel_acks',()):a.ack_buy_cancel(sid)
   for sid,accepted in kwargs.pop('funding_cancel_acks',()):
    a.ack_funding_cancel(sid,at,accepted=accepted)
    if accepted and self.budget:
     for key,z in self.budget.lines.items():
      if z['sid']==sid and z['opp']:
       self.budget.cancel_request(key,at=at.isoformat(),source_binding=self.budget.source_binding)
       self.budget.cancel_ack(key,at=at.isoformat(),source_binding=self.budget.source_binding)
   if kwargs.pop('is_open',False):
    sells=kwargs.pop('sell_windows',None)
    for sid in sorted(tuple(a.exits)):
     w=sells(sid,at) if sells else T.window(sid,a.market.prices[sid]*(ONE-LR.SLIP),at,fees=a.market.fees(sid,at),rule=a.market.quantity(sid,at),eid='sell|'+a.exits[sid].event_id+'|'+at.isoformat(),raw_open=a.market.prices[sid],cash_due_at=at)
     if w:self.apply_window('sell',sid,w)
    a.settle_due(at);self.opening(None,at,kwargs.pop('capacities',None),buy_windows=kwargs.pop('buy_windows',None))
   if obs is not None:self.planning(at,obs,stocks,industry_evidence=industry_evidence,next_open=kwargs.pop('next_open',None))
   else:self.last_completed_event=at
   require(not kwargs,'unsupported event fields '+str(kwargs));self.assert_observers();b=a.bridge(at)
   self.event_ids[event_id]=payload;return b
  except Exception:
   prior=pickle.loads(backup);self.__dict__.clear();self.__dict__.update(prior.__dict__);self.account.owner=self;raise
 def binding(self):return dict(mode=self.mode,source=self.source_binding(),engine=IO.runner_identity(self),scope='native synthetic only; no history loader',parent_plan='76fe675c45f49550b700d584ac5ff5144a3a6bc89ca028c744c6d544fe596e74')
 def checkpoint(self,path):
  self.assert_observers();path=Path(path);IO.write_pickle(path,self);IO.write_json(path.with_suffix('.provenance.json'),dict(checkpoint_sha256=N.sha(path),engine_identity=IO.runner_identity(self),binding=self.binding()))
 @classmethod
 def restore(cls,path):
  side=json.loads(Path(path).with_suffix('.provenance.json').read_text());probe=cls(side['binding']['mode']);IO.assert_checkpoint_identity(probe,path)
  require(probe.binding()==side['binding'],'source/mode binding changed')
  with Path(path).open('rb') as f:r=pickle.load(f)
  require(r.binding()==side['binding'],'restored binding changed');r.account.owner=r;r.assert_observers()
  for c in r.authority.certificates.values():r.verify_native(c)
  return r
 def observable(self,at):
  return dict(account=self.account.exported(at),budget=self.budget.dumps() if self.budget else None,authority=self.authority.__dict__,transitions=self.transitions,active=self.active,
   f1={s:asdict(v) for s,v in self.f1.items()},f1seq=self.f1seq,last_completed=self.last_completed_event,event_ids=self.event_ids,windows=self.windows,results=self.results)
