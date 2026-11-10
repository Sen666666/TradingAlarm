from pathlib import Path
from datetime import datetime,time as tm
from decimal import Decimal as D
from dataclasses import dataclass
import importlib.util,sys,json,csv,hashlib,bisect,gzip,time
import pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;Z=D(0);ONE=D(1)
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
S=load('lossbudget_market',W/'partial-recovery-local-rgn-20261031/shared.py');H=S.H;L=S.L;A=S.A
stamp=S.stamp;at=S.at;read=S.read;save=S.save;export=S.export;sha=S.sha
@dataclass
class Budget:
 K:D
 b:D
 locked:bool=False
 reason:str|None=None
 requested_at:str|None=None
 def close(self,*,V,known,at,original=False):
  if self.locked:return False
  if original:self.locked=True;self.reason='original';self.requested_at=at;return True
  if not known:return None
  if V<=(ONE-self.b)*self.K:self.locked=True;self.reason='loss_budget';self.requested_at=at;return True
  return False

def liquidation(m,s,q,mark,t):
 gross=D(q)*mark;slippage=gross*D('.0005');fee=sum(m.fees(s,t).incremental('sell',gross-slippage,{}, {},1,shares=q,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value')).values(),Z) if q else Z
 return fee,slippage

class Book:
 def __init__(self,q):self.q=q;self.flow=Z;self.div=Z;self.cursor=0;self.fees=Z;self.paid={};self.maxres=Z
 def check(self,a,m,s,t):
  for x in a.audit_log[self.cursor:]:
   if x['kind']=='fill':
    f=x['receipt'];assert f.side=='sell';self.q-=f.shares;self.flow+=f.gross_cny-f.fees_cny;self.fees+=f.fees_cny;paid,acc=self.paid.get(x['order_id'],({},{}));kw=dict(shares=f.shares,par_value=m.rules.get('security_metadata',{}).get(s,{}).get('par_value'));schedule=m.fees(s,t);fee=schedule.incremental('sell',f.gross_cny,paid,acc,1,**kw);assert fee==x['fee_components'] and sum(fee.values(),Z)==f.fees_cny;rate=schedule.rate_accrual('sell',f.gross_cny,1,**kw);self.paid[x['order_id']]=({k:paid.get(k,Z)+v for k,v in fee.items()},{k:acc.get(k,Z)+v for k,v in rate.items()});assert D(f.shares)*x['price']==f.gross_cny
   elif x['kind']=='dividend_accrual':self.div+=x['receivable'].net_local
   elif x['kind'] in ['split','split_fraction_floor_proxy']:self.q=int(D(self.q)*x['ratio'])
  self.cursor=len(a.audit_log);assert self.q==a.quantity(s);marks={s:m.latest_mark(s,t)} if self.q else {};b=a.balance(t,marks);expected=self.flow+self.div+(D(self.q)*marks[s].raw_price if self.q else Z);res=abs(b['nav']-expected);self.maxres=max(self.maxres,res);assert res<=D('1e-12') and a.available>=0;return b
