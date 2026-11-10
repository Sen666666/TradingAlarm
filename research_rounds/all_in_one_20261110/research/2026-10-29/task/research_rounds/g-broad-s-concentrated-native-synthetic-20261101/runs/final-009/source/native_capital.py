"""V2 synthetic integration. Native C.Account owns ALL financial state.

This is a fixture-facing adapter, not a historical runner. I/CP1 and priority
inputs are explicit causal fixtures; F1 itself is the frozen original kernel.
"""
from dataclasses import replace,asdict,dataclass
from datetime import datetime,timedelta,date
from decimal import Decimal as D,ROUND_FLOOR
from pathlib import Path
import json,hashlib,pickle,inspect
from imports_native import C,LR,T,F1,IO,O,COMPOSITE,fees,quantity,sha
from policy import Policy,UnknownRisk
Z=D(0);ONE=D(1)
@dataclass(frozen=True)
class CanonicalReceipt:
 event_id:str
 sid:str
 start:datetime
 end:datetime
 confirmed:datetime
 structure:tuple
 source:str='original_stock_CP1_fixture_interface'
 scale:str='21'

def encode(x):
 if isinstance(x,(D,date,Path)):return str(x)
 if isinstance(x,set):return sorted(x)
 if hasattr(x,'__dataclass_fields__'):return asdict(x)
 raise TypeError(type(x).__name__)
def digest(x):return hashlib.sha256(json.dumps(x,default=encode,sort_keys=True,separators=(',',':')).encode()).hexdigest()

class FixtureMarket:
 def __init__(self):
  self.protocol={'fractional_split_policy':'floor_position_fraction_writeoff'};self.prices={};self.factors={};self.sectors={};self.stars={};self.known={}
 def set(self,sid,price,at,sector='S',star=True):
  self.prices[sid]=D(str(price));self.known[sid]=at;self.sectors[sid]=sector;self.stars[sid]=star;self.factors.setdefault(sid,ONE)
 def marks(self,at,positions):return {s:T.Mark(self.prices[s],self.known[s],T.fx(1,self.known[s]),'synthetic-asof-mark') for s in positions}
 def quote(self,sid,at):
  return replace(T.quote(sid,self.prices[sid],sector=self.sectors[sid],fees=fees(at,self.stars[sid]),rule=quantity(at,self.stars[sid])),known_at=at,fx=T.fx(1,at))
class FixtureFacts:
 def __init__(self,market):self.market=market;self.floors={};self.structure_lookup={}
 def factor(self,sid,at):return self.market.factors[sid]
 def floor(self,sid,at,kind):return self.floors.get(sid)

class CapitalAccount(C.Account):
 def __init__(self,label='G_S_V2'):
  market=FixtureMarket();facts=FixtureFacts(market);super().__init__(label,market,facts,False,1,0)
  self.policy=Policy();self.capital_meta={};self.supports={};self.cancel_requests=set();self.native_callbacks=[];self.rejections=[];self.dividend_income=Z
  self.share_ratio={};self.source_binding={};self.last_cursor=None
 def mark(self,sid,price,at,sector='S',star=True,floor=None):
  self.market.set(sid,price,at,sector,star);self.share_ratio.setdefault(sid,ONE)
  if floor is not None:self.facts.floors[sid]=D(str(floor))*self.facts.factor(sid,at)
 def raw_floor(self,z):
  f=self.facts.floor(z['sid'],self.last_cursor,'I') if z['kind']=='core' else z['floor']
  if f is None:raise UnknownRisk('missing native effective floor')
  return f/self.facts.factor(z['sid'],self.last_cursor)
 def nav(self,at):return self.balance(at,self.market.marks(at,self.positions))['nav']
 def snapshot(self,at):
  self.last_cursor=at
  for z in self.layers:
   if not z['qty']:continue
   locked=sum(e.remaining for e in self.policy.locks.values() if e.lot==z['id'])
   if not locked:self.policy.snapshot(z['id'],mark=self.market.prices[z['sid']],floor=self.raw_floor(z),ratio=self.share_ratio[z['sid']],cursor=at,qty=z['qty'],source='native-asof-pre-ratchet')
 def resources(self,*,exclude_order=None):
  rows=[]
  for z in self.layers:
   if not z['qty']:continue
   s=z['sid'];m=self.market.prices.get(s)
   if m is None or self.market.known.get(s) is None:raise UnknownRisk('missing native mark/source '+s)
   floor=self.raw_floor(z);locks=[e for e in self.policy.locks.values() if e.lot==z['id'] and e.remaining]
   locked=sum(e.remaining for e in locks);assert locked<=z['qty'],'overlapping exit tranches'
   risk=D(z['qty']-locked)*max(Z,m-floor)+sum((e.charge(m,floor) for e in locks),Z)
   meta=self.capital_meta[z['id']]
   rows.append(dict(sid=s,sector=meta['sector'],pool=meta['pool'],role=meta['role'],capital=D(z['qty'])*m,risk=risk,reserve=Z,kind='lot',id=z['id']))
  for sid,o in self.buys.items():
   if o.order_id==exclude_order:continue
   i=self.order_meta[o.order_id];m=self.supports[o.order_id]
   floor=i['floor']/self.facts.factor(sid,self.last_cursor)
   rows.append(dict(sid=sid,sector=m['sector'],pool=m['pool'],role=m['role'],capital=o.remaining_budget_cny,risk=D(o.remaining_shares)*max(Z,m['limit']-floor),reserve=o.remaining_budget_cny+o.fee_reserved_cny,kind='cancel_pending' if sid in self.cancel_requests else 'order',id=o.order_id))
  return rows
 def totals(self,rows=None):
  rows=self.resources() if rows is None else rows
  return {k:sum((r[k] for r in rows),Z) for k in ('capital','risk','reserve')}
 def intent(self,sid,clock,*,receipt=None,core=True,stock_q=True,i_valid=True,cp_floor=None,priority=(0,),deadline=None):
  q=self.market.quote(sid,clock.decision_at);floor=self.facts.floor(sid,clock.decision_at,'I')
  if isinstance(receipt,str):receipt=CanonicalReceipt(receipt,sid,clock.decision_at-timedelta(days=1),clock.decision_at,clock.decision_at,(0,1))
  return dict(sid=sid,sector=q.sector_id,clock=clock,quote=q,receipt=receipt,core=core,stock_q=stock_q,i_valid=i_valid,cp_floor=cp_floor,priority=tuple(priority),deadline=deadline or clock.earliest_execution_at.replace(hour=15,minute=10),I_floor=floor,epoch=(0,1))
 def _preview(self,i,use,role,at,*,exclude_order=None,cap=None):
  sid=i['sid'];p=self.market.prices[sid]*(ONE+LR.SLIP);rule=quantity(at,self.market.stars[sid]);schedule=fees(at,self.market.stars[sid]);nd=self.policy.nd
  if not i['i_valid'] or not i['stock_q']:return dict(q=0,why=['stock_I_Q'],use=use,role=role)
  scope='G' if use=='G' else i['sector']
  if not self.policy.allowed(scope,use):return dict(q=0,why=['permission'],use=use,role=role)
  if sid in self.exits or (sid in self.buys and self.buys[sid].order_id!=exclude_order):return dict(q=0,why=['native_responsibility'],use=use,role=role)
  if not exclude_order and role=='mobile':
   c=i['receipt'];valid=isinstance(c,CanonicalReceipt) and c.sid==sid and c.source=='original_stock_CP1_fixture_interface' and c.scale=='21' and c.structure==i['epoch'] and c.start<=c.end<=c.confirmed==i['clock'].decision_at<at and c.event_id not in self.policy.consumed
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
  if target<=0:return dict(q=0,why=['K_inactive'],use=use,role=role)
  pool='probe' if use=='T' else 'confirmed'
  budget=min(nd*D('.1'),max(Z,target-sum((r['capital'] for r in sec),Z)))
  if use=='T' and role=='mobile':budget=min(budget,nd*D('.02'))
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
   if use=='T':
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
  return dict(q=q,why=[] if q else (['target_minimum'] if upper<rule.buy_minimum else reasons(rule.buy_minimum)),use=use,role=role,pool=pool,p=p,floor=floor,budget=budget,limit=p,schedule=schedule,minimum=rule.buy_minimum,step=rule.buy_step,actual_nav=current,decision_nav=nd)
 def route(self,i,at,*,use=None):
  if at>i['deadline']:return dict(q=0,why=['original_deadline'])
  # G/S1: independent mobile first. Trial: original core-first fallback.
  candidates=[]
  for use in ((use,) if use else ('S','G','T')):
   roles=('core','mobile') if use=='T' else ('mobile','core')
   # Core can never become a large G/S1 order.
   for role in roles:
    if role=='core' and use!='T':continue
    x=self._preview(i,use,role,at);candidates.append(x)
    if x['q']:
     g=self._preview(i,'G',role,at)
     x['g_backup']=min(g['q'],x['q']);x['g_context']=self.policy.scopes.get('G').context if self.policy.scopes.get('G') else None
     x['alternatives']=[dict(v) for v in candidates];return x
  return dict(q=0,why=[x['why'] for x in candidates],alternatives=candidates)
 def submit(self,i,at,*,use=None):
  self.last_cursor=at;x=self.route(i,at,use=use)
  if not x['q']:self.rejections.append(dict(at=at,sid=i['sid'],route=x));return x
  q=x['q'];meta=dict(i,kind='core' if x['role']=='core' else 'add',floor=x['floor']*self.facts.factor(i['sid'],at),budget=x['budget'],cap=q,score=90,reason='V2_'+x['use'],risk_budget=self.policy.nd*D('.0025'))
  oid=self.reserve_quantity(meta,q,x['p'],x['schedule'],at)
  self.supports[oid]=dict(sector=i['sector'],pool=x['pool'],role=x['role'],use=x['use'],context=self.policy.scopes['G' if x['use']=='G' else i['sector']].context,limit=x['p'],deadline=i['deadline'],priority=i['priority'],receipt=i['receipt'],quantity=q,g_backup=x['g_backup'],g_context=x['g_context'],g_original_gross=D(x['g_backup'])*x['p'],g_original_fee=LR.fees(x['g_backup'],x['p'],x['schedule'],'buy'),created_at=at,original_intent=i)
  if x['role']=='mobile':assert i['receipt'].event_id not in self.policy.consumed;self.policy.consumed.add(i['receipt'].event_id)
  x['order_id']=oid;return x
 def fill_buy(self,sid,w):
  o=self.buys.get(sid)
  if not o:return None
  support=self.supports[o.order_id]
  if w.at>support['deadline'] or sid in self.cancel_requests:return None
  self.last_cursor=w.at
  amendment=self.revalidate(sid,w.at)
  if amendment['status']!='amended':return None
  old=len(self.layers);f=super().fill_buy(sid,w)
  if f:
   z=self.layers[-1];assert len(self.layers)==old+1
   self.capital_meta[z['id']]=dict(sector=support['sector'],pool=support['pool'],role=support['role'],purpose=support['use'],source_context=support['context'],order=o.order_id,unit_cost=f.gross_cny/D(f.shares),ratio=self.share_ratio[sid])
   self.policy.snapshot(z['id'],mark=self.market.prices[sid],floor=self.raw_floor(z),ratio=self.share_ratio[sid],cursor=w.at,qty=z['qty'],source='native-actual-fill-known-mark-floor')
   self.policy.record_loss(support['sector'],support['context'],f.fees_cny)
   self.native_callbacks.append(dict(kind='native_buy',receipt=f.receipt_id,layer=z['id'],shares=f.shares))
  return f
 def migrate(self,lot_id):
  """Optional actual metadata transfer; never relabel pending or create cash."""
  z=next(z for z in self.layers if z['id']==lot_id);m=self.capital_meta[lot_id];sid=z['sid'];sec=m['sector']
  if m['pool']!='probe':return False
  if sid in self.buys or sid in self.cancel_requests:return False
  use='S' if sec in self.policy.k and self.policy.allowed(sec,'S',holding=True) else ('G' if self.policy.allowed('G','G',holding=True) else None)
  if use is None:return False
  target=self.policy.targets(sec) if use=='S' else self.policy.nd*D('.2')
  if sum((r['capital'] for r in self.resources() if r['sector']==sec),Z)>target:return False
  before=(self.available,self.nav(self.last_cursor),self.totals(),dict(self.policy.losses))
  m['pool']='confirmed';m['purpose']=use
  assert before==(self.available,self.nav(self.last_cursor),self.totals(),dict(self.policy.losses))
  return True
 def request_buy_cancel(self,sid):
  if sid in self.buys:self.cancel_requests.add(sid);self.native_callbacks.append(dict(kind='cancel_requested',sid=sid))
 def ack_buy_cancel(self,sid):
  self.cancel_requests.discard(sid);return self.cancel_buy(sid)
 def revalidate(self,sid,at):
  """Shrink only, before native fill. No new order/receipt/lifetime."""
  o=self.buys.get(sid)
  if not o:return dict(status='absent')
  m=self.supports[o.order_id];i=m['original_intent'];use=m['use'];scope='G' if use=='G' else m['sector'];s=self.policy.scopes.get(scope)
  if sid in self.cancel_requests:return dict(status='cancel_pending',q=o.remaining_shares)
  if at>m['deadline']:
   self.request_buy_cancel(sid);return dict(status='cancel_requested',reason='original_deadline')
  same=bool(s and s.context==m['context'] and self.policy.allowed(scope,use))
  cap=o.remaining_shares
  if not same:
   g=self.policy.scopes.get('G');cap=min(cap,max(0,m['g_backup']-o.filled_shares))
   if not (cap and g and g.context==m['g_context'] and self.policy.allowed('G','G')):
    self.request_buy_cancel(sid);return dict(status='cancel_requested',reason='no_original_support')
   use='G'
  if use=='G':
   remaining_gross=max(Z,m['g_original_gross']-o.local_notional)
   cap=min(cap,int(remaining_gross/(self.market.prices[sid]*(ONE+LR.SLIP))))
  x=self._preview(i,use,m['role'],at,exclude_order=o.order_id,cap=cap)
  if not x['q']:
   self.request_buy_cancel(sid);return dict(status='cancel_requested',reason=x['why'])
  q=x['q'];newgross=D(q)*x['p'];fee=sum(self._fee(o,x['schedule'],'buy',newgross,shares=q).values(),Z)
  if use=='G' and fee>max(Z,m['g_original_fee']-sum(o.fees_local.values(),Z)):
   self.request_buy_cancel(sid);return dict(status='cancel_requested',reason='original_G_fee_allowance')
  oldgross=o.remaining_budget_cny;oldfee=o.fee_reserved_cny
  assert q<=o.remaining_shares and newgross<=oldgross
  if self.available+oldgross+oldfee<newgross+fee:raise AssertionError('non-atomic amendment cash')
  self.available+=oldgross+oldfee-newgross-fee;o.remaining_budget_cny=newgross;o.fee_reserved_cny=fee;o.remaining_shares=q;o.submitted_remaining=min(o.submitted_remaining,q)
  m['limit']=x['p'];m['use']=use
  if use=='G':m['context']=m['g_context']
  self.native_callbacks.append(dict(kind='amend_before_fill',order=o.order_id,q=q,use=use,gross=newgross,fees=fee))
  return dict(status='amended',q=q,use=use,gross=newgross,fees=fee)
 def trim(self,lot_id,qty,clock,reason='allocation_trim'):
  z=next(z for z in self.layers if z['id']==lot_id);sid=z['sid'];assert 0<qty<=z['qty']
  # Minimal native integration selects one layer per stock exit obligation.
  if sid in self.exits:raise ValueError('existing exit responsibility must finish; no overlapping resize')
  self.policy.lock(lot_id,sid,qty,self.share_ratio[sid],reason);self.sell_layers[sid]={lot_id};z['reason']=reason
  self.request_reduction(self.market.quote(sid,clock.decision_at),clock,qty)
  for e in self.policy.locks.values():
   if e.lot==lot_id and e.remaining:e.native_exit=self.exits[sid].event_id
 def funding_reductions(self,intents,clock):
  """Bounded new-S demand -> real pro-rata G reductions, NOT sale credit.

  Uses actual quote/lot/fee rules. Multiple selected economic layers of the same
  stock are intentionally rejected pending native layer-exit arbitration.
  """
  demands={};seen=set();items=[]
  for i in sorted(intents,key=lambda x:(x['priority'],x['sid'])):
   sid=i['sid'];sec=i['sector'];c=i['receipt']
   if sid in seen:continue
   seen.add(sid)
   legal=isinstance(c,CanonicalReceipt) and c.event_id not in self.policy.consumed and c.sid==sid and c.start<=c.end<=c.confirmed==clock.decision_at==i['clock'].decision_at and i['deadline']>=clock.earliest_execution_at and c.structure==i['epoch'] and c.scale=='21' and c.source=='original_stock_CP1_fixture_interface'
   if not (legal and i['stock_q'] and i['i_valid'] and self.policy.allowed(sec,'S') and sec in self.policy.k) or sid in self.exits or sid in self.buys:continue
   rows=self.resources();stock=sum((r['capital'] for r in rows if r['sid']==sid),Z);sector=sum((r['capital'] for r in rows if r['sector']==sec),Z)
   budget=min(max(Z,self.policy.nd*D('.1')-stock),max(Z,self.policy.targets(sec)-sector-demands.get(sec,Z)))
   p=self.market.prices[sid]*(ONE+LR.SLIP);floor=max(i['I_floor'],D(i['cp_floor']))/self.facts.factor(sid,clock.decision_at);rule=quantity(clock.earliest_execution_at,self.market.stars[sid]);schedule=fees(clock.earliest_execution_at,self.market.stars[sid])
   if self.market.prices[sid]<=floor:continue
   q=LR.maximum_quantity(rule,int(budget/p),lambda n:D(n)*(p-floor)<=self.policy.nd*D('.05'))
   if not q:continue
   gross=D(q)*p;demands[sec]=demands.get(sec,Z)+gross;items.append(dict(sid=sid,sector=sec,q=q,gross=gross,cash=gross+LR.fees(q,p,schedule,'buy')))
  cash_need=max(Z,sum((x['cash'] for x in items),Z)-max(Z,self.available-self.policy.nd*D('.1')))
  if not cash_need:return dict(demand=items,needed=Z,reductions=[])
  available=[z for z in self.layers if z['qty'] and z['sid'] not in self.exits and self.capital_meta[z['id']]['purpose']=='G' and self.capital_meta[z['id']]['sector'] not in demands]
  if len({z['sid'] for z in available})!=len(available):raise ValueError('multi-layer native exit arbitration not wired in minimal harness')
  requested=[];left=cash_need
  for role in ('mobile','core'):
   group=sorted([z for z in available if self.capital_meta[z['id']]['role']==role],key=lambda z:(z['sid'],z['id']))
   def plan(frac):
    rows=[]
    for z in group:
     sid=z['sid'];rule=quantity(clock.earliest_execution_at,self.market.stars[sid]);q=rule.sell_floor(int(D(z['qty'])*frac),z['qty'])
     p=self.market.prices[sid]*(ONE-LR.SLIP);net=D(q)*p-LR.fees(q,p,fees(clock.earliest_execution_at,self.market.stars[sid]),'sell') if q else Z
     rows.append(dict(lot=z['id'],sid=sid,q=q,estimated_net=net))
    return rows
   if not group:continue
   full=plan(ONE);fullcash=sum((x['estimated_net'] for x in full),Z);lo=Z;hi=ONE
   if fullcash>=left:
    for _ in range(80):
     mid=(lo+hi)/2
     if sum((x['estimated_net'] for x in plan(mid)),Z)>=left:hi=mid
     else:lo=mid
    rows=plan(hi)
   else:rows=full
   for x in rows:
    if x['q']:self.trim(x['lot'],x['q'],clock,'actionable_S_funding');requested.append(x)
   left=max(Z,left-sum((x['estimated_net'] for x in rows),Z))
   if not left:break
  self.native_callbacks.append(dict(kind='funding_reductions_requested',demand=items,needed=cash_need,reductions=requested,still_unfunded=left,estimated_is_not_cash=True))
  return dict(demand=items,needed=cash_need,reductions=requested,still_unfunded=left)
 def withdraw_to_remaining_support(self,clock):
  """Price-support loss, not P lapse. Existing exit obligations never cancel."""
  result=[]
  for sec in sorted({self.capital_meta[z['id']]['sector'] for z in self.layers if z['qty']}):
   s=self.policy.scopes.get(sec);g=self.policy.scopes.get('G')
   if s and s.support and s.mature and sec in self.policy.k:continue
   limit=self.policy.nd*(D('.20') if g and g.support else (D('.02') if s and s.support else Z))
   group=[z for z in self.layers if z['qty'] and self.capital_meta[z['id']]['sector']==sec]
   value=sum((D(z['qty'])*self.market.prices[z['sid']] for z in group),Z)
   already=sum((D(self.exits[z['sid']].remaining_target if self.exits[z['sid']].remaining_target is not None else z['qty'])*self.market.prices[z['sid']] for z in group if z['sid'] in self.exits),Z)
   excess=max(Z,value-limit-already)
   # Component regression uses single economic layer per stock. Reject ambiguity.
   if len({z['sid'] for z in group})!=len(group):raise ValueError('multi-layer support-exit arbitration not wired')
   for role in ('mobile','core'):
    selected=sorted([z for z in group if z['sid'] not in self.exits and self.capital_meta[z['id']]['role']==role],key=lambda z:(z['sid'],z['id']))
    total=sum((D(z['qty'])*self.market.prices[z['sid']] for z in selected),Z)
    if not excess or not total:continue
    take=min(excess,total);fraction=take/total;plan=[]
    for z in selected:
     rule=quantity(clock.earliest_execution_at,self.market.stars[z['sid']]);q=rule.sell_floor(int(D(z['qty'])*fraction),z['qty']);plan.append([z,q,rule])
    cut=sum((D(q)*self.market.prices[z['sid']] for z,q,rule in plan),Z)
    for entry in plan:
     if cut>=take:break
     z,q,rule=entry;new=min(z['qty'],q+rule.sell_step);cut+=D(new-q)*self.market.prices[z['sid']];entry[1]=new
    for z,q,rule in plan:
     if q:self.trim(z['id'],q,clock,'remaining_support_target');result.append(dict(lot=z['id'],sid=z['sid'],shares=q,sector_cap=limit))
    excess=max(Z,excess-cut)
  return result
 def fill_exit(self,sid,w):
  old=len(self.trades);f=super().fill_exit(sid,w)
  if f:
   assert len(self.trades)==old+1
   for part in self.trades[-1]['parts']:
    self.policy.consume_exit(part['layer'],part['shares']);m=self.capital_meta[part['layer']]
    loss=max(Z,m['unit_cost']-w.execution_price)*part['shares']+f.fees_cny*D(part['shares'])/f.shares
    self.policy.record_loss(m['sector'],m['source_context'],loss)
   self.native_callbacks.append(dict(kind='native_sell',receipt=f.receipt_id,shares=f.shares))
  return f
 def split(self,**kw):
  sid=kw['sid'];ex=self.exits.get(sid);remaining=ex.remaining_target if ex else None
  super().split(**kw)
  # Isolated repair: pilot wrapper incorrectly broadens a partial reduction.
  if ex and remaining is not None:
   ex.remaining_target=int(D(remaining)*kw['ratio']);ex.submitted_remaining=min(ex.submitted_remaining,ex.remaining_target)
  self.policy.split(sid,kw['ratio']);self.share_ratio[sid]*=kw['ratio'];self.market.factors[sid]*=kw['ratio'];self.market.prices[sid]/=kw['ratio']
  for z in self.live(sid):self.capital_meta[z['id']]['unit_cost']/=kw['ratio']
  for o in self.buys.values():
   if o.quote.security_id==sid:
    m=self.supports[o.order_id];m['quantity']=int(D(m['quantity'])*kw['ratio']);m['g_backup']=int(D(m['g_backup'])*kw['ratio']);m['limit']/=kw['ratio']
  self.native_callbacks.append(dict(kind='native_split',event=kw['event_id'],sid=sid,ratio=kw['ratio']))
 def accrue_dividend(self,**kw):
  before=kw['event_id'] in self.action_events;super().accrue_dividend(**kw)
  if not before:self.dividend_income+=kw['net_local']
 def bridge(self,at):
  self.check();b=self.balance(at,self.market.marks(at,self.positions));flows=sum((f.gross_cny if f.side=='sell' else -f.gross_cny for f in self.fills),Z)
  journal_nav=D(1000000)+flows-self.fees_cny+self.dividend_income+b['inventory']
  assert b['nav']==journal_nav,(b,journal_nav)
  paid_income=self.dividend_income-b['dividend_receivable']
  cash_assets=b['available']+b['order_reserved']+b['sale_receivable']
  expected_cash=D(1000000)+flows-self.fees_cny+paid_income
  assert cash_assets==expected_cash,(cash_assets,expected_cash)
  layer_cash=sum((z['cash'] for z in self.layers),Z)
  assert layer_cash==flows-self.fees_cny
  for t in self.trades:assert D(t['shares'])*t['price']==t['gross_cny']
  assert sum((f.fees_cny for f in self.fills),Z)==self.fees_cny
  assert b['order_reserved']==sum((o.remaining_budget_cny+o.fee_reserved_cny for o in self.buys.values()),Z)
  return dict(**b,journal_nav=journal_nav,independent_nav_difference=b['nav']-journal_nav,journal_cash_assets=expected_cash,cash_asset_difference=cash_assets-expected_cash,layer_cash_difference=layer_cash-(flows-self.fees_cny),inventory_mark_source='same native as-of mark; not an independent price feed',quantities={s:self.quantity(s) for s in self.positions},resources=self.totals())
 def exported(self,at):
  balance=self.bridge(at)
  return dict(balance=balance,policy=self.policy.exported(),layers=self.layers,supports=self.supports,cancel_requests=sorted(self.cancel_requests),buys={s:asdict(o) for s,o in self.buys.items()},exits={s:asdict(o) for s,o in self.exits.items()},trades=self.trades,fills=[asdict(f) for f in self.fills],native_callbacks=self.native_callbacks,capital_meta=self.capital_meta,rejections=self.rejections,
   native_inventory={s:asdict(p) for s,p in self.positions.items()},native_settlements={s:asdict(v) for s,v in self.settlements.items()},native_dividends={s:asdict(v) for s,v in self.dividends.items()},native_actions=sorted(self.action_events),native_completed=[asdict(v) for v in self.completed],core_epochs=self.core_epoch,order_meta=self.order_meta,share_ratio=self.share_ratio,market_marks=self.market.prices,market_asof=self.market.known,market_factors=self.market.factors,facts_floors=self.facts.floors)

class SyntheticRunner:
 def __init__(self):self.account=CapitalAccount();self.f1={};self.f1seq={};self.cursor=0
 def planning(self,at,observations):
  a=self.account;a.last_cursor=at;a.snapshot(at);self.cursor+=1;a.policy.cursor=self.cursor;a.policy.nd=a.nav(at);a.current_nav=a.policy.nd
  packet={}
  for scope,ob in observations.items():
   old=self.f1.get(scope,F1.State(scope));state,dec=F1.step(old,ob);self.f1[scope]=state;self.f1seq[scope]=self.f1seq.get(scope,0)+1
   source=digest(asdict(ob.source));packet[scope+'|'+source]=self.f1seq[scope]
   a.policy.evidence(scope,source,dec.events,dec.permit_next_open,state.mode=='ACTIVE' and state.pending_price_failure is None,self.cursor,self.f1seq[scope])
  # Original ACT pause/high tracking. Recovery is ONLY the V2 scoped proof rule.
  a.policy.act['peak']=max(a.policy.act['peak'],a.policy.nd)
  if a.policy.act['on'] and ONE-a.policy.nd/a.policy.act['peak']>=D('.2'):
   a.policy.start_incident(self.cursor,a.policy.nd,{s+'|'+v.source:v.seq for s,v in a.policy.scopes.items()})
   for z in a.layers:
    if z['qty'] and z['sid'] not in a.exits:
     a.trim(z['id'],z['qty'],T.admission.Clock(at,at+timedelta(days=1),at.date()),'ACT_pause')
  a.policy.unlock(self.cursor,a.policy.nd);return packet
 def route(self,intent,at):return self.account.submit(intent,at)
 def opening(self,intents,at,capacities=None):
  a=self.account;a.settle_due(at);unique={}
  for i in sorted(intents,key=lambda i:(i['priority'],i['sid'])):unique.setdefault(i['sid'],i)
  out={};done=set()
  for use in ('S','G','T'):
   for sid,i in unique.items():
    if sid in done:continue
    x=a.submit(i,at,use=use);out[sid]=x
    if x['q']:
     done.add(sid)  # Reservation, including zero fill, consumes this stock slot.
     q=quantity(at,a.market.stars[sid]);sch=fees(at,a.market.stars[sid]);w=T.window(sid,a.market.prices[sid]*(ONE+LR.SLIP),at,capacity=(capacities or {}).get(sid,10**8),fees=sch,rule=q,eid='buy|'+x['order_id'],raw_open=a.market.prices[sid],sellable_at=at+timedelta(days=1),cash_due_at=at)
     a.fill_buy(sid,w)
  a.settle_due(at);return [out[sid] for sid in unique]
 def binding(self):
  from imports_native import F1_PATH,BASE,V2,MANIFEST,RULES_PATH
  paths={Path(__file__),O/'policy.py',O/'imports_native.py',Path(C.__file__),F1_PATH,BASE,V2,MANIFEST,RULES_PATH,Path(IO.__file__)}
  paths|={Path(inspect.getsourcefile(c)) for c in C.Account.__mro__ if c is not object}
  callbacks={k:IO._code_fingerprint(getattr(CapitalAccount,k).__code__) for k in ('submit','route','fill_buy','fill_exit','split','trim','revalidate','resources','migrate','funding_reductions','withdraw_to_remaining_support')}
  return dict(contract=COMPOSITE,sources={str(p):sha(p) for p in sorted(paths)},engine=IO.runner_identity(self),native_callback_code=callbacks,mode='synthetic_generated_prices_only',history_paths=0)
 def checkpoint(self,path):
  path=Path(path);IO.write_pickle(path,self);IO.write_json(path.with_suffix('.provenance.json'),dict(checkpoint_sha256=sha(path),engine_identity=IO.runner_identity(self),binding=self.binding()))
 @classmethod
 def restore(cls,path):
  probe=cls();IO.assert_checkpoint_identity(probe,path);side=json.loads(Path(path).with_suffix('.provenance.json').read_text())
  if probe.binding()!=side['binding']:raise ValueError('frozen input/source/contract mismatch')
  with Path(path).open('rb') as f:r=pickle.load(f)
  if r.binding()!=side['binding']:raise ValueError('restored method identity mismatch')
  return r
