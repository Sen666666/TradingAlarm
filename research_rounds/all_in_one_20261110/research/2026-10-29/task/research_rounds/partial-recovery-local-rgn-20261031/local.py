from shared import *
class RiskSlice(L.SectorAccount):
 def __init__(self,*,sid,unit_id,group,cap,old_B,seed_at,cash,claims=(),delay=0,fractional='floor_position_fraction_writeoff'):
  initial=D(cash)+sum((D(x['net_local']) for x in claims),Z);super().__init__(initial_cash=initial,delay_events=delay,fractional_split_policy=fractional);self.available=D(cash);self.sid=sid;self.unit=unit_id;self.group=group;self.cap=cap;self.gate_B=float(old_B);self.last_flat=stamp(seed_at) if isinstance(seed_at,str) else seed_at;self.controller=None;self.pending_B=None;self.ended=False;self.intents={};self.consumed=set();self.credit=None;self.extra=[]
  for e in sorted(claims,key=lambda x:x['ex_at']):self.accrue_dividend(event_id=e['event_id'],sid=sid,currency='CNY',net_local=D(e['net_local']),ex_at=stamp(e['ex_at']),paid_at=stamp(e['paid_at']) if e.get('paid_at') else None,source_id=e['source_id'],entitlement_basis='actual_original_risk_entitlement_carried')
 def sync(self):
  if self.controller:self.controller.sync_execution(shares=self.quantity(self.sid),buy_pending=self.sid in self.buys,exit_order_pending=self.sid in self.exits)
 def expire_day_buys(self,at):
  sid=self.sid;o=self.buys.get(sid);eligible=bool(o and at.date()>=o.earliest_at.date() and not o.filled_shares and self.delay_events and not o.delay_remaining and not self.ended and self.quantity(sid)<self.cap and sid not in self.exits);super().expire_day_buys(at);self.daily_delay_credit.clear();self.credit=(self.unit,self.last_flat,at) if eligible else None
 def submit(self,*,arm,clock,quote,floor,native_I,Q,budget):
  sid=self.sid;event=f'{self.unit}|I={clock.session_date}'
  if self.ended or not native_I or Q is not True or clock.decision_at<=self.last_flat or event in self.consumed:return False,'not_new_legal_IQ'
  self.consumed.add(event)
  if arm=='N':return False,'N_no_restore'
  if arm=='G' and (floor is None or AR.compare(float(floor),self.gate_B)<0):return False,'floor_below_B_or_unknown'
  if sid in self.buys or sid in self.exits or self.quantity(sid)>=self.cap or (self.controller and self.controller.exit_locked and self.quantity(sid)>0):return False,'occupied_or_no_gap'
  if floor is None:return False,'floor_unknown'
  gap=self.cap-self.quantity(sid);budget=min(D(budget),self.available,D(gap)*quote.read_price(clock.decision_at))
  valid=self.credit==(self.unit,self.last_flat,clock.decision_at);self.daily_delay_credit={sid} if valid else set()
  ok,oid=reserve(self,quote=quote,clock=clock,gross_budget_cny=budget,purpose='risk_restore',target_shares_cap=gap,candidate_id=event);self.daily_delay_credit.clear()
  if ok:
   self.intents[oid]=float(floor)
   if valid:self.credit=None;self.extra.append(dict(kind='credit_consumed',at=clock.decision_at,order_id=oid))
  return ok,oid
 def fill_buy(self,sid,window,factor=None):
  o=self.buys.get(sid)
  if o is None:return None
  if factor is None or window.raw_open<=D(str(self.intents[o.order_id]))/D(str(factor)):
   self.extra.append(dict(kind='open_support_or_factor_reject',at=window.at,order_id=o.order_id));self.cancel_buy(sid);return None
  floor=self.intents[o.order_id];before=self.quantity(sid);fill=super().fill_buy(sid,window)
  if fill:
   if before==0:self.controller=RB.RiskBoundary(cycle_id=fill.receipt_id,symbol=sid,source_id=self.group,unit_id=self.group,shares=self.quantity(sid),e0_floor=floor,buy_pending=sid in self.buys)
   self.sync()
  return fill
 def fill_exit(self,sid,window):
  purpose=self.exits[sid].purpose if sid in self.exits else None;fill=super().fill_exit(sid,window);self.sync()
  if fill and self.quantity(sid)==0:
   if purpose=='risk_trim':assert self.pending_B is not None;self.gate_B=self.pending_B;self.last_flat=window.at;self.pending_B=None
   self.credit=None
  return fill
 def split(self,**kw):
  super().split(**kw);self.cap=int(D(self.cap)*D(kw['ratio']));self.sync()
 def close(self,*,clock,quote,ob,sigma,full):
  sid=self.sid
  if full:
   self.ended=True;self.credit=None;self.cancel_buy(sid)
   if self.quantity(sid) and quote is not None:self.request_exit(quote,clock)
  if not self.quantity(sid):return None
  assert self.controller is not None;self.sync();bar=clock.decision_at.date().toordinal();negative=RB.NegativeReceipt(f'{sid}|source={ob["segment"]}|confirmed={clock.session_date}|native_event=-1',sid,self.group,bar) if ob['event']==-1 and ob['source_known'] else None
  z=self.controller.on_close(bar=bar,raw_close=ob['raw_close'],factor=ob['factor'],unit_id=self.group,negative=negative,sigma=sigma,updated_floor=ob['floor'],floor_known=ob['floor_known'],event_feed_known=ob['event_known'],original_exit=full)
  self.extra.append(dict(kind='risk_close',at=clock.decision_at,detail=z))
  if self.controller.exit_locked and self.controller.exit_reason=='risk_boundary' and sid not in self.exits and not full and quote is not None:
   self.pending_B=self.controller.boundary;self.request_exit(quote,clock);self.exits[sid].purpose='risk_trim';self.sync();self.extra.append(dict(kind='independent_risk_request',at=clock.decision_at,B=self.pending_B,shares=self.quantity(sid)))
  return z

class Independent:
 def __init__(self,a):self.cursor=0;self.q=0;self.cash=a.available;self.div=Z;self.fees=Z;self.fee={};self.maximum=Z
 def check(self,a,m,s,at):
  for x in a.audit_log[self.cursor:]:
   k=x['kind']
   if k=='fill':
    f=x['receipt'];sign=1 if f.side=='buy' else -1;self.q+=sign*f.shares;self.cash+=-f.gross_cny-f.fees_cny if sign==1 else f.gross_cny-f.fees_cny;self.fees+=f.fees_cny;old,acc=self.fee.get(x['order_id'],({},{}));sc=m.fees(s,f.at);kwargs=dict(shares=f.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'));fee=sc.incremental(f.side,f.gross_cny,old,acc,1,**kwargs);assert fee==x['fee_components'] and sum(fee.values(),Z)==f.fees_cny;rate=sc.rate_accrual(f.side,f.gross_cny,1,**kwargs);self.fee[x['order_id']]=({k:old.get(k,Z)+v for k,v in fee.items()},{k:acc.get(k,Z)+v for k,v in rate.items()});assert D(f.shares)*D(x['price'])==f.gross_cny
   elif k in ['split','split_fraction_floor_proxy']:self.q=int(D(self.q)*D(x['ratio']))
   elif k=='dividend_accrual':self.div+=D(x['receivable'].net_local)
  self.cursor=len(a.audit_log);assert self.q==a.quantity(s);marks={s:m.latest_mark(s,at)} if self.q else {};bal=a.balance(at,marks);expected=self.cash+self.div+(D(self.q)*marks[s].raw_price if self.q else Z);err=abs(expected-bal['nav']);self.maximum=max(self.maximum,err);assert err<D('1e-8') and a.available>=0;return bal
