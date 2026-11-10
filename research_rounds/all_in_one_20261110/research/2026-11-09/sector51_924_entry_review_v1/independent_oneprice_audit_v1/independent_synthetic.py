"""Independent adversarial micro-tests. No historical strategy runs or economics changes."""
from pathlib import Path
from decimal import Decimal as D
import sys,copy,json,hashlib,itertools
import pandas as pd
O=Path(__file__).resolve().parent;R=O.parent/'oneprice_execution_stress_v1'
sys.dont_write_bytecode=True;sys.path.insert(0,str(R))
import stress_engine as m
T=pd.Timestamp('2024-09-03');NEXT=T+pd.Timedelta(days=1);LATER=T+pd.Timedelta(days=2);ZERO=D(0)
class Market:
 names={s:s for s in ['a','b','old']};sid_sector={'a':'A','b':'B','old':'Z'};sector_ids=['A','B','Z'];events={}
 def __init__(self):self.bars={};self.cal=pd.DatetimeIndex([T-pd.Timedelta(days=1),T]);self.days=self.cal[1:]
 def z(self,s,d):return dict(dict(raw_open=10,raw_high=11,raw_low=9,raw_close=10,adjustment_factor=1,source_kind='local',source_path='fixture',segment_id=0),**self.bars.get((s,str(d.date())),{}))
 def fee(self,s,d,q,p,side):return D(5)+D(q)*p*D('.0001') if q else ZERO
 def getmeta(self,s,d):return m.b.QuantityRule('independent',100,100,100,True,1),None,None
 def size(self,s,d,p,budget,cap):
  q=max(0,min(int(cap),int(budget/p))//100*100)
  while q and q*p+self.fee(s,d,q,p,'buy')>budget:q-=100
  return q
 def bar(self,s,d=T,**k):self.bars[(s,str(d.date()))]=k
 def constant(self,s,d=T):self.bar(s,d,raw_open=10,raw_high=10,raw_low=10,raw_close=10)
 def action(self,s,d):return []
def seed(s):return dict(kind='SEED',sid=s,birth_type='A',signal_day='2024-09-02',budget=D(24000),planned_q=100,capacity=100,ifloor=D(5),factor=D(1),origin=('local','fixture','0'),nav0=D(1200000))
def attempt(s,q=100,exit=None,bought='2024-09-02',kind='SEED'):
 return dict(id=s+'|R',sid=s,signal_day='2024-08-30',birth_type='A',lots=[dict(id=s+'|L',q=q,kind=kind,bought=bought,floor=D(5),cp_id=None)],ifloor=D(5),factor=D(1),origin=('local','fixture','0'),exit=exit,plan=None,cp=None,cashflow=D(-900),dividend=ZERO,fees=ZERO,nav0=D(1200000),add_count=0,seed_day='2024-09-02')
def with_add(s,q=100,planned=100):
 a=attempt(s,q);a['cp']=dict(id=s+'CP',date='2024-09-02',floor=D(5),origin=a['origin'],consumed=False,invalid=False);a['plan']=dict(kind='ADD',sid=s,signal_day='2024-09-02',cp_date='2024-09-02',cp_id=s+'CP',budget=D(24000),planned_q=planned,capacity=planned,close_net='90',origin=a['origin'],factor=D(1));return a
def inject(e,a):e.active[a['sid']]=a;e.archive[a['id']]=a
class Tracked(m.StressEngine):
 def __init__(self,d,gate=True):super().__init__(d,gate);self.gate_calls=[]
 def no_fill(self,s,d):self.gate_calls.append((s,d));return super().no_fill(s,d)
def batch(e,p=(),dt=T):
 n=len(e.gate_calls);e.freeze_intent(dt,list(p));assert len(e.gate_calls)==n,'GATE_USED_TO_BUILD_INTENT';e.exit_open(dt);e.alloc_open(dt,list(p))
checks=[];counts={}
def ok(name,n=1):checks.append(name);counts[name]=n
# The same OPEN intents must survive all changes to ex-post H/L/C and actual prior
# state must be untouched by freezing. All combinations have the same OPEN inputs.
for cash in [120000,122000,124000,200000]:
 for gs,ga,gb in itertools.product([False,True],repeat=3):
  d=Market();e=Tracked(d);e.cash=D(cash);old=attempt('old',(1200000-cash)//10,'LOCKED');inject(e,old)
  for s,g in [('old',gs),('a',ga),('b',gb)]:
   if g:d.constant(s)
  state=copy.deepcopy((e.cash,e.active,e.archive,e.seq));e.freeze_intent(T,[seed('b'),seed('a')]);assert not e.gate_calls and state==copy.deepcopy((e.cash,e.active,e.archive,e.seq))
  assert e.archive['old|R'] is e.active['old'];assert [r['side'] for r in e._intent_orders]==['SELL_ALL','BUY_SEED','BUY_SEED']
  e.exit_open(T);post_cash=D(cash)
  if not gs:post_cash+=old['lots'][0]['q']*D('9.995')-d.fee('old',T,old['lots'][0]['q'],D('9.995'),'sell') if old['lots'] else D(0)
  # Use the known initial inventory, since a successful exit emptied old's lots.
  oldq=(1200000-cash)//10
  post_cash=D(cash)+(oldq*D('9.995')-d.fee('old',T,oldq,D('9.995'),'sell') if not gs else ZERO)
  nav=post_cash+(oldq*10 if gs else 0);reserved=[];shadow=post_cash;cost=D(100)*D('10.005')+d.fee('a',T,100,D('10.005'),'buy')
  for s,g in [('a',ga),('b',gb)]:
   if shadow-D('.1')*nav>=cost:shadow-=cost;reserved.append((s,g))
  e.alloc_open(T,[seed('b'),seed('a')]);assert [x['sid'] for x in e.reservations]==[s for s,g in reserved]
  assert e.cash==post_cash-sum((cost for s,g in reserved if not g),ZERO)
  assert [x['sid'] for x in e.orders if x['side']=='BUY_SEED']==[s for s,g in reserved if not g]
  assert [x['sid'] for x in e.nofills if x['side']=='BUY_SEED']==[s for s,g in reserved if g]
  if gs:assert e.quantity(e.active['old'])==oldq and all(l['exit'] for l in e.active['old']['lots'])
  else:assert 'old' not in e.active
ok('32_failed_sale_buy_gate_cash_reservation_combinations',32)
# A denied first reservation must not recycle into the second original rejection.
d=Market();e=Tracked(d);e.cash=D(122000);inject(e,attempt('old',107800));d.constant('a');batch(e,[seed('b'),seed('a')]);assert not e.orders and e.cash==D(122000);assert [(x['sid'],x['kind']) for x in e.reservations]==[('a','SEED')];assert e._intent_candidates[1]['decision'].startswith('MIN_LOT_CAPITAL_REJECT');assert e.candidates[1]['executed_q']==0
ok('no_buy_gate_cash_recycling_or_original_reject_resurrection')
# Failed sale permits only a reduced original ADD when actual cash is insufficient.
d=Market();e=Tracked(d);e.cash=D(123000);inject(e,attempt('old',107600,'LOCKED'));a=with_add('a',planned=2300);inject(e,a);d.constant('old');batch(e);assert e._intent_candidates[0]['executed_q']==2300;assert e.reservations[0]['reserved_q']==200;assert e.orders[0]['side']=='BUY_ADD' and e.orders[0]['qty']==200;assert e.cash==D(123000)-D(200)*D('10.005')-d.fee('a',T,200,D('10.005'),'buy')
ok('failed_sale_shrinks_original_ADD_without_fictitious_cash')
# Gate cannot change frozen intentions, create an attempt or consume a CP.
d=Market();e=Tracked(d);a=with_add('a');inject(e,a);d.constant('a');before=copy.deepcopy(a['cp']);batch(e);assert a['cp']==before and a['add_count']==0 and not e.orders and e.quantity(a)==100;a['plan']=with_add('a')['plan'];batch(e,dt=NEXT);assert len(e.orders)==1 and a['cp'] is None and a['add_count']==1
ok('ADD_no_fill_preserves_CP_actual_retry_consumes_once')
d=Market();e=Tracked(d);d.constant('a');batch(e,[seed('a')]);assert not e.active and not e.archive and not e.seq and e.cash==D(1200000);batch(e,dt=NEXT);assert not e.orders and not e.active
ok('SEED_no_fill_creates_no_attempt_and_old_ticket_is_not_stored')
# Partial layer exit remains locked even after the price rebounds above the floor.
d=Market();e=Tracked(d);a=attempt('a');a['lots'].append(dict(id='a|ADD',q=100,kind='ADD',bought='2024-09-02',floor=D(11),cp_id='c'));inject(e,a);d.constant('a');batch(e);assert e.quantity(a)==200 and a['lots'][1]['exit'] and a['exit'] is None;d.bar('a',NEXT,raw_open=12,raw_high=13,raw_low=11,raw_close=12);batch(e,dt=NEXT);assert e.quantity(a)==100 and e.orders[-1]['side']=='SELL_LAYERS' and e.orders[-1]['lots']==['a|ADD']
ok('failed_partial_sell_retains_lot_exit_lock_after_rebound')
d=Market();e=Tracked(d);a=attempt('a',exit='LOCKED',bought=str(T.date()));inject(e,a);d.constant('a');batch(e);assert not e.nofills and not e.orders and a['lots'][0]['exit']=='T1_LOCKED_EXIT';d.constant('a',NEXT);batch(e,dt=NEXT);assert len(e.nofills)==1 and not e.orders;batch(e,dt=LATER);assert not e.active and len(e.orders)==1
ok('T1_no_attempt_then_failed_sale_then_valid_retry')
# Test a real missing-gate failure after an actual SELL and first ADD mutated state.
class Rollback(Tracked):
 def economic_preflight(self,d,pending):pass
 def accrue(self,d):pass
 def close(self,d,prev):raise AssertionError('should block before close')
d=Market();e=Rollback(d);inject(e,attempt('old',100,exit='LOCKED'));inject(e,with_add('a'));inject(e,with_add('b'));d.bar('b',raw_high=float('nan'))
keys=['cash','receivable','active','archive','seq','claims','snapshots'];initial=copy.deepcopy({k:getattr(e,k) for k in keys});e.run();assert len(e.uncertified_day['partial_orders'])==2 and e.blockers;assert {k:getattr(e,k) for k in keys}==initial;assert all(e.active[s] is e.archive[a['id']] for s,a in e.active.items());assert all(not getattr(e,k) for k in ['orders','candidates','cp_log','ledger','holdings','equity','sector_daily','nofills','intents','reservations'])
ok('real_mid_batch_missing_gate_rolls_back_sell_ADD_CP_state_and_all_logs')
# Check the gate itself, and baseline equality when explicitly disabled.
d=Market();e=Tracked(d);d.constant('a');assert e.no_fill('a',T);d.bar('a',raw_open=10,raw_high=10.000001,raw_low=10,raw_close=10);assert not e.no_fill('a',T)
for value in [float('nan'),0,-1]:
 d.bar('a',raw_high=value)
 try:e.no_fill('a',T)
 except m.Blocked:pass
 else:raise AssertionError('invalid gate must block')
ok('exact_equality_and_invalid_gate_fail_closed',4)
for cash in [120000,122000,200000,1200000]:
 d=Market();d.constant('a');e=Tracked(d,False);base=m.b.Engine(d);e.cash=base.cash=D(cash);a=with_add('a');inject(e,a);inject(base,copy.deepcopy(a));batch(e,[seed('b')]);base.exit_open(T);base.alloc_open(T,[seed('b')])
 assert e.cash==base.cash and e.active==base.active and e.archive==base.archive and e.orders==base.orders and e.cp_log==base.cp_log
 extra={'original_intended_q','reserved_q','fill_status'};assert [{k:v for k,v in r.items() if k not in extra} for r in e.candidates]==base.candidates
ok('gate_disabled_exact_baseline_account_orders_candidates',4)
report=dict(status='PASS',tests=checks,cases=sum(counts.values()),case_counts=counts,engine_sha256=hashlib.sha256((R/'stress_engine.py').read_bytes()).hexdigest(),source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Independent adversarial synthetic execution tests, not historical fill certification. Fixture written separately from implementation synthetic_stress.py.')
(O/'INDEPENDENT_SYNTHETIC.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
