"""LR-1: only core sizing and cash apportionment change; BP-1 remains immutable."""
from pathlib import Path
import sys,json,hashlib,collections,math
from decimal import Decimal as D,ROUND_FLOOR
from datetime import datetime
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parents[1]
BASE=ROOT/'research_rounds/probe-pyramid-pilot-20261029'
sys.path.insert(0,str(BASE/'code'))
import pilot as BP
C,E,R,L,A,N=BP.C,BP.E,BP.R,BP.L,BP.A,BP.N
SNAP,CP,PV=BP.SNAP,BP.CP,BP.PV
ZERO,ONE,INITIAL=BP.ZERO,BP.ONE,BP.INITIAL
save,sha=BP.save,BP.sha
RISK=D('.0025');SLIP=D('.0005')
CASES=['601869.SH','300502.SZ','300308.SZ','688498.SH','688048.SH','688256.SH','002987.SZ','002439.SZ','688041.SH']

def fees(qty,price,schedule,side,par=None):
 return sum(schedule.incremental(side,D(qty)*price,{}, {},ONE,shares=qty,par_value=par).values(),ZERO) if qty else ZERO
def protection_risk(qty,price,floor,schedule,par=None):
 return max(ZERO,D(qty)*(price-floor*(ONE-SLIP))+fees(qty,price,schedule,'buy',par)+fees(qty,floor*(ONE-SLIP),schedule,'sell',par))
def maximum_quantity(rule,cap,allowed):
 """Largest legal original order, never fabricate a sub-minimum order."""
 if cap<rule.buy_minimum or not allowed(rule.buy_minimum):return 0
 lo,hi=0,(cap-rule.buy_minimum)//rule.buy_step
 while lo<hi:
  mid=(lo+hi+1)//2
  if allowed(rule.buy_minimum+mid*rule.buy_step):lo=mid
  else:hi=mid-1
 return rule.buy_minimum+lo*rule.buy_step
def waterfill(caps,weights,cash):
 out={s:ZERO for s in caps};active=set(caps);left=min(max(ZERO,cash),sum(caps.values(),ZERO))
 while active and left>0:
  total=sum((weights[s] for s in active),ZERO);hit=[s for s in active if left*weights[s]/total>=caps[s]-out[s]]
  if not hit:
   for s in active:out[s]+=left*weights[s]/total
   break
  for s in sorted(hit):v=caps[s]-out[s];out[s]+=v;left-=v;active.remove(s)
 return out

def resize_core(i,nav,factor):
 q=i['quote'];floor=i['floor']/factor;ref=q.raw_price*(ONE+SLIP);risk=nav*RISK;grosscap=nav*D('.1')
 i.update(risk_budget=risk,frozen_floor_raw=floor,signal_price=q.raw_price,reference_price=ref)
 if floor<=0 or floor>=q.raw_price:i.update(budget=ZERO,cap=0,size_reject='invalid_protection');return
 cap=maximum_quantity(q.quantity,int(grosscap/ref),lambda n:protection_risk(n,ref,floor,q.fees,q.par_value)<=risk)
 if not cap:i.update(budget=ZERO,cap=0,size_reject='minimum_unit_exceeds_risk_or_nominal_cap');return
 # Maximum gross reservation at the frozen share cap, without an arbitrary gap buffer.
 stop=D(cap)*floor*(ONE-SLIP);sellfee=fees(cap,floor*(ONE-SLIP),q.fees,'sell',q.par_value);lo=int(D(cap)*ref*100);hi=int(grosscap*100)
 while lo<hi:
  mid=(lo+hi+1)//2;b=D(mid)/100
  if b+fees(cap,b/D(cap),q.fees,'buy',q.par_value)-stop+sellfee<=risk:lo=mid
  else:hi=mid-1
 i.update(budget=D(lo)/100,cap=cap,size_reject=None)

def preview(i,op,factor,rule,schedule):
 p=op*(ONE+SLIP);floor=i['floor']/factor;cap=i['cap'];budget=i['budget'];par=i['quote'].par_value
 if op<=floor:return None,'open_at_or_below_protection'
 def allowed(q):return D(q)*p<=budget and (i['kind']!='core' or protection_risk(q,p,floor,schedule,par)<=i['risk_budget'])
 maxq=maximum_quantity(rule,min(cap,int(budget/p)),allowed)
 if not maxq:return None,'open_minimum_exceeds_frozen_contract'
 cache={}
 def cost(q):
  if q not in cache:cache[q]=D(q)*p+fees(q,p,schedule,'buy',par)
  return cache[q]
 return dict(sid=i['sid'],i=i,price=p,floor=floor,rule=rule,schedule=schedule,maxq=maxq,minq=rule.buy_minimum,cost=cost,weight=D(str(i['weight'])),qty=0),None

def whole_orders(items,cash):
 """Minimum orders first, then proportional top-ups; no future execution filter."""
 if not items or cash<=0:return {x['sid']:0 for x in items},[]
 by={x['sid']:x for x in items};caps={s:x['cost'](x['maxq']) for s,x in by.items()};weights={s:x['weight'] for s,x in by.items()};ideal=waterfill(caps,weights,cash)
 order=sorted(by,key=lambda s:(-ideal[s]/by[s]['cost'](by[s]['minq']),s));left=cash;selected=[];audit=[]
 for s in order:
  x=by[s];m=x['cost'](x['minq']);take=m<=left
  if take:x['qty']=x['minq'];left-=m;selected.append(s)
  audit.append(dict(sid=s,minimum_cash=m,ideal_cash=ideal[s],minimum_share_ratio=ideal[s]/m,minimum_selected=take))
 if selected:
  extra=waterfill({s:by[s]['cost'](by[s]['maxq'])-by[s]['cost'](by[s]['qty']) for s in selected},{s:weights[s] for s in selected},left);targets={s:by[s]['cost'](by[s]['qty'])+extra[s] for s in selected}
  for s in selected:
   x=by[s];old=x['cost'](x['qty']);x['qty']=maximum_quantity(x['rule'],x['maxq'],lambda q:x['cost'](q)<=targets[s]);left-=x['cost'](x['qty'])-old
  while True:
   choices=[]
   for s in selected:
    x=by[s];n=x['qty']+x['rule'].buy_step
    if n>x['maxq']:continue
    delta=x['cost'](n)-x['cost'](x['qty'])
    if delta<=left:choices.append((-(targets[s]-x['cost'](x['qty']))/delta,s,n,delta))
   if not choices:break
   _,s,n,delta=min(choices);by[s]['qty']=n;left-=delta
 assert sum((x['cost'](x['qty']) if x['qty'] else ZERO for x in items),ZERO)<=cash
 return {s:x['qty'] for s,x in by.items()},audit

class Account(BP.Account):
 def reserve_quantity(self,i,q,p,schedule,at):
  """Lock known-open cash under a past frozen contract; execution stays in old ledger."""
  sid=i['sid'];clock=i['clock'];quote=i['quote'];gross=D(q)*p;fee=fees(q,p,schedule,'buy',quote.par_value);quote.read_price(clock.decision_at);self._time(at)
  assert clock.decision_at<at and clock.earliest_execution_at==at
  assert 0<q<=i['cap'] and gross<=i['budget'] and gross+fee<=self.available
  assert sid not in self.buys and sid not in self.exits
  oid=self._id('buy',sid);order=L.BuyOrder(oid,quote,clock.decision_at,clock.earliest_execution_at,i['budget'],gross,fee,q,q,0,'annual_rebalance');order.candidate_id='LR1:'+i['reason'];self.buys[sid]=order;self.available-=gross+fee;self.order_meta[oid]=i
  self.audit_log.append(dict(kind='reserve',at=at,decision_at=clock.decision_at,sid=sid,order_id=oid,gross_budget_cny=gross,fee_reserved_cny=fee,target_shares=q,purpose='annual_rebalance',candidate_id=order.candidate_id,quote_source=quote.source_id,fee_schedule=schedule.schedule_id,frozen_max_shares=i['cap'],frozen_max_gross=i['budget'],known_open_funding=True))
  self.log('lot_risk_funded',at,sid=sid,order_id=oid,layer_kind=i['kind'],signal_at=clock.decision_at,shares=q,gross=gross,fees=fee,risk_budget=i.get('risk_budget'),floor=i['floor'])
  return oid

class Pilot(BP.Pilot):
 def __init__(self,cut=None,only=None):
  super().__init__(cut,['P0','P1']);wanted=only or ['P0','P1','L0','L1'];self.accounts={k:(self.accounts[k] if k in ('P0','P1') else Account('P0' if k=='L0' else 'P1',self.market,self.facts)) for k in wanted}
 def planning(self,at):
  start=len(self.daily);super().planning(at)
  for row,(aid,a) in zip(self.daily[start:],self.accounts.items()):
   row['account']=aid
   if not aid.startswith('L'):continue
   allitems=a.pending
   for i in allitems:
    if i['kind']=='core':
     resize_core(i,a.current_nav,self.facts.factor(i['sid'],at))
     if i.get('size_reject'):a.counts['size_'+i['size_reject']]+=1
   a.pending=[i for i in allitems if not i.get('size_reject')];a.decisions[-1]['intents']=[{k:v for k,v in i.items() if k not in ('quote','clock')} for i in allitems];row.update(pending_intents=len(a.pending),counts=dict(a.counts))
 def opening(self,a,at):
  if type(a) is BP.Account:return super().opening(a,at)
  for sid in sorted(a.exits):
   w=self.market.window(sid,at,'sell',ONE)
   if w:a.fill_exit(sid,w)
  a.settle_due(at);cash=max(ZERO,a.available-a.current_nav*D('.1'));items=[i for i in a.pending if i['clock'].earliest_execution_at==at];previews=[];day=pd.Timestamp(at.date())
  for i in items:
   sid=i['sid'];raw=self.market.raw[sid]
   if day not in raw.index or not np.isfinite(raw.loc[day].open) or raw.loc[day].open<=0:a.counts['allocation_missing_open']+=1;continue
   op=D(str(raw.loc[day].open));factor=self.facts.factor(sid,at);z,why=preview(i,op,factor,self.market.quantity(sid,at),self.market.fees(sid,at))
   if why:a.counts['allocation_'+why]+=1;a.log('lot_risk_open_reject',at,sid=sid,reason=why,signal_at=i['clock'].decision_at);continue
   previews.append(z)
  chosen={};details=[]
  for group in (0,1):
   part=[x for x in previews if x['i']['group']==group];qty,audit=whole_orders(part,cash);details+=audit
   for x in part:
    if qty[x['sid']]:chosen[x['sid']]=x;cash-=x['cost'](qty[x['sid']])
   assert cash>=0
  for z in details:a.log('lot_allocation',at,**z)
  # Complete allocation precedes all buys. Future H/L/volume postchecks never recycle failed-order money.
  for x in sorted(previews,key=lambda x:(x['i']['group'],x['sid'])):
   sid=x['sid'];q=x['qty'];i=x['i']
   if not q:a.counts['whole_order_unfunded']+=1;continue
   if i['kind']=='core':assert protection_risk(q,x['price'],x['floor'],x['schedule'],i['quote'].par_value)<=i['risk_budget']
   a.reserve_quantity(i,q,x['price'],x['schedule'],at);w=self.market.window(sid,at,'buy',ONE)
   if w:
    assert w.execution_price==x['price'];a.fill_buy(sid,w)
   else:a.counts['no_open_window']+=1
  a.settle_due(at);a.minimum_available=min(a.minimum_available,a.available);a.check()

def freeze():
 files=list((O/'code').glob('*.py'))+[O/'RULES.txt',O/'RAW_REVIEW.txt',BASE/'code/pilot.py',BASE/'code/analyze.py',BASE/'completion-sha256.json',BASE/'VERIFICATION.json']
 inherited=json.loads((BASE/'FREEZE.json').read_text())['sha256'];allowed=str((BASE/'code/analyze.py').relative_to(ROOT));assert all(sha(ROOT/k)==v for k,v in inherited.items() if k!=allowed)
 files+= [ROOT/k for k in inherited if k!=allowed]
 files +=[BASE/'charts'/f'raw-{n}.png' for n in [1,2,3]]
 save(O/'FREEZE.json',dict(recorded_at=datetime.now().astimezone().isoformat(),before_new_results=True,paths=['P0','P1','L0','L1'],new_economic_paths=2,risk_per_probe=str(RISK),parameters_after_results_changed=0,sha256={str(p.relative_to(ROOT)):sha(p) for p in files}))
 print('FROZEN',len(files))
if __name__=='__main__':
 if sys.argv[1]=='freeze':freeze()
 elif sys.argv[1]=='economic':
  z=json.loads((O/'FREEZE.json').read_text());assert all(sha(ROOT/k)==v for k,v in z['sha256'].items());r=Pilot()
  try:r.run().write(O/'results')
  except BaseException as err:
   dest=O/('failed-'+datetime.now().strftime('%H%M%S'));r.write(dest);save(dest/'FAILURE.json',dict(error=repr(err)));raise
 elif sys.argv[1]=='prefix':Pilot('2025-12-31',['L1']).run('2025-12-31').write(O/'technical-prefix')
 else:raise ValueError(sys.argv[1])
