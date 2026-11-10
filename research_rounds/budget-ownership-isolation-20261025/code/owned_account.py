"""A settled-cash ownership adapter over the frozen source financial methods."""
from budget_common import *
import inspect,textwrap
sys.path.append(str(OLD/'code'))
import sector_account as source
D=Decimal

def derive(method,replacements):
 text=textwrap.dedent(inspect.getsource(method))
 for a,b in replacements:
  assert text.count(a)==1,(method.__name__,a,text.count(a));text=text.replace(a,b)
 scope=dict(method.__globals__);exec(compile(text,'<ownership-spend-limit:'+method.__name__+'>','exec'),scope)
 return scope[method.__name__]

_reserve=derive(source.SectorAccount.reserve_budget,[('min(dec(gross_budget_cny), self.available)','min(dec(gross_budget_cny), self.available, self.spend_limit(quote.sector_id))'),('if budget+fee <= self.available:','if budget+fee <= min(self.available, self.spend_limit(quote.sector_id)):')])
_buy=derive(source.SectorAccount.fill_buy,[('order.fee_reserved_cny+self.available:','order.fee_reserved_cny+min(self.available, self.spend_limit(order.quote.sector_id)):')])
_sell=derive(source.SectorAccount.fill_exit,[('if net < 0 and self.available < -net:','if net < 0 and min(self.available, self.spend_limit(order.quote.sector_id)) < -net:')])

class OwnedAccount(source.SectorAccount):
 def __init__(self,*,owners,owner_of_sid,isolate,**kwargs):
  super().__init__(**kwargs);self.owners=tuple(owners);self.owner_of_sid=dict(owner_of_sid);self.isolate=isolate
  share=(self.initial_cash/D(len(owners))).quantize(D('.01'));self.owner_cash={s:share for s in owners};self.owner_cash[owners[-1]]+=self.initial_cash-sum(self.owner_cash.values());self.settlement_owner={};self.owner_journal=[];self.budget_constraints=[];self._tracking_depth=0
 def spend_limit(self,owner):return max(D(0),self.owner_cash[owner]) if self.isolate else self.available
 def check(self):
  assert abs(sum(self.owner_cash.values(),D(0))-self.available)<D("1e-18"),(self.owner_cash,self.available)
  if self.isolate:assert all(v>=-D("1e-18") for v in self.owner_cash.values()),self.owner_cash
 def track(self,owner,kind,call):
  a=self.available;s=sum(self.owner_cash.values(),D(0));oldkeys=set(self.settlements);self._tracking_depth+=1
  try:answer=call()
  finally:self._tracking_depth-=1
  residual=(self.available-a)-(sum(self.owner_cash.values(),D(0))-s)
  self.owner_cash[owner]+=residual
  for k in set(self.settlements)-oldkeys:self.settlement_owner[k]=owner
  if residual:self.owner_journal.append(dict(at=self.as_of,owner=owner,kind=kind,available_delta=residual,owner_after=self.owner_cash[owner],global_after=self.available))
  if not self._tracking_depth:self.check()
  return answer
 def reserve_budget(self,**kw):
  owner=kw['quote'].sector_id;before=len(self.audit_log);a=self.spend_limit(owner);requested=source.dec(kw['gross_budget_cny'])
  result=self.track(owner,'reserve',lambda:_reserve(self,**kw))
  if self.isolate and a<min(requested,self.available+sum((r['gross_budget_cny']+r['fee_reserved_cny'] for r in self.audit_log[before:] if r['kind']=='reserve'),D(0))):
   self.budget_constraints.append(dict(at=kw['clock'].decision_at,sid=kw['quote'].security_id,owner=owner,owner_cash_before=a,requested_gross=requested,accepted=result[0],result=result[1]))
  return result
 def cancel_buy(self,sid):return self.track(self.owner_of_sid[sid],'cancel',lambda:source.SectorAccount.cancel_buy(self,sid))
 def fill_buy(self,sid,window):return self.track(self.owner_of_sid[sid],'buy_fill',lambda:_buy(self,sid,window))
 def fill_exit(self,sid,window):return self.track(self.owner_of_sid[sid],'sell_fill',lambda:_sell(self,sid,window))
 def settle_due(self,at):
  credits={k:(self.settlement_owner[k],x.cny_amount) for k,x in self.settlements.items() if x.due_at<=at and not x.debit};result=super().settle_due(at)
  for k,(owner,value) in credits.items():
   self.owner_cash[owner]+=value;self.owner_journal.append(dict(at=at,owner=owner,kind='settled_sale',available_delta=value,owner_after=self.owner_cash[owner],global_after=self.available))
  for k in result:self.settlement_owner.pop(k,None)
  self.check();return result
 def pay_dividend(self,event_id,**kw):
  owner=self.owner_of_sid[self.dividends[event_id].security_id];return self.track(owner,'dividend_paid',lambda:source.SectorAccount.pay_dividend(self,event_id,**kw))
 def charge_expense(self,**kw):
  owners={self.owner_of_sid[s] for s in self.owner_of_sid if s in kw['expense_id'] or s in kw['source_id']}
  if len(owners)!=1:raise ValueError('Expense requires a unique security owner')
  owner=owners.pop()
  if self.isolate and source.dec(kw['cny_amount'])>self.owner_cash[owner]:raise ValueError('Mandatory expense exceeds owner cash')
  return self.track(owner,'expense',lambda:source.SectorAccount.charge_expense(self,**kw))
