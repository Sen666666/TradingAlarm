"""Two frozen policies on the original Runner; no new trading engine."""
import role_adapter as M
from pathlib import Path
from dataclasses import replace
import math,sys,json,numpy as np,pandas as pd
O=M.O;RR=M.RR;D=M.D
W=M.load('partial_prior_feed',O.parent/'full-account-risk-reentry-20261030/wire.py')
class Events(list):
 def __init__(self,a):super().__init__();self.a=a
 def append(self,r):super().append(r);self.a.log('partial_event',r.get('at'),detail=r)
def account_class(Parent,feed):
 base=M.RoleAccount if Parent is M.Parent else type('DrugRoleBase',(M.RoleAccount,Parent),{})
 class Account(base):
  def __init__(self,*args,**kw):super().__init__(*args,roles_enabled=False,**kw);self.policy_tag='A';self.cash_reserve=D(0)
  def reserve_budget(self,**kw):
   if not self.cash_reserve:return super().reserve_budget(**kw)
   at=kw['clock'].decision_at;marks=self.market.marks(at,self.positions);bal=self.balance(at,marks);active=max(D(0),bal['nav']-self.cash_reserve);pending=sum((o.remaining_budget_cny for o in self.buys.values()),D(0));cash=max(D(0),self.available-self.cash_reserve);cap=min(D(kw['gross_budget_cny']),D('.15')*active,max(D(0),D('.90')*active-bal['inventory']-pending),cash);q=kw['quote'];fx=q.fx.read(at);price=q.read_price(at);lo,hi=0,max(0,int(cap*100))
   while lo<hi:
    mid=(lo+hi+1)//2;b=D(mid)/100;fee=sum(q.fees.incremental('buy',b/fx,{}, {},self.cost_multiplier,shares=b/(price*fx),par_value=q.par_value).values(),D(0))*fx
    if b+fee<=cash:lo=mid
    else:hi=mid-1
   kw=dict(kw,gross_budget_cny=D(lo)/100);result=super().reserve_budget(**kw);assert self.available>=self.cash_reserve;self.log('fixed_cash_budget',at,sid=q.security_id,nav=bal['nav'],active_nav=active,tradable_cash=cash,pending=pending,inventory=bal['inventory'],requested=kw['gross_budget_cny'],ok=result[0],result=result[1],protected=self.cash_reserve);return result
  def fill_buy(self,sid,w):
   if self.cash_reserve and sid in self.buys:
    o=self.buys[sid];fx=w.fx.read(w.at);price=D(w.execution_price);step=w.quantity.fill_step;cap=min(o.remaining_shares,int(o.remaining_budget_cny/(price*fx)));lo,hi=0,cap//step
    while lo<hi:
     mid=(lo+hi+1)//2;fee=sum(self._fee(o,w.fees,'buy',mid*step*price,shares=mid*step,par_value=w.par_value).values(),D(0))*fx
     if fee<=o.fee_reserved_cny+max(D(0),self.available-self.cash_reserve):lo=mid
     else:hi=mid-1
    w=replace(w,capacity_shares=min(w.capacity_shares,lo*step))
   result=super().fill_buy(sid,w)
   if self.cash_reserve:assert self.available>=self.cash_reserve
   return result
  def fill_exit(self,sid,w):
   if self.cash_reserve and sid in self.exits:
    o=self.exits[sid];pos=self.positions[sid];available=sum(l.shares for l in pos.lots if l.sellable_at<=w.at);available=min(available,pos.shares if o.remaining_target is None else o.remaining_target);extra=w.quantity.sell_floor(max(0,available-o.submitted_remaining),pos.shares-o.submitted_remaining);n=min(o.submitted_remaining+extra,available,w.capacity_shares)//w.quantity.fill_step*w.quantity.fill_step
    if n:
     fee=sum(self._fee(o,w.fees,'sell',n*w.execution_price,shares=n,par_value=w.par_value).values(),D(0))*w.fx.read(w.at);net=n*w.execution_price*w.fx.read(w.at)-fee
     if net<0 and -net>self.available-self.cash_reserve:raise RuntimeError('Fixed cash contract conflicts with existing sell fee obligation')
   out=super().fill_exit(sid,w)
   if self.cash_reserve:assert self.available>=self.cash_reserve
   return out
 return Account

def setup(sector,root,policies,cutoff=None):
 if sector=='TECH':
  M.P.setup('RS',cutoff);R,E=M.P.R,M.P.E;Parent=E.Account;prep=Path(W.read(RR/'pvr-act-comparison-20261027/input.json')['snapshot']['path']);core=RR/'pvr-act-comparison-20261027/input';mode='I'
 else:
  loc=RR/'innovative-drug-local-recovery-20261028';sys.path.insert(0,str(loc/'code'));P=M.load('partial_original_drug',loc/'code/study.py');P.setup(root,cutoff);R,E=P.R,P.E;Parent=R.Account;prep=RR/'innovative-drug-sfw3-20261028/prepared';core=prep;mode='ACT'
 R.HERE=root
 if cutoff:E.risk_policy.RECOVERY=E.risk_policy.RECOVERY.loc[:cutoff].copy()
 feed=W.Feed(sector,prep,cutoff) if 'B' in policies else None;R.Account=account_class(Parent,feed);oldspecs=R.specs
 def specs(modes,stresses,variant):
  orig=oldspecs(modes,stresses,variant)
  if policies==['A']:return orig
  return tuple(replace(s,account_id=s.account_id.split('__')[0]+'__'+kind+'_'+s.account_id.split('__')[1]) for kind in policies for s in orig)
 R.specs=specs;BaseRunner=R.Runner
 class Runner(BaseRunner):
  def run_tech(self):
   for aid,a in self.accounts.items():
    a.policy_tag='A' if policies==['A'] else aid.split('__')[1].split('_')[0];a.roles_enabled=a.policy_tag=='B';a.cash_reserve=D(500000) if a.policy_tag=='L' else D(0)
    if a.roles_enabled:
     def ctx(sid,at):
      c=feed.context(sid,at);assert c['structure_id'] is not None,(sid,at,'entry structure unknown');return c['structure_id']
     a.role_context=ctx;a.role_events=Events(a)
   return super().run_tech()
 R.Runner=Runner;oldoverride=E.risk_policy.override
 def override(a,stocks,clock,riskmode,Fact):
  stocks=oldoverride(a,stocks,clock,riskmode,Fact);a._partial_stocks=stocks
  if a.roles_enabled:
   a.full_signals={s.security_id for s in stocks if s.trend_up.read(clock) is False}
   for s in stocks:
    sid=s.security_id
    if not a.quantity(sid):continue
    day=pd.Timestamp(clock.decision_at.date());f=feed.frames[sid];e=feed.ev[sid];sg=feed.signals[sid];native=day in f.index;known=day in e.index;obs=bool(day in sg.index and sg.loc[day,'observed_bar'] and not sg.loc[day,'source_invalid'] and not sg.loc[day,'synthetic_event_bar']);row=f.loc[day] if native else None;event=int(e.loc[day,'event']) if known else None;source=feed.context(sid,clock.decision_at)['source_segment'];r=a.roles[sid];unit_ok=f'|source={source}|' in r['group'];px=float(row.raw_close) if native and obs and unit_ok else None;factor=float(row.factor) if px is not None else None;floor=float(row.i_floor) if native and np.isfinite(row.i_floor) and unit_ok else None;quote=a.market.quote(sid,clock.decision_at)
    if quote is None:raise RuntimeError(f'Original quote unavailable for actual held {sid} at {clock.decision_at}')
    sig=feed.sigma(sid,day,source) if event==-1 and r['R'] and unit_ok else None;eid=f'{sid}|source={source}|confirmed={day.date()}|native_event=-1' if event==-1 and unit_ok else None;result=a.close_risk(sid,clock,quote,px,negative_id=eid,sigma=sig,floor=floor,factor=factor,full_exit=sid in a.full_signals,event_known=known and unit_ok,floor_known=floor is not None);a.log('partial_input',clock.decision_at,sid=sid,group=r['group'],native_event=event,raw_i_buy=bool(row.i_buy) if native else False,source_unit_known=unit_ok,price_known=px is not None,event_known=known,diagnostic=result)
  elif a.cash_reserve:
   bal=a.balance(clock.decision_at,a.market.marks(clock.decision_at,a.positions));assert a.available>=a.cash_reserve;a.log('fixed_cash_checkpoint',clock.decision_at,protected=a.cash_reserve,active_nav=max(D(0),bal['nav']-a.cash_reserve),tradable_cash=max(D(0),a.available-a.cash_reserve),**bal)
  return stocks
 E.risk_policy.override=override;basecommit=M.ORIGINAL_COMMIT
 def commit(a,**kw):
  if a.policy_tag=='A':return basecommit(a,**kw)
  clock=kw['clock'];records=[];factory=kw['decision_factory']
  if not a.roles_enabled:
   def capture(**args):d=factory(**args);records.append(d);return d
   args=dict(kw,decision_factory=capture);ack=basecommit(a,**args)
  else:
   _,_,sectors=a.facts.packet(clock.decision_at,a.mode);day=pd.Timestamp(clock.decision_at.date());receipts={}
   for sid in a.roles:
    f=feed.frames[sid]
    if day in f.index and bool(f.loc[day,'i_buy']):receipts[sid]=M.FreshI(f'{sid}|source={int(f.loc[day,"segment_id"])}|I={day.date()}',sid,clock.decision_at)
   ack=M.commit_roles(a,clock=clock,securities=a._partial_stocks,sectors=sectors,quotes=kw['quotes'],marks=kw['marks'],receipts=receipts,previous=kw.get('previous',()),bootstrap=kw.get('bootstrap',False),completed_exits=kw.get('completed_exits',()),ACT_on=a.risk_state['on']);records=list(ack.decisions)
  interesting=set(a.positions)|set(a.buys)|set(a.exits)|{e.security_id for e in kw.get('completed_exits',())};compact=[]
  for d in records:
   keep=interesting|{e.security_id for e in d.eligibility if e.q is True}|{m.security_id for m in d.memories if m.waiting};compact.append(dict(selected=d.selected,rejected=d.rejected,waiting=d.waiting,continue_buys=d.continue_buys,pause_buys=d.pause_buys,cancel_buys=d.cancel_buys,exit_requests=d.exit_requests,eligibility=[e for e in d.eligibility if e.security_id in keep],memories=[m for m in d.memories if m.security_id in keep]))
  a.log('partial_admission',clock.decision_at,policy=a.policy_tag,accepted=ack.accepted,rejected=ack.rejected,occupancy=ack.occupancy,decisions=compact);a.check_roles();return ack
 E.ledger.commit_cutoff=commit
 return R,E,feed,core,prep,mode
