from study import *
from types import SimpleNamespace as N
w={'j':0,'day':'2025-01-01','segment':'a','floor':90.}
base=dict(day='2025-01-02',j=1,L=10,close=100.,old_floor=91.,event=1,pivot=95.,pivot_date='2025-01-01',valid=True,segment='a',on=True)
checks=0
def test(updates,reason,floor=None):
 global checks
 z,why=advance(w,**(base|updates));assert why==reason,(why,reason)
 if floor is not None:assert z['floor']==floor
 checks+=1
for u,r,f in [({},None,95),({'pivot_date':'2024-12-31'},None,91),({'event':0},None,91),({'close':90},'waiting_floor_breach',None),({'old_floor':101},'updated_floor_breach',None),({'j':10},'expired',None),({'j':9},None,95),({'L':3,'j':3},'expired',None),({'L':3,'j':2},None,95),({'on':False},'risk_pause',None),({'valid':False},'structure_or_source',None),({'segment':'b'},'structure_or_source',None),({'pivot':85,'old_floor':89},None,90)]:test(u,r,f)
assert w['floor']==90
# Reservation uses inherited floor, restores shared Facts, and locks origin into intent.
a=object.__new__(Account);a.mode='SW10F';a.watch={'X':w};a.intents={};a.audit_log=[]
f=N(floor=lambda *args:D(80),row=lambda *args:N(i_buy=False));a.facts=f
orig=E.Account.reserve_budget
try:
 def reserve(self,**kw):
  floor=self.facts.floor('X',None,self.mode);assert floor==D(90);self.intents['o']={'floor_signal':floor};return True,'o'
 E.Account.reserve_budget=reserve
 assert a.reserve_budget(quote=N(security_id='X'),clock=N(decision_at=pd.Timestamp('2025-01-02')))==(True,'o')
 assert a.facts is f and a.intents['o']['watch_origin']==w['day'];checks+=1
finally:E.Account.reserve_budget=orig
orig=E.Account.fill_buy
try:
 a.buys={'X':N(order_id='o')};a.fast_floor={}
 E.Account.fill_buy=lambda *args:True
 assert a.fill_buy('X',N(at=pd.Timestamp('2025-01-03')))
 assert a.fast_floor['X']==90 and a.fast_anchor['X']=='2025-01-01';checks+=1
finally:E.Account.fill_buy=orig
save(O/'tests.json',{'passed':True,'meaningful_boundary_checks':checks})
