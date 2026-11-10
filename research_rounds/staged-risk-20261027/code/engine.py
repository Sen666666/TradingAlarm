"""Finite capital replay using the original Decimal share/cash/fee ledger."""
from common import *
import risk_policy
RISK_MODE="CONTROL"
from dataclasses import replace,asdict
from decimal import Decimal as D
from bisect import bisect_right
from datetime import time,timedelta
import types,collections
import current_fixed_pool as pool

FastMarket=import_path('tech_fast_market',TEMP/'code/fast_market.py').FastMarket
INITIAL=D('1000000');ZERO=D(0)
MODES=['E0','I','IX','RB1','H50','BH','AMT15']

def policy(mode):return 'IX' if mode=='IX' else 'E0' if mode=='E0' else 'I'

class Facts:
 def __init__(self,b,market,cutoff=None):
  self.b,self.market=b,market;self.f={};self.cache={};self.day=None
  for sid in b.series:
   f=pd.read_parquet(PREP/'facts'/f'{sid}.parquet')
   self.f[sid]=f.loc[:cutoff].copy() if cutoff else f
 def row(self,sid,at):
  f=self.f[sid];day=pd.Timestamp(at.date());i=f.index.searchsorted(day,side='right')-1
  return None if i<0 else f.iloc[i]
 def factor(self,sid,at):return D(str(self.row(sid,at)['factor']))
 def floor(self,sid,at,mode):
  r=self.row(sid,at);v=np.nan if r is None else r[policy(mode).lower()+'_floor']
  return None if not np.isfinite(v) else D(str(v))
 def packet(self,at,mode):
  p=policy(mode)
  if self.day!=at:self.day=at;self.cache={}
  if p in self.cache:return self.cache[p]
  clock=admission.Clock(at,self.market.sessions['A'][bisect_right(self.market.sessions['A'],at)],at.date())
  inputs=self.b.at_decision(clock,market_buyable=self.market.market_buyable(at));stocks=[]
  for l,h in zip(inputs.lines,inputs.historical):
   assert l.security_id==h.security_id;sid=l.security_id;r=self.row(sid,at)
   if p!='E0':
    up=h.trend_up.read(clock)
    if up is not None:h=replace(h,trend_up=replace(h.trend_up,value=bool(r[p.lower()+'_target'])))
   s=pool.build_security(l,h,inputs.evidence)
   if p!='E0':
    allowed=s.buy_allowed.read(clock,for_execution=True);f=self.f[sid];today=pd.Timestamp(at.date());event=today in f.index and bool(f.loc[today,p.lower()+'_buy'])
    s=replace(s,buy_allowed=admission.Fact(None if allowed is None else bool(allowed and event),at,at,source_id='original_'+p+'_daily_event'))
   stocks.append(s)
  result=(clock,tuple(stocks),inputs.sectors);self.cache[p]=result;return result

class Account(ledger.SectorAccount):
 def __init__(self,*args,**kw):
  super().__init__(*args,**kw);self.mode='I';self.facts=None;self.protect=True;self.current_nav=INITIAL;self.intents={};self.rearm=set();self.normal_exits=set();self.swap=None;self.swap_seq=0;self.counts=collections.Counter()
 @property
 def available(self):return self._available
 @available.setter
 def available(self,value):
  self._available=value
  if not hasattr(self,'minimum_available') or value<self.minimum_available:self.minimum_available=value
 def log(self,kind,at,**kw):self.audit_log.append(dict(kind=kind,at=at,**kw))
 def loss(self,quote,q,price,floor,order=None):
  qty=q+(order.filled_shares if order else 0);gross=q*price+(order.local_notional if order else ZERO)
  buyfees=sum(quote.fees.incremental('buy',q*price,order.fees_local if order else {},order.fee_accrued_local if order else {},self.cost_multiplier,shares=q,par_value=quote.par_value).values(),ZERO)
  if order:buyfees+=sum(order.fees_local.values(),ZERO)
  slip=D('0.0005')*self.cost_multiplier;sellprice=floor*(1-slip)
  sellfees=sum(quote.fees.incremental('sell',qty*sellprice,{}, {},self.cost_multiplier,shares=qty,par_value=quote.par_value).values(),ZERO)
  return max(ZERO,gross+buyfees-qty*sellprice+sellfees)
 def risk_cap(self,quote,cap,price,floor,budget,order=None):
  step=quote.quantity.fill_step;lo,hi=0,max(0,int(cap)//step)
  while lo<hi:
   m=(lo+hi+1)//2
   if self.loss(quote,m*step,price,floor,order)<=budget:lo=m
   else:hi=m-1
  return lo*step
 def reserve_budget(self,**kw):
  at=kw['clock'].decision_at;sid=kw['quote'].security_id;quote=kw['quote'];budget=D(kw['gross_budget_cny']);floor_signal=self.facts.floor(sid,at,self.mode) if self.facts else None
  if self.mode=='H50' or RISK_MODE=='HALF':budget*=D('.5')
  risk=self.current_nav*D('.01');floor=floor_signal/self.facts.factor(sid,at) if floor_signal is not None else None
  if self.mode=='RB1':
   if floor is None or quote.raw_price<=floor:self.log('risk_reject',at,sid=sid,reason='support_not_below_entry');return False,'risk_support_invalid'
   cap=int(budget/quote.raw_price);q=self.risk_cap(quote,cap,quote.raw_price,floor,risk);q=quote.quantity.buy_floor(q)
   if not q:self.log('risk_reject',at,sid=sid,reason='minimum_quantity');return False,'risk_minimum_quantity'
   budget=min(budget,q*quote.raw_price);kw['target_shares_cap']=min(kw.get('target_shares_cap',q),q)
  kw['gross_budget_cny']=budget;ok,reason=super().reserve_budget(**kw)
  if ok:
   self.intents[reason]=dict(sid=sid,decision_at=at,floor_signal=floor_signal,risk_budget=risk,nav=self.current_nav,budget=budget)
   self.log('entry_contract',at,order_id=reason,mode=self.mode,**self.intents[reason]);self.counts['buy_orders']+=1
  else:self.counts['reject_'+reason]+=1
  return ok,reason
 def fill_buy(self,sid,w):
  o=self.buys.get(sid)
  if o is None:return None
  z=self.intents[o.order_id];floor_signal=z['floor_signal'];floor=floor_signal/self.facts.factor(sid,w.at) if floor_signal is not None else None
  if self.protect and (floor is None or w.raw_open<=floor):
   self.log('open_support_reject',w.at,sid=sid,order_id=o.order_id,raw_open=w.raw_open,floor=floor)
   if not self.quantity(sid):self.rearm.add(sid)
   self.counts['open_support_reject']+=1;self.cancel_buy(sid);return None
  if self.mode=='RB1':
   q=self.risk_cap(replace(o.quote,fees=w.fees,quantity=w.quantity),o.remaining_shares,w.execution_price,floor,z['risk_budget'],o)
   if not o.submitted_remaining:q=w.quantity.buy_floor(q)
   if not q:
    self.log('risk_open_reject',w.at,sid=sid,order_id=o.order_id);self.cancel_buy(sid);self.rearm.add(sid);return None
   if q<o.remaining_shares:
    self.log('risk_open_cap',w.at,sid=sid,order_id=o.order_id,previous=o.remaining_shares,shares=q,floor=floor,risk_budget=z['risk_budget']);o.remaining_shares=q;o.submitted_remaining=min(o.submitted_remaining,q)
   self.log('risk_fill_bound',w.at,sid=sid,order_id=o.order_id,shares=q,estimated_loss=self.loss(replace(o.quote,fees=w.fees),q,w.execution_price,floor,o),risk_budget=z['risk_budget'],floor=floor)
  fill=super().fill_buy(sid,w)
  if fill:self.counts['buy_fills']+=1
  return fill
 def request_exit(self,quote,clock):
  old=self.exits.get(quote.security_id)
  if old and old.purpose=='risk_reduction' and quote.security_id in self.normal_exits:
   old.remaining_target=None;old.purpose='structure_exit';old.earliest_at=max(old.earliest_at,clock.earliest_execution_at)
   self.log('risk_reduction_upgrade',clock.decision_at,sid=quote.security_id,event_id=old.event_id)
  sid=quote.security_id
  if sid in self.normal_exits and sid in self.exits and self.exits[sid].purpose=='rotation_exit':
   self.exits[sid].purpose='structure_exit';self.log('rotation_exit_upgraded',clock.decision_at,sid=sid)
  return super().request_exit(quote,clock)
 def expire_day_buys(self,at):
  keep={}
  if self.swap and self.swap.get('phase')=='buy':
   sid=self.swap['candidate'];o=self.buys.get(sid)
   if o and at.date().isoformat()<self.swap['buy_deadline']:keep[sid]=self.buys.pop(sid)
  expired=super().expire_day_buys(at);self.buys.update(keep);expired|=self.rearm;self.rearm.clear();return expired

class Sink:
 def __init__(self,p):
  p.mkdir(parents=True,exist_ok=False);self.streams={k:gzip.open(p/f'{k}.jsonl.gz','wt',compresslevel=1) for k in ['daily','decisions']}
 def emit(self,name,row):self.streams[name].write(json.dumps(native.encoded(row),ensure_ascii=False,allow_nan=False)+'\n')
 def close(self):
  for x in self.streams.values():x.close()

def projected(a,sid,securities,sectors,clock,marks,remove=None):
 stock={s.security_id:s for s in securities};ss={s.sector_id:s for s in sectors};e=admission.eligibility(stock[sid],ss,clock,'S0')
 occ=[x for x in a.occupancy(clock.decision_at) if x.security_id!=remove]
 if sid in {x.security_id for x in occ} or len(occ)>=6:return None
 counts=collections.Counter(x.sector_id for x in occ)
 if counts[e.sector_id]>=2 or (e.sector_id not in counts and len(counts)>=3):return None
 bal=a.balance(clock.decision_at,marks);mv=marks[remove].cny_price(clock.decision_at)*a.quantity(remove) if remove else ZERO
 pending=sum((o.remaining_budget_cny for s,o in a.buys.items() if s!=remove),ZERO);cash=a.available
 if remove:
  q=a.market.quote(remove,clock.decision_at);sale=mv*(1-D('.0005')*a.cost_multiplier);cost=sum(q.fees.incremental('sell',sale,{}, {},a.cost_multiplier,shares=a.quantity(remove),par_value=q.par_value).values(),ZERO);cash+=max(ZERO,sale-cost)
 budget=max(ZERO,min(D('.15')*bal['nav'],D('.90')*bal['nav']-(bal['inventory']-mv)-pending,cash))
 q=a.market.quote(sid,clock.decision_at)
 if q is None or not q.quantity.buy_floor(int(budget/q.raw_price)):return None
 fee=sum(q.fees.incremental('buy',budget,{}, {},a.cost_multiplier,shares=budget/q.raw_price,par_value=q.par_value).values(),ZERO)
 if budget+fee>cash:
  budget=max(ZERO,cash-fee)
  if not q.quantity.buy_floor(int(budget/q.raw_price)):return None
 return budget

class Runner(native.HistoryRunner):
 def replacement_ok(self,a,sid,at):
  clock,stocks,sectors=self.facts.packet(at,'I');r=self.facts.row(sid,at)
  if r is None or not bool(r.i_target) or not bool(r.g_ready) or r.g_grade<2:return False
  s=next(x for x in stocks if x.security_id==sid);s=replace(s,buy_allowed=self.market.market_buyable(at)[sid]);return admission.eligibility(s,{x.sector_id:x for x in sectors},clock,'S0').q is True
 def end_swap(self,a,at,reason):
  z=a.swap;a.log('rotation_finished',at,rotation=z,reason=reason,held_candidate=a.quantity(z['candidate']),held_victim=a.quantity(z['victim']));a.counts['rotation_'+reason]+=1;a.swap=None
 def advance_swap(self,a,at,clock):
  z=a.swap
  if not z:return
  old,new=z['victim'],z['candidate'];day=at.date().isoformat()
  if z['phase']=='sell':
   if not a.quantity(old):
    z['sold_at']=next(e.completed_at for e in reversed(a.completed) if e.security_id==old);a.counts['rotation_sold']+=1
    if not self.replacement_ok(a,new,at):self.end_swap(a,at,'candidate_invalid_after_sale');return
    _,stocks,sectors=self.facts.packet(at,'I');marks=self.market.marks(at,a.positions);budget=projected(a,new,stocks,sectors,clock,marks)
    if budget is None:self.end_swap(a,at,'unfundable_after_sale');return
    quote=self.market.quote(new,at);budget=min(budget,D(z['budget']));ok,oid=a.reserve_budget(quote=quote,clock=clock,gross_budget_cny=budget,candidate_id=z['id'])
    if not ok:self.end_swap(a,at,'reservation_failed');return
    z.update(phase='buy',buy_order=oid,buy_deadline=self.market.sessions['A'][bisect_right(self.market.sessions['A'],at)+1].date().isoformat());a.log('rotation_buy_reserved',at,rotation=z.copy(),order_id=oid,budget=budget)
   elif day>=z['sell_deadline']:
    order=a.exits.get(old)
    if order and order.purpose=='rotation_exit':del a.exits[old];a.log('rotation_sell_cancelled',at,sid=old,event_id=order.event_id)
    self.end_swap(a,at,'sell_incomplete')
  elif z['phase']=='buy':
   if new not in a.buys:self.end_swap(a,at,'bought' if a.quantity(new) else 'not_bought')
   elif not self.replacement_ok(a,new,at):a.cancel_buy(new);self.end_swap(a,at,'candidate_invalid_while_waiting')
 def start_swap(self,a,at,clock,stocks,sectors):
  if a.swap:return
  sd={s.security_id:s for s in stocks};ss={s.sector_id:s for s in sectors};eligible={s:admission.eligibility(x,ss,clock,'S0') for s,x in sd.items()};ids=[s for s,e in eligible.items() if e.q is True and not a.quantity(s) and s not in a.buys and s not in a.exits];fall=[];priority=admission._priority(ids,sd,ss,eligible,clock,'S0',fall,'rotation');marks=self.market.marks(at,a.positions)
  a.counts['rotation_candidate_checks']+=len(ids)
  for new in priority:
   if projected(a,new,stocks,sectors,clock,marks) is not None:a.counts['rotation_normal_buy_possible']+=1;continue
   amt=self.amount(new,at)
   if amt is None:continue
   feasible=[]
   for old,pos in a.positions.items():
    if old in a.exits or old in a.buys or any(l.sellable_at>clock.earliest_execution_at for l in pos.lots):continue
    oldamt=self.amount(old,at)
    if oldamt is None:continue
    budget=projected(a,new,stocks,sectors,clock,marks,remove=old)
    if budget is not None:feasible.append((oldamt,sd[old].rank.read(clock) if sd[old].rank and sd[old].rank.read(clock) is not None else -1,old,budget))
   if not feasible:a.counts['rotation_no_feasible_victim']+=1;continue
   oldamt,rank,old,budget=min(feasible)
   if amt<D('1.5')*oldamt:a.counts['rotation_below_1_5']+=1;continue
   a.swap_seq+=1;deadline=self.market.sessions['A'][bisect_right(self.market.sessions['A'],at)+1].date().isoformat();z=dict(id=f'ROT:{a.swap_seq}:{at.date()}',phase='sell',candidate=new,victim=old,signal_at=at,budget=budget,candidate_amount=amt,victim_amount=oldamt,ratio=amt/oldamt,sell_deadline=deadline)
   a.swap=z;a.request_exit(self.market.quote(old,at),clock);a.exits[old].purpose='rotation_exit';a.log('rotation_started',at,rotation=z.copy());a.counts['rotation_started']+=1;return
 def amount(self,sid,at):
  f=self.market.raw[sid];day=pd.Timestamp(at.date())
  if day not in f.index:return None
  r=f.loc[day]
  if not bool(r.observed_bar) or not bool(r.valid_price) or not np.isfinite(r.amount) or r.amount<=0:return None
  assert r.amount_unit=='CNY';return D(str(r.amount))
 def run_tech(self):
  cutoffs={x for x in self.market.cutoffs if self.start<=x<=self.end};opens={x for x in self.market.sessions['A'] if self.start<=x<=self.end};acts={datetime.combine(datetime.fromisoformat(d).date(),time.min,native.TZ) for d in self.actions_by_date};events=sorted(cutoffs|opens|{x for x in acts if self.start<=x<=self.end})
  for at in events:
   for a in self.accounts.values():a.settle_due(at)
   self._actions(at)
   for a in self.accounts.values():self._payments(a,at)
   if at in opens:
    for aid,a in self.accounts.items():
     for sid in sorted(a.exits):
      w=self.market.window(sid,at,'sell',a.cost_multiplier)
      if w:a.fill_exit(sid,w)
     a.settle_due(at);priority=self.priority.get(aid,())
     for sid in sorted(a.buys,key=lambda s:(not bool(a.buys[s].filled_shares),priority.index(s) if s in priority else len(priority),s)):
      w=self.market.window(sid,at,'buy',a.cost_multiplier)
      if w:a.fill_buy(sid,w)
     a.settle_due(at)
   if at not in cutoffs:continue
   clock=self.facts.packet(at,'E0')[0]
   for spec in self.specs:
    aid=spec.account_id;a=self.accounts[aid];mode=a.mode;marks=self.market.marks(at,a.positions);a.current_nav=a.balance(at,marks)['nav']
    risk_policy.step(a,at,RISK_MODE)
    if mode=='BH':
     if aid not in self.started:
      for sid in self.benchmark:
       quote=self.market.quote(sid,at)
       if quote:a.reserve_budget(quote=quote,clock=clock,gross_budget_cny=INITIAL*D('.15'),candidate_id='fixed_start_BH')
      self.started.add(aid);self.priority[aid]=tuple(self.benchmark);a.bh_deadline=self.market.sessions['A'][bisect_right(self.market.sessions['A'],at)+1].date()
     elif at.date()>=a.bh_deadline:a.expire_day_buys(at)
    else:
     expired=a.expire_day_buys(at);self.memory[aid]=tuple(replace(m,waiting=True,created_at=at,origin='expired_unfilled_recompetition') if m.security_id in expired else m for m in self.memory[aid])
     _,stocks,sectors=self.facts.packet(at,mode);stocks=risk_policy.override(a,stocks,clock,RISK_MODE,admission.Fact);a.normal_exits={s.security_id for s in stocks if s.trend_up.read(clock) is False}
     if mode=='AMT15':self.advance_swap(a,at,clock)
     if a.swap and a.swap['phase']=='buy':
      new=a.swap['candidate'];stocks=tuple(replace(s,buy_allowed=self.market.market_buyable(at)[new]) if s.security_id==new else s for s in stocks)
     def factory(**kw):return admission.decide(clock=clock,variant=spec.variant,securities=stocks,sectors=sectors,**kw)
     cursor=self.exit_cursor.get(aid,0);quotes=LazyQuotes(self.market,at);marks=self.market.marks(at,a.positions)
     ack=ledger.commit_cutoff(a,decision_factory=factory,clock=clock,quotes=quotes,marks=marks,previous=self.memory[aid],bootstrap=aid not in self.started,completed_exits=tuple(a.completed[cursor:]))
     self.exit_cursor[aid]=len(a.completed);self.memory[aid]=ack.memories;self.started.add(aid);self.priority[aid]=tuple(dict.fromkeys(tuple(ack.decisions[-1].continue_buys)+ack.accepted));a.daily_delay_credit.clear()
     if mode=='AMT15':self.start_swap(a,at,clock,*self.facts.packet(at,'I')[1:])
     risk_policy.reduce_after_commit(a,clock,RISK_MODE)
     d=ack.decisions[-1];self.sink.emit('decisions',dict(account=aid,at=at,accepted=ack.accepted,rejected=ack.rejected,selected=d.selected,exits=d.exit_requests,eligible=[e.security_id for e in d.eligibility if e.q is True],occupancy=ack.occupancy,swap=a.swap,counts=dict(a.counts)))
    marks=self.market.marks(at,a.positions);bal=a.balance(at,marks);row=dict(account=aid,at=at,**bal,peak_cash_committed=INITIAL-a.minimum_available,positions={s:p.shares for s,p in a.positions.items()},mark_observed_at={s:m.known_at for s,m in marks.items()},mark_source_id={s:m.source_id for s,m in marks.items()},pending_buys=tuple(a.buys),pending_sells=tuple(a.exits),counts=dict(a.counts));self.last_daily[aid]=row;self.daily_rows+=1;self.sink.emit('daily',row)
   if at.date().day<=3:print(dict(stage='replay',date=str(at.date()),accounts=len(self.accounts),daily_rows=self.daily_rows),flush=True)
  return dict(status='complete',accounts=list(self.accounts),daily_rows=self.daily_rows,technical=self.synthetic,final_nav={a:str(d['nav']) for a,d in self.last_daily.items()})

class LazyQuotes(dict):
 def __init__(self,m,at):self.m,self.at=m,at
 def get(self,s,default=None):
  if not dict.__contains__(self,s):
   q=self.m.quote(s,self.at)
   if q is not None:dict.__setitem__(self,s,q)
  return dict.get(self,s,default)
 def __contains__(self,s):return self.get(s) is not None
 def __getitem__(self,s):
  q=self.get(s)
  if q is None:raise KeyError(s)
  return q
