from pathlib import Path
import sys,importlib.util
from dataclasses import replace
O=Path(__file__).resolve().parent;W=O.parent
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);sys.modules[n]=m;s.loader.exec_module(m);return m
previous=load('rb1_history_frozen_current_adapter',W/'rb1-act-finite-20261031/adapter.py');w=previous.w
def setup(sector,root,roles,ported=True,cutoff=None):
 R,E,core,prep,mode=w.setup(sector,root,False,cutoff);Parent=R.Account
 if ported:R.Account=previous.port.account_class(Parent)
 spec0=R.specs
 def specs(modes,stresses,variant):
  return tuple(replace(s,account_id=s.account_id.split('__')[0]+'__'+role+'_'+s.account_id.split('__')[1]) for role in roles for s in spec0(modes,stresses,variant))
 R.specs=specs;Base=R.Runner;F=R.Facts
 class Facts(F):
  def __init__(self,*a,**kw):super().__init__(*a,**kw);self.qualification_rows=[];self.qualification_seen=set()
  def packet(self,at,mode):
   value=super().packet(at,mode)
   if E.policy(mode)=='I' and at not in self.qualification_seen:
    self.qualification_seen.add(at);clock,stocks,sectors=value;ss={s.sector_id:s for s in sectors};es=[E.admission.eligibility(s,ss,clock,'S0') for s in stocks];self.qualification_rows.append(dict(at=at,market_I_Q_true=[e.security_id for e in es if e.q is True],market_I_Q_unknown=[e.security_id for e in es if e.q is None],observed_pool=len(stocks),account_ACT_cash_capacity_not_applied=True))
   return value
 R.Facts=Facts
 class Runner(Base):
  def run_tech(self):
   if ported:
    for aid,a in self.accounts.items():a.rb1_sizing=aid.split('__')[1].startswith('R_')
   return super().run_tech()
 R.Runner=Runner
 return R,E,core,prep,mode
