from common import *
import run as sizing
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace as NS
from run_first10 import first10_specs
from test_sector_account import quote,window,fx,RULE,FREE
D=sizing.D;PAD=sizing.PAD

class Market:
 def __init__(self):
  self.days=[pd.Timestamp('2020-01-02')+pd.Timedelta(days=i) for i in range(13)];self.opens=[datetime.combine(d.date(),sizing.time(9,30),native.TZ) for d in self.days];self.cutoffs=tuple(datetime.combine(d.date(),sizing.time(15,10),native.TZ) for d in self.days[:12]);self.sessions={'A':tuple(self.opens)};self.actions={};self.protocol={};self.notices=[];self.prices=[10,11,12,12,9,13,12,13,14,10,9,9]
 def quote(self,sid,at):
  i=self.days.index(pd.Timestamp(at.date()));return replace(quote(sid=sid,price=self.prices[i]),known_at=at,fx=fx(at=at))
 def window(self,sid,at,side,cost_multiplier):
  i=self.opens.index(at);price=self.prices[max(0,i-1)];return window(sid=sid,price=price,at=at,capacity=10**9,fees=FREE,rule=RULE,eid=f'{i}:{side}',sellable_at=self.opens[min(i+1,len(self.opens)-1)],cash_due_at=at)
 def rate(self,currency,at):return fx(at=at)
 def currency_fx(self,at):return {'CNY':fx(at=at)}
 def marks(self,at,positions):
  i=self.days.index(pd.Timestamp(at.date()));return {sid:ledger.Mark(D(self.prices[i]),at,fx(at=at),'synthetic') for sid in positions}

class Sink:
 def __init__(self):self.records={};self.n=0
 def daily(self,aid,a,at,market):
  self.records[aid,at.date().isoformat()]=dict(book=a.book.copy(),q={s:p.shares for s,p in a.positions.items()},counts=dict(a.counts));self.n+=1

def main():
 m=Market();sink=Sink();src=next(s for s in first10_specs() if s.account_id=='S0_base');ss=tuple(replace(src,account_id=mode+'__S0_base',initial_capital_cny=PAD) for mode in ['F100','F10','F30','A','B','C','D']);native.first10_specs=lambda:ss;native.SectorAccount=sizing.Account
 r=sizing.Runner(NS(),m,start=m.cutoffs[0],end=m.cutoffs[-1],sink=sink,synthetic=True)
 for aid,a in r.accounts.items():a.mode=aid.split('__')[0]
 grades=np.array([4,4,4,4,2,4,-2,4,4,-3,-3,-3],np.int8)[:,None];eligible=np.array([True]*10+[False]*2)[:,None];facts=dict(dates=np.array([d.date().isoformat() for d in m.days[:12]]),symbols=np.array(['A']),eligible=eligible,up=np.array([1]*10+[0]*2)[:,None],grade=grades,fresh=np.array([1,0,1,0,1,1,0,0,1,0,0,0],bool)[:,None],acute=np.zeros((12,1),bool),signal_price=np.array(m.prices,float)[:,None])
 r.run_fast(facts)
 def rec(mode,i):return sink.records[mode+'__S0_base',m.days[i].date().isoformat()]
 checks=0
 for mode,budget in [('F100',1000000),('F10',100000),('F30',300000),('A',100000),('B',100000),('C',100000),('D',100000)]:assert rec(mode,1)['book']['A']==D(budget);checks+=1
 for mode in ['A','B','C','D']:assert rec(mode,2)['book']['A']==D(100000);checks+=1 # Staying at 100 cannot automatically add.
 assert D(290000)<rec('A',3)['book']['A']<=D(300000);checks+=1
 assert D(990000)<rec('B',3)['book']['A']<=D(1000000);checks+=1
 assert rec('A',5)['book']['A']==rec('A',4)['book']['A'];checks+=1 # Fresh but underwater cannot add.
 assert rec('A',7)['book']['A']>D(590000);checks+=1
 for mode in ['C','D']:assert D(100000)<=rec(mode,7)['book']['A']<D(103000);checks+=1
 for mode in ['F100','F10','F30','A','B','C','D']:assert rec(mode,11)['q']=={};checks+=1
 for a in r.accounts.values():assert max(a.book.values(),default=D(0))<=D(1000000);checks+=1
 # Raw-price float gain does not cause any forced cost rebalance.
 assert rec('F100',7)['book']['A']==D(1000000);checks+=1
 # A minimum order larger than the small first allocation is really rejected.
 a=sizing.Account(initial_cash=PAD);q=replace(quote(price=2000),known_at=m.cutoffs[0],fx=fx(at=m.cutoffs[0]));clock=admission.Clock(m.cutoffs[0],m.opens[1],m.cutoffs[0].date());a.buy('A',q,clock,D(100000),2000,0,'initial');assert not a.buys and a.available==PAD;checks+=1
 write(HERE/'technical/synthetic.json',dict(passed=True,assertions=checks,paths=7,days=12,checks=['small_initial_even_grade100','persistent_high_not_auto_add','new_fact_ladder_vs_grade_jump','no_average_down','cost_target_reduction_keeps_core','E0_full_exit_priority','minimum_quantity_reject','natural_price_gain_not_rebalanced']))
 print(dict(passed=True,assertions=checks),flush=True)
if __name__=='__main__':main()
