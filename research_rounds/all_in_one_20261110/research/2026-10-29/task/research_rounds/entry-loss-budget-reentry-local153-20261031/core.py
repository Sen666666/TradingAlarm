from pathlib import Path
import importlib.util,sys
O=Path(__file__).resolve().parent;W=O.parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
Old=load('budget_reentry_old_core',W/'entry-loss-budget-local153-20261031/core.py');S=Old.S;H=Old.H;L=Old.L;A=Old.A;D=Old.D;Z=Old.Z;ONE=Old.ONE;Budget=Old.Budget;Book=Old.Book;at=Old.at;stamp=Old.stamp;read=Old.read;save=Old.save;export=Old.export;sha=Old.sha;liquidation=Old.liquidation
from datetime import datetime,timedelta
from dataclasses import dataclass
import json,csv,gzip,bisect,time
import pandas as pd
from collections import defaultdict,Counter
@dataclass
class Leg:
 number:int
 K:D
 controller:Budget
 dividend:D=Z
 sales:D=Z
 buy_at:str|None=None
 closed:bool=False
class Wallet(L.SectorAccount):
 def __init__(self,*,symbol,cycle_id,b,K,q,quote,sellable,delay=0,fractional='floor_position_fraction_writeoff'):
  super().__init__(initial_cash=K,delay_events=delay,fractional_split_policy=fractional);self.available=Z;self.positions[symbol]=L.Position(symbol,quote.issuer_id,quote.sector_id,quote.currency,[L.InventoryLot(q,sellable)]);self.sid=symbol;self.cid=cycle_id;self.b=b;self.leg=Leg(1,K,Budget(K,b));self.last_flat=None;self.ended=False;self.seen=set();self.floors={};self.notes=[]
 def reserve_restore(self,*,clock,quote,floor,budget,fresh,Q):
  sid=self.sid;eid=f'{self.cid}|freshI={clock.session_date}'
  if self.ended or self.last_flat is None or clock.decision_at<=self.last_flat or not fresh or Q is not True:return False,'not_new_legal_IQ'
  if self.quantity(sid) or sid in self.buys or sid in self.exits:return False,'local_occupied'
  if eid in self.seen:return False,'signal_already_consumed'
  self.seen.add(eid)
  if floor is None:return False,'floor_unknown'
  ok,why=S.reserve(self,quote=quote,clock=clock,gross_budget_cny=min(budget,self.available),purpose='initial',candidate_id=eid)
  if ok:self.floors[why]=floor
  return ok,why
 def fill_buy(self,s,window,factor):
  if s not in self.buys:return None
  floor=self.floors[self.buys[s].order_id]
  if factor is None or window.raw_open<=floor/factor:self.cancel_buy(s);self.notes.append(dict(kind='original_open_floor_reject',at=str(window.at)));return None
  before=self.quantity(s);f=super().fill_buy(s,window)
  if f:
   spent=f.gross_cny+f.fees_cny
   if before==0:self.leg=Leg(self.leg.number+1,spent,Budget(spent,self.b),buy_at=str(f.at))
   else:self.leg.K+=spent;self.leg.controller.K=self.leg.K
  return f
 def fill_exit(self,s,w):
  f=super().fill_exit(s,w)
  if f and not self.quantity(s):self.last_flat=w.at
  return f
class CycleBook:
 def __init__(self,q):self.q=q;self.flow=Z;self.div=Z;self.cursor=0;self.fees=Z;self.paid={};self.maxres=Z
 def check(self,a,m,s,t):
  for x in a.audit_log[self.cursor:]:
   if x['kind']=='fill':
    f=x['receipt'];sgn=1 if f.side=='buy' else -1;self.q+=sgn*f.shares;self.flow+=-f.gross_cny-f.fees_cny if sgn==1 else f.gross_cny-f.fees_cny;self.fees+=f.fees_cny;paid,acc=self.paid.get(x['order_id'],({},{}));kw=dict(shares=f.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'));sc=m.fees(s,f.at);fees=sc.incremental(f.side,f.gross_cny,paid,acc,1,**kw);assert fees==x['fee_components'] and sum(fees.values(),Z)==f.fees_cny;ra=sc.rate_accrual(f.side,f.gross_cny,1,**kw);self.paid[x['order_id']]=({k:paid.get(k,Z)+v for k,v in fees.items()},{k:acc.get(k,Z)+v for k,v in ra.items()});assert D(f.shares)*x['price']==f.gross_cny
    if sgn==-1:a.leg.sales+=f.gross_cny-f.fees_cny
   elif x['kind']=='dividend_accrual':self.div+=x['receivable'].net_local;a.leg.dividend+=x['receivable'].net_local
   elif x['kind'] in ['split','split_fraction_floor_proxy']:self.q=int(D(self.q)*x['ratio'])
  self.cursor=len(a.audit_log);assert self.q==a.quantity(s);marks={s:m.latest_mark(s,t)} if self.q else {};b=a.balance(t,marks);expected=self.flow+self.div+(D(self.q)*marks[s].raw_price if self.q else Z);res=abs(b['nav']-expected);self.maxres=max(self.maxres,res);assert res<=D('1e-12') and a.available>=0;return b
