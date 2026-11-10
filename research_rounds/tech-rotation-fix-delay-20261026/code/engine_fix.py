from study_common import *
from dataclasses import replace
from decimal import Decimal as D
from bisect import bisect_right
from datetime import timedelta,time,datetime
import collections
ZERO=D(0);INITIAL=D(1000000)

class Account(base_engine.Account):
 def reserve_budget(self,**kw):
  ok,oid=super().reserve_budget(**kw)
  if ok and self.cfg.get('buy_delay')==0:self.buys[kw['quote'].security_id].delay_remaining=0
  return ok,oid
 def request_exit(self,quote,clock):
  r=super().request_exit(quote,clock)
  if self.cfg.get('sell_delay')==0 and quote.security_id in self.exits:self.exits[quote.security_id].delay_remaining=0
  return r
 def expire_day_buys(self,at):
  keep={}
  if self.cfg.get('latch'):
   for sid,o in list(self.buys.items()):
    j=bisect_right(self.market.sessions['A'],o.created_at);deadline=self.market.sessions['A'][j+1].date()
    if at.date()<deadline:keep[sid]=self.buys.pop(sid)
  out=super().expire_day_buys(at);self.buys.update(keep);return out
 def reserve_pair(self,z,ctx,at):
  new=z['candidate'];q=self.market.quote(new,at)
  if q is None:return False,'unknown_execution_quote'
  # Frozen quantity is in old share units; only actual known splits convert it.
  cap=ctx['share_cap']
  for e in self.market.actions.get(new,[]):
   if ctx['signal_at'].date().isoformat()<e['effective_date']<=at.date().isoformat():cap=int(D(cap)*D(e['split_ratio']))
  clock=admission.Clock(at,at+timedelta(seconds=1),at.date())
  ok,oid=ledger.SectorAccount.reserve_budget(self,quote=q,clock=clock,gross_budget_cny=D(z['budget']),target_shares_cap=cap,candidate_id=z['id'])
  if ok:
   self.intents[oid]=dict(sid=new,decision_at=ctx['signal_at'],funded_at=at,floor_signal=ctx['support'],risk_budget=ctx['nav']*D('.01'),nav=ctx['nav'],budget=self.buys[new].budget_cny)
   self.log('entry_contract',at,order_id=oid,mode=self.mode,**self.intents[oid]);self.counts['buy_orders']+=1
  return ok,oid

class Runner(base_engine.Runner):
 def start_swap(self,a,at,clock,stocks,sectors):
  before=a.swap;super().start_swap(a,at,clock,stocks,sectors)
  if a.cfg.get('sd') and before is None and a.swap:
   z=a.swap;q=self.market.quote(z['candidate'],at);a.swap_context=dict(signal_at=at,support=self.facts.floor(z['candidate'],at,'I'),nav=a.current_nav,share_cap=q.quantity.buy_floor(int(D(z['budget'])/q.raw_price)))
   a.log('same_day_rotation_contract',at,rotation_id=z['id'],**a.swap_context)
 def advance_swap(self,a,at,clock):
  if not a.cfg.get('sd'):return super().advance_swap(a,at,clock)
  z=a.swap
  if not z:return
  old,new=z['victim'],z['candidate']
  if z['phase']=='sell':
   if at.date().isoformat()>=z['sell_deadline'] and a.quantity(old):
    o=a.exits.get(old)
    if o and o.purpose=='rotation_exit':del a.exits[old];a.log('rotation_sell_cancelled',at,sid=old,event_id=o.event_id)
    self.end_swap(a,at,'sell_incomplete')
  elif z['phase']=='buy':
   if new not in a.buys:self.end_swap(a,at,'bought' if a.quantity(new) else 'not_bought')
   elif not self.intent_valid(a,new,at):a.cancel_buy(new);self.end_swap(a,at,'candidate_invalid_while_waiting')
 def intent_valid(self,a,sid,at):
  clock,stocks,sectors=self.facts.packet(at,'I');s=next(x for x in stocks if x.security_id==sid)
  s=replace(s,buy_allowed=self.market.market_buyable(at)[sid]);return admission.eligibility(s,{x.sector_id:x for x in sectors},clock,'S0').q is True
 def after_sales(self,a,at):
  if not a.cfg.get('sd') or not a.swap:return
  z=a.swap;old,new=z['victim'],z['candidate']
  if z['phase']!='sell' or a.quantity(old):return
  z['sold_at']=next(e.completed_at for e in reversed(a.completed) if e.security_id==old);a.counts['rotation_sold']+=1
  ok,oid=a.reserve_pair(z,a.swap_context,at)
  if not ok:self.end_swap(a,at,'reservation_failed');return
  j=bisect_right(self.market.sessions['A'],at);z.update(phase='buy',buy_order=oid,buy_deadline=self.market.sessions['A'][j].date().isoformat())
  a.log('rotation_buy_reserved',at,rotation=z.copy(),order_id=oid,budget=a.buys[new].budget_cny)
 def normal_buy_symbols(self,a):
  paired=a.swap['candidate'] if a.cfg.get('sd') and a.swap and a.swap['phase']=='buy' else None
  return [s for s in a.buys if s!=paired]
 def after_buys(self,a,at):
  if not a.cfg.get('sd') or not a.swap or a.swap['phase']!='buy':return
  z=a.swap;sid=z['candidate']
  if sid not in a.buys:return
  w=self.market.window(sid,at,'buy',a.cost_multiplier)
  if not w:return
  when=at+timedelta(seconds=1);price=w.execution_price
  if a.cfg.get('paired_buy_bps') is not None:price=w.raw_open*(1+D(str(a.cfg['paired_buy_bps']))/10000)
  w=replace(w,event_id=w.event_id+':after_sale',at=when,execution_price=price,cash_due_at=max(when,w.cash_due_at),execution_basis='daily_open_proxy_after_sale_sequence_1s_not_observed_tick')
  fill=a.fill_buy(sid,w);a.settle_due(when)
 def latch_stocks(self,a,at,stocks):
  if not a.cfg.get('latch'):return stocks
  buyable=self.market.market_buyable(at)
  return tuple(replace(s,buy_allowed=buyable[s.security_id]) if s.security_id in a.buys else s for s in stocks)
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
     a.settle_due(at);self.after_sales(a,at);priority=self.priority.get(aid,())
     for sid in sorted(self.normal_buy_symbols(a),key=lambda s:(not bool(a.buys[s].filled_shares),priority.index(s) if s in priority else len(priority),s)):
      w=self.market.window(sid,at,'buy',a.cost_multiplier)
      if w:a.fill_buy(sid,w)
     a.settle_due(at);self.after_buys(a,at)
   if at not in cutoffs:continue
   clock=self.facts.packet(at,'E0')[0]
   for spec in self.specs:
    aid=spec.account_id;a=self.accounts[aid];mode=a.mode;marks=self.market.marks(at,a.positions);a.current_nav=a.balance(at,marks)['nav']
    if mode=='BH':
     if aid not in self.started:
      for sid in self.benchmark:
       quote=self.market.quote(sid,at)
       if quote:a.reserve_budget(quote=quote,clock=clock,gross_budget_cny=INITIAL*D('.15'),candidate_id='fixed_start_BH')
      self.started.add(aid);self.priority[aid]=tuple(self.benchmark);a.bh_deadline=self.market.sessions['A'][bisect_right(self.market.sessions['A'],at)+1].date()
     elif at.date()>=a.bh_deadline:a.expire_day_buys(at)
    else:
     expired=a.expire_day_buys(at);self.memory[aid]=tuple(replace(m,waiting=True,created_at=at,origin='expired_unfilled_recompetition') if m.security_id in expired else m for m in self.memory[aid])
     _,stocks,sectors=self.facts.packet(at,mode);a.normal_exits={s.security_id for s in stocks if s.trend_up.read(clock) is False}
     if mode=='AMT15':self.advance_swap(a,at,clock)
     if a.swap and a.swap['phase']=='buy':
      new=a.swap['candidate'];stocks=tuple(replace(s,buy_allowed=self.market.market_buyable(at)[new]) if s.security_id==new else s for s in stocks)
     stocks=self.latch_stocks(a,at,stocks)
     def factory(**kw):return admission.decide(clock=clock,variant=spec.variant,securities=stocks,sectors=sectors,**kw)
     cursor=self.exit_cursor.get(aid,0);quotes=LazyQuotes(self.market,at);marks=self.market.marks(at,a.positions)
     ack=ledger.commit_cutoff(a,decision_factory=factory,clock=clock,quotes=quotes,marks=marks,previous=self.memory[aid],bootstrap=aid not in self.started,completed_exits=tuple(a.completed[cursor:]))
     self.exit_cursor[aid]=len(a.completed);self.memory[aid]=ack.memories;self.started.add(aid);self.priority[aid]=tuple(dict.fromkeys(tuple(ack.decisions[-1].continue_buys)+ack.accepted));a.daily_delay_credit.clear()
     if mode=='AMT15':self.start_swap(a,at,clock,*self.facts.packet(at,'I')[1:])
     d=ack.decisions[-1];self.sink.emit('decisions',dict(account=aid,at=at,accepted=ack.accepted,rejected=ack.rejected,selected=d.selected,exits=d.exit_requests,eligible=[e.security_id for e in d.eligibility if e.q is True],occupancy=ack.occupancy,swap=a.swap,counts=dict(a.counts)))
    marks=self.market.marks(at,a.positions);bal=a.balance(at,marks);row=dict(account=aid,at=at,**bal,peak_cash_committed=INITIAL-a.minimum_available,positions={s:p.shares for s,p in a.positions.items()},mark_observed_at={s:m.known_at for s,m in marks.items()},mark_source_id={s:m.source_id for s,m in marks.items()},pending_buys=tuple(a.buys),pending_sells=tuple(a.exits),counts=dict(a.counts));self.last_daily[aid]=row;self.daily_rows+=1;self.sink.emit('daily',row)
   if at.date().day<=3:print(dict(stage='replay',date=str(at.date()),accounts=len(self.accounts),daily_rows=self.daily_rows),flush=True)
  return dict(status='complete',accounts=list(self.accounts),daily_rows=self.daily_rows,technical=self.synthetic,final_nav={a:str(d['nav']) for a,d in self.last_daily.items()})

LazyQuotes=base_engine.LazyQuotes
