"""D1 bounded-session pressure only; original normal/cost books remain frozen."""
from pathlib import Path
import sys,inspect,textwrap,copy
from bisect import bisect_right
from dataclasses import replace
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'execution-pressure-preflight-20261031'))
import pressure_runner as R
J=R.J;L=R.L;BASE=R.BASE;D=J.D;Z=D(0)

class Account(J.Account):
 def __init__(self,*args,**kw):
  super().__init__(*args,**kw);self.configure_d1(False)
 def configure_d1(self,enabled,calendar=None):
  self.d1_enabled=enabled;self.delay_events=int(enabled);self.d1_orders={};self.d1_exits={};self.d1_audit=[]
  self.d1_calendar=tuple(calendar if calendar is not None else self.market.sessions['A'])
 def next_session(self,at):
  j=bisect_right([x.date() for x in self.d1_calendar],at.date())
  if j>=len(self.d1_calendar):raise ValueError('D1 calendar does not cover next market session')
  return self.d1_calendar[j]
 def reserve_quantity(self,i,q,p,schedule,at):
  oid=super().reserve_quantity(i,q,p,schedule,at)
  if self.d1_enabled:
   o=self.buys[i['sid']];o.delay_remaining=1  # No native/core/old-ADD credit transfer.
   self.d1_orders[oid]=dict(original_shares=q,original_principal=o.remaining_budget_cny,
    first_wait=None,retry_at=None,expiry_day=None,core_used_risk=Z,
    stock_structure=getattr(self.facts,'structure_lookup',{}).get(i['sid'],{}).get(i['clock'].decision_at.date()))
  return oid
 def _consume_event(self,order,w):
  if not self.d1_enabled:return super()._consume_event(order,w)
  buy=hasattr(order,'order_id');identity=order.order_id if buy else order.event_id
  if buy:m=self.d1_orders[identity]
  else:m=self.d1_exits.setdefault(identity,dict(first_wait=None,retry_at=None))
  if m['retry_at'] is not None and w.at<m['retry_at']:return False
  before=order.delay_remaining;result=super()._consume_event(order,w)
  if before and not order.delay_remaining:
   assert m['first_wait'] is None
   m['first_wait']=w.at;m['retry_at']=self.next_session(w.at)
   if buy:
    m['expiry_day']=m['retry_at'].date();self.budget.orders[self.order_bridge[identity]].expiry_bar=J.ordinal(m['expiry_day'])
   self.d1_audit.append(dict(kind='D1_actual_wait',at=w.at,side='buy' if buy else 'sell',order=identity,retry_at=m['retry_at'],expiry_day=m.get('expiry_day'),event=w.event_id))
  return result
 def expire_day_buys(self,at):
  if not self.d1_enabled:return super().expire_day_buys(at)
  self._time(at);self.daily_delay_credit=set();self.add_credits={};unfilled=set()
  for sid,o in tuple(self.buys.items()):
   if at.date()<o.earliest_at.date():continue
   m=self.d1_orders[o.order_id]
   if m['first_wait'] is not None and at.date()<m['expiry_day']:
    self.d1_audit.append(dict(kind='D1_retained_original_order',at=at,sid=sid,order=o.order_id));continue
   if not o.filled_shares and not self.quantity(sid):unfilled.add(sid)
   self.d1_audit.append(dict(kind='D1_buy_deadline_cancel',at=at,sid=sid,order=o.order_id,filled=o.filled_shares,remaining=o.remaining_shares,waited=m['first_wait'] is not None))
   self.cancel_buy(sid)
  return unfilled
 def amend_d1(self,sid,at,raw,rule,schedule):
  """Pre-fill native+mirror amendment, never a new request/token consumption."""
  o=self.buys[sid];m=self.d1_orders[o.order_id];i=self.order_meta[o.order_id];b=self.budget;bo=b.orders[self.order_bridge[o.order_id]]
  assert m['retry_at'] is not None and at>=m['retry_at'] and at.date()<=m['expiry_day']
  self.sync(at);open_nav=self.balance(at,self.market.marks(at,self.positions))['nav']
  decision_nav=self.current_nav  # Original fresh intents retain this decision-NAV base.
  J.C.activate(self);p=raw*(D(1)+J.LR.SLIP);floor=i['floor']/self.facts.factor(sid,at)
  if raw<=floor:return self.reject_d1(sid,at,'open_at_or_below_protection')
  oldcap=bo.qty*bo.limit;oldrisk=bo.qty*max(0.,bo.limit-bo.floor);oldres=bo.qty*(bo.limit+bo.fee_per_share)
  pc,pr,_=b.resources(bo.pool);sc,sr,_=b.resources(sector=bo.sector);_,ar,reserve=b.resources()
  otherfees=sum(x.qty*x.fee_per_share for x in b.orders.values() if x is not bo and x.status in ('open','cancel_pending'))
  state=b.sectors[bo.sector];frac=.02 if bo.pool=='probe' else (.02,.10,.20)[state.level]
  def fee(q):return sum(self._fee(o,schedule,'buy',D(q)*p,shares=q,par_value=i['quote'].par_value).values(),Z)
  def core_risk(q):
   if not o.filled_shares:return J.LR.protection_risk(q,p,floor,schedule,i['quote'].par_value)
   # Continuing fragments retain the one original core leg's full risk budget.
   # Aggregate actual bought cash/fees, plus future incremental buy and one
   # original estimated protection sale; never reset a .25% budget per slice.
   totalq=m['filled_core_qty']+q;exitprice=floor*(D(1)-J.LR.SLIP)
   return max(Z,m['filled_core_gross']+D(q)*p-D(totalq)*exitprice+m['filled_core_buy_fee']+fee(q)+J.LR.fees(totalq,exitprice,schedule,'sell',i['quote'].par_value))
  def failures(q):
   f=fee(q);nav=b.nav-otherfees-float(f);cap=float(D(q)*p);risk=q*max(0.,float(p-floor));out=[]
   if D(q)*p>o.remaining_budget_cny:out.append('original_principal')
   if i['kind']=='core' and core_risk(q)>i['risk_budget']:out.append('original_core_risk')
   totalcash=self.available+o.remaining_budget_cny+o.fee_reserved_cny
   if cap+float(f)>min(float(totalcash-open_nav*D('.1')),b.cash-(reserve-oldres))+1e-8:out.append('cash_or_original_reserve')
   if pc-oldcap+cap>(.10 if bo.pool=='probe' else .60)*nav+1e-8:out.append('pool_capital')
   if bo.pool=='probe' and pr-oldrisk+risk>.005*nav+1e-8:out.append('probe_risk')
   if sc-oldcap+cap>frac*nav+1e-8:out.append('sector_capital')
   if sr-oldrisk+risk>.01*nav+1e-8:out.append('sector_risk')
   if self.d1_account_cap and ar-oldrisk+risk>.03*nav+1e-8:out.append('account_risk')
   if float(self.quantity(sid)*raw)+cap>.10*float(open_nav)+1e-8:out.append('stock_capital')
   return out
  cap=min(o.remaining_shares,int(o.remaining_budget_cny/p))
  if o.filled_shares:
   step=rule.fill_step;lo,hi=0,cap//step
   while lo<hi:
    mid=(lo+hi+1)//2
    if not failures(mid*step):lo=mid
    else:hi=mid-1
   q=lo*step
  else:q=J.LR.maximum_quantity(rule,cap,lambda q:not failures(q))
  if not q:return self.reject_d1(sid,at,','.join(failures(rule.fill_step if o.filled_shares else rule.buy_minimum)) or 'minimum_unit_not_funded')
  old=copy.deepcopy(o.__dict__);oldbo=copy.deepcopy(bo.__dict__);cash=self.available
  audit=dict(kind='D1_same_order_amend',at=at,sid=sid,order=o.order_id,receipt=i.get('CP1_id'),old_shares=o.remaining_shares,new_shares=q,old_principal=o.remaining_budget_cny,new_principal=D(q)*p,old_fee=o.fee_reserved_cny,new_fee=fee(q),price=p,old_order_recheck_open_nav=open_nav,fresh_intent_decision_nav=decision_nav)
  try:
   newfee=fee(q);self.available+=o.remaining_budget_cny+o.fee_reserved_cny-D(q)*p-newfee
   o.remaining_shares=q;o.remaining_budget_cny=D(q)*p;o.fee_reserved_cny=newfee;o.submitted_remaining=min(o.submitted_remaining,q)
   bo.qty=q;bo.limit=float(p);bo.floor=float(floor);bo.fee_per_share=float(newfee/D(q))
   assert q<=old['remaining_shares'] and o.remaining_budget_cny<=old['remaining_budget_cny'] and self.available>=0
   self.sync(at);assert self.current_nav==decision_nav;m['amended_at']=at;self.d1_audit.append(audit)
  except BaseException:
   o.__dict__.clear();o.__dict__.update(old);bo.__dict__.clear();bo.__dict__.update(oldbo);self.available=cash;self.sync(at)
   raise
  return True
 def reject_d1(self,sid,at,reason):
  self.d1_audit.append(dict(kind='D1_retry_cancel',at=at,sid=sid,reason=reason));self.cancel_buy(sid);self.sync(at);return False
 def fill_buy(self,sid,w):
  if self.d1_enabled and sid in self.buys:
   o=self.buys[sid];m=self.d1_orders[o.order_id]
   if m['retry_at'] is not None:
    if w.at<m['retry_at']:return None
    assert m.get('amended_at')==w.at,'D1 retained order must amend before any native fill'
  o=self.buys.get(sid);meta=self.order_meta[o.order_id] if o else None
  result=super().fill_buy(sid,w)
  if result and self.d1_enabled:
   m=self.d1_orders[o.order_id]
   if meta['kind']=='core':
    m['filled_core_qty']=m.get('filled_core_qty',0)+result.shares;m['filled_core_gross']=m.get('filled_core_gross',Z)+result.gross_cny;m['filled_core_buy_fee']=m.get('filled_core_buy_fee',Z)+result.fees_cny
    floor=meta['floor']/self.facts.factor(sid,w.at);exitprice=floor*(D(1)-J.LR.SLIP)
    m['core_used_risk']=max(Z,m['filled_core_gross']-D(m['filled_core_qty'])*exitprice+m['filled_core_buy_fee']+J.LR.fees(m['filled_core_qty'],exitprice,w.fees,'sell',meta['quote'].par_value))
  return result

PLANNING=textwrap.dedent(inspect.getsource(J.Runner.planning))
needle='a.sync(at);self.industry(a,at)';assert PLANNING.count(needle)==1
PLANNING=PLANNING.replace(needle,needle+';self.revalidate_carried_buys(a,at,continuing)')
OPENING=textwrap.dedent(inspect.getsource(J.Runner.opening))
needle='a.settle_due(at);a.sync(at);funded=[];done=set()';assert OPENING.count(needle)==1
OPENING=OPENING.replace(needle,'a.settle_due(at);a.sync(at);carried=self.prepare_carried(a,at);funded=[];done=set()')
needle=' # Execution proxies are consulted only after all H1-ranked funding decisions.';assert OPENING.count(needle)==1
OPENING=OPENING.replace(needle,needle+"\n for sid in carried:\n  win=self.market.window(sid,at,'buy',1)\n  if win:a.fill_buy(sid,win)")
env=dict(J.__dict__);exec(PLANNING+'\n'+OPENING,env)

class Pair(L.PreparedRunner):
 reference='B3'
 def __init__(self,*args,enabled=True,**kw):
  original=J.Account;J.Account=Account
  try:super().__init__(*args,policies=('B',),**kw)
  finally:J.Account=original
  self.d1_enabled=enabled
  for a in self.accounts.values():
   a.configure_d1(enabled);a.d1_account_cap=self.reference=='B3'
   if self.reference=='B_diag':BASE.enable(a)
 planning=env['planning'];opening=env['opening'];route=J.Runner.route
 def revalidate_carried_buys(self,a,at,continuing):
  if not a.d1_enabled:return
  for sid,o in tuple(a.buys.items()):
   m=a.d1_orders[o.order_id];bo=a.budget.orders[a.order_bridge[o.order_id]];s=a.budget.sectors.get(bo.sector);row=self.facts.row(sid,at);i=a.order_meta[o.order_id]
   structure=getattr(self.facts,'structure_lookup',{}).get(sid,{}).get(at.date());why=None
   if not a.risk_state['on']:why='ACT_paused'
   elif sid in a.exits:why='exit_pending'
   elif not s or not s.active or s.attempt!=bo.attempt or s.episode!=bo.episode:why='industry_authorization_ended'
   elif row is None or sid not in continuing or continuing[sid].q is not True:why='continuing_Q_false_or_unknown'
   elif not bool(row.i_target):why='stock_I_ended'
   elif m['stock_structure'] is None or structure is None:why='stock_structure_unknown'
   elif structure!=m['stock_structure']:why='stock_structure_changed'
   elif D(str(row.close))<=i['floor']:why='original_protection_failed'
   if why:a.reject_d1(sid,at,why)
 def prepare_carried(self,a,at):
  if not a.d1_enabled:return []
  result=[]
  for sid,o in sorted(tuple(a.buys.items()),key=lambda z:(a.order_meta[z[1].order_id]['rank'],z[0])):
   m=a.d1_orders[o.order_id]
   if m['retry_at'] is None or at<m['retry_at']:continue
   assert at.date()<=m['expiry_day'],'D1 expired order survived its cutoff'
   raw=self.market.raw[sid];day=J.pd.Timestamp(at.date())
   if day not in raw.index or not J.np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:continue
   if a.amend_d1(sid,at,D(str(raw.loc[day].open)),self.market.quantity(sid,at),self.market.fees(sid,at)):result.append(sid)
  return result
 def checkpoint(self,out,last_event):
  import shutil
  super().checkpoint(out,last_event);out=Path(out);day=str(last_event.date())
  if day in ('2025-09-30','2025-12-31','2026-03-31'):
   for suffix in ('pkl','json'):shutil.copyfile(out/('checkpoint.'+suffix),out/('checkpoint-'+day+'.'+suffix))
 def restore(self,path):
  expected=(self.reference,self.d1_enabled);at=super().restore(path)
  assert (self.reference,self.d1_enabled)==expected,'D1 checkpoint execution configuration changed'
  assert all(a.d1_enabled==expected[1] and a.delay_events==int(expected[1]) and a.d1_account_cap==(expected[0]=='B3') for a in self.accounts.values())
  return at
 def dump_joint(self,path):
  super().dump_joint(path)
  for key,a in self.accounts.items():L.save(Path(path)/(key+'-D1_AUDIT.json'),dict(events=a.d1_audit,orders=a.d1_orders,exits=a.d1_exits))
class B3D1(Pair):reference='B3';route=J.Runner.route
class DiagD1(Pair):reference='B_diag';route=BASE.Runner.route
