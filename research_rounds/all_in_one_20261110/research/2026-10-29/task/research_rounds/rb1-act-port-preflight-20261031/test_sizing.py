from pathlib import Path
from types import SimpleNamespace as S
from datetime import timedelta
from dataclasses import replace
from decimal import Decimal as D
import importlib.util,sys,json,time,hashlib
from sizing_adapter import account_class
O=Path(__file__).resolve().parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');start=time.monotonic()
def load(n,p):
 sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sys.modules[n]=m;sp.loader.exec_module(m);return m
P=load('rb1_preflight_original_setup',RR/'pvr-act-comparison-20261027/code/experiment.py');P.setup('RS');E=P.E;A=E.admission;L=E.ledger
T=load('rb1_preflight_real_ledger_fixture',RR/'rs-h1-execution-20261025/code/test_sector_account.py')
sys.path.insert(0,str(RR/'swf-pvr-combination-20261028/code'))
Q=load('rb1_preflight_drug_original_account',RR/'swf-pvr-combination-20261028/code/study.py')
results=[];t0=T.T
def clock(t):return A.Clock(t,t+timedelta(days=1),t.date())
def make(enabled=True,Parent=E.Account,mode='I',nav=1000000,fees=None,delay=0,floor=5):
 C=account_class(Parent);a=C(initial_cash=nav,delay_events=delay);a.rb1_sizing=enabled;a.mode=mode;a.current_nav=D(nav)
 st=dict(floor=None if floor is None else D(str(floor)),factor=D(1))
 a.facts=S(floor=lambda *_:st['floor'],factor=lambda *_:st['factor'],row=lambda *_:S(i_buy=True,e0_target=True))
 return a,st
def reserve(a,t=t0,price=10,budget=150000,sid='A',rule=None,fees=None):
 return a.reserve_budget(quote=T.quote(sid=sid,price=price,rule=rule or T.RULE,fees=fees or T.FREE),clock=clock(t),gross_budget_cny=D(budget))
def win(t=None,price=10,fees=None,**kw):return T.window(at=t or clock(t0).earliest_execution_at,price=price,fees=fees or T.FREE,**kw)
def view(a):
 return dict(available=a.available,buys=a.buys,positions=a.positions,exits=a.exits,fills=a.fills,audit=a.audit_log,intents=a.intents,rearm=a.rearm,completed=a.completed,settlements=a.settlements)
def run(name,fn):fn();results.append(dict(name=name,passed=True));print(name,'PASS',flush=True)

def off_exact():
 for Parent,mode in [(E.Account,'I'),(Q.Account,'ACT')]:
  a,st=make(False,Parent,mode);b=Parent(initial_cash=1000000);b.mode=mode;b.current_nav=D(1000000);b.facts=a.facts
  assert reserve(a,fees=T.MINIMUM)==reserve(b,fees=T.MINIMUM)
  for k in range(2):
   w=win(t=clock(t0).earliest_execution_at+timedelta(hours=k),fees=T.MINIMUM,capacity=100,eid=f'part{k}')
   assert a.fill_buy('A',w)==b.fill_buy('A',w)
  assert view(a)==view(b) and a.mode==mode
run('off_exact_original_TECH_and_DRUG_reserve_partial_fill_cash_audit',off_exact)

def old_rb1_exact():
 for Parent,mode in [(E.Account,'I'),(Q.Account,'ACT')]:
  a,st=make(True,Parent,mode);b=Parent(initial_cash=1000000);b.mode='RB1';b.current_nav=D(1000000);b.facts=a.facts
  assert reserve(a,fees=T.MINIMUM)==reserve(b,fees=T.MINIMUM)
  assert a.fill_buy('A',win(price=D('10.005'),fees=T.MINIMUM))==b.fill_buy('A',win(price=D('10.005'),fees=T.MINIMUM))
  assert view(a)==view(b) and a.mode==mode
run('on_exact_existing_RB1_math_both_super_chains_native_mode_restored',old_rb1_exact)

def widths():
 a,_=make(floor=5);b,_=make(floor=D('9.9'));assert reserve(a)[0] and reserve(b)[0]
 assert a.buys['A'].target_shares==1900 and b.buys['A'].target_shares==15000
 for x in [a,b]:
  o=x.buys['A'];z=x.intents[o.order_id];f=x.facts.floor('A',t0)
  assert x.loss(o.quote,o.target_shares,D(10),f)<=z['risk_budget']==10000
run('hand_expected_wide_1900_narrow_15000_same_1pct_and_15pct_cap',widths)

def minimum_and_unknown():
 a,_=make(floor=1);ok,reason=reserve(a,price=1000);assert not ok and reason=='risk_minimum_quantity' and a.available==1000000 and not a.buys and not a.occupancy(t0)
 a,_=make(floor=None);assert reserve(a)[1]=='risk_support_invalid' and a.available==1000000
 a,_=make(floor=10);assert reserve(a)[1]=='risk_support_invalid'
run('minimum_unit_reject_no_reserve_slot_missing_floor_and_equal_support',minimum_and_unknown)

def upward_gap():
 a,_=make();reserve(a);q0=a.buys['A'].target_shares;budget=a.buys['A'].budget_cny;f=a.fill_buy('A',win(price=20));assert f and f.shares<q0 and f.gross_cny<=budget and a.mode=='I'
 assert all(x['estimated_loss']<=x['risk_budget'] for x in a.audit_log if x['kind']=='risk_fill_bound')
run('up_gap_only_shrinks_frozen_cash_and_quantity_under_original_RB1',upward_gap)

def lower_gap():
 a,_=make();reserve(a);q=a.buys['A'].target_shares;f=a.fill_buy('A',win(price=9));assert f and f.shares==q
run('down_gap_cannot_expand_frozen_quantity',lower_gap)

def below_support():
 a,_=make();reserve(a);assert a.fill_buy('A',win(price=4)) is None and not a.buys and not a.positions and 'A' in a.rearm
run('open_below_support_original_cancel_and_rearm_no_fake_inventory',below_support)

def partial():
 a,_=make();reserve(a,fees=T.MINIMUM);o=a.buys['A'];R=a.intents[o.order_id]['risk_budget'];t=clock(t0).earliest_execution_at
 f1=a.fill_buy('A',win(t=t,fees=T.MINIMUM,capacity=100,eid='p1'));assert f1 and f1.shares==100
 f2=a.fill_buy('A',win(t=t+timedelta(hours=1),price=12,fees=T.MINIMUM,capacity=100,eid='p2'));assert f2 and a.intents[o.order_id]['risk_budget']==R
 rows=[x for x in a.audit_log if x['kind']=='risk_fill_bound'];assert len(rows)==2 and all(x['estimated_loss']<=R for x in rows)
 assert sum(f.fees_cny for f in [f1,f2])==5
run('partial_fills_keep_one_risk_budget_prior_cost_and_one_minimum_fee',partial)

def partial_cancel():
 a,_=make();reserve(a);t=clock(t0).earliest_execution_at;a.fill_buy('A',win(t=t,capacity=100,eid='first'));q=a.quantity('A')
 assert a.fill_buy('A',win(t=t+timedelta(hours=1),price=4,eid='bad')) is None
 assert a.quantity('A')==q and q>0 and not a.buys and not a.exits
run('partial_cancel_preserves_actual_holding_no_invented_risk_exit',partial_cancel)

def split_units():
 a,st=make();reserve(a);n=a.buys['A'].target_shares;t=t0+timedelta(hours=1)
 a.split(event_id='split',sid='A',ratio=D(2),at=t,new_shares_sellable_at=t);st['factor']=D(2)
 assert a.buys['A'].target_shares==2*n
 f=a.fill_buy('A',win(price=5));assert f and f.shares==2*n
 bound=[x for x in a.audit_log if x['kind']=='risk_fill_bound'][-1];assert bound['floor']==D('2.5') and bound['risk_budget']==10000 and bound['estimated_loss']<=10000
run('pending_split_quantities_and_frozen_floor_same_economic_units',split_units)

def cost2():
 a,_=make();a.cost_multiplier=2;reserve(a,fees=T.MINIMUM);f=a.fill_buy('A',win(price=D('10.01'),fees=T.MINIMUM));assert f
 rows=[x for x in a.audit_log if x['kind']=='risk_fill_bound'];assert rows[-1]['estimated_loss']<=10000 and rows[-1]['risk_budget']==10000
run('cost2_original_incremental_fees_and_slip_same_1pct_not_new_budget',cost2)

def delay():
 a,_=make(delay=1);reserve(a);op=clock(t0).earliest_execution_at
 assert a.fill_buy('A',win(t=op,eid='delay1')) is None
 expired=a.expire_day_buys(op+timedelta(hours=6));assert expired=={'A'} and not a.buys
 # This call stands for a new originally eligible I order; credit alone creates none.
 assert a.quantity('A')==0;assert reserve(a,t=op+timedelta(hours=6))[0]
 assert a.buys['A'].delay_remaining==0
 assert a.fill_buy('A',win(t=clock(op+timedelta(hours=6)).earliest_execution_at,eid='fresh'))
run('original_delay_expiry_credit_no_automatic_old_order_resurrection',delay)

def securities(t,ids=('A','B'),same_sector=True,up=True,fresh=True):
 def fact(v):return A.Fact(v,t,t,observed_at=t)
 ss=tuple(A.Security(s,fact(s),fact('G' if same_sector else 'H'+s),fact(True),fact(fresh),fact(20e9),fact(up),A.Rank(90-k,t,t)) for k,s in enumerate(ids))
 gs=tuple(A.Sector(g,fact(True),A.Rank(70-k,t,t)) for k,g in enumerate(dict.fromkeys('G' if same_sector else 'H'+s for s in ids)))
 return ss,gs
def admission(a,t,ss,gs,previous=(),completed=()):
 factory=lambda **kw:A.decide(clock=clock(t),variant='S0',securities=ss,sectors=gs,**kw)
 quotes={s.security_id:T.quote(sid=s.security_id,price=1000 if s.security_id=='A' else 10) for s in ss}
 return L.commit_cutoff(a,decision_factory=factory,clock=clock(t),quotes=quotes,marks={},previous=previous,bootstrap=not previous,completed_exits=completed)
def priority():
 a,_=make();ss,gg=securities(t0,ids=('A','B','C'));d=A.decide(clock=clock(t0),variant='S0',securities=ss,sectors=gg,bootstrap=True)
 before=d.selected;ack=admission(a,t0,ss,gg)
 assert before==('A','B') and ('A','risk_minimum_quantity') in ack.rejected and ack.accepted==('B','C') and a.buys['B'].target_shares>0
 assert [x.security_id for x in d.eligibility if x.q is True]==['A','B','C']
run('same_native_priority_and_Q_risk_rejection_changes_only_real_admission',priority)

def act_native():
 a,_=make(mode='ACT',Parent=Q.Account);reserve(a);a.fill_buy('A',win());t=clock(t0).earliest_execution_at+timedelta(hours=6)
 a.risk_state=dict(on=False,peak=D(1000000),saw_off=True,previous_fast=False,episode=0)
 ss,gg=securities(t,ids=('A',));out=E.risk_policy.override(a,ss,clock(t),'ACT20_BREAK',A.Fact)
 assert out[0].trend_up.read(clock(t)) is False and out[0].buy_allowed.read(clock(t)) is False
 assert a.mode=='ACT'
run('DRUG_native_ACT_mode_survives_sizing_and_original_pause_forces_exit',act_native)

def cash_budget():
 a,_=make(nav=10000,floor=D('9.99'));ok,_=reserve(a,budget=1500,fees=T.MINIMUM);assert ok
 o=a.buys['A'];assert o.budget_cny<=1500 and o.budget_cny+o.fee_reserved_cny<=10000
 # Six small commitments consume six slots despite spare cash: sizing is not a slot waiver.
 assert o.target_shares==100 and a.available>8000
run('budget_cash_and_minimum_fee_still_bind_no_forced_full_risk',cash_budget)

def original_fresh_reentry():
 a,_=make();reserve(a);op=clock(t0).earliest_execution_at;f=a.fill_buy('A',win(t=op,cash_due_at=op,eid='initial'));a.settle_due(op)
 def cut(t,previous=(),fresh=True,up=True,completed=()):
  ss,gg=securities(t,ids=('A',),fresh=fresh,up=up)
  factory=lambda **kw:A.decide(clock=clock(t),variant='S0',securities=ss,sectors=gg,**kw)
  return L.commit_cutoff(a,decision_factory=factory,clock=clock(t),quotes={'A':T.quote()},marks=T.marks(t) if a.quantity('A') else {},previous=previous,bootstrap=not previous,completed_exits=completed)
 t=op+timedelta(hours=6);ack=cut(t,up=False);assert 'A' in a.exits
 ex=clock(t).earliest_execution_at;a.fill_exit('A',win(t=ex,cash_due_at=ex,eid='exit'));a.settle_due(ex);assert not a.quantity('A')
 t=ex+timedelta(hours=6);ack=cut(t,ack.memories,fresh=False,completed=tuple(a.completed));assert not a.buys
 t+=timedelta(days=1);a.current_nav=a.balance(t,{})['nav'];ack=cut(t,ack.memories,fresh=True)
 assert ack.accepted==('A',) and a.buys['A'].purpose=='initial' and a.mode=='I'
 assert a.intents[a.buys['A'].order_id]['risk_budget']==a.current_nav*D('.01')
run('real_original_exit_memory_and_fresh_reentry_new_1pct_order_no_priority',original_fresh_reentry)

def exception_restores():
 a,_=make(mode='ACT',Parent=Q.Account)
 def broken(*_):raise ValueError('synthetic missing input')
 a.facts.floor=broken
 try:reserve(a)
 except ValueError:pass
 else:raise AssertionError('missing exception')
 assert a.mode=='ACT' and not a.buys
run('exception_always_restores_original_policy_mode',exception_restores)

paths=[Path(__file__),O/'sizing_adapter.py',O/'PROTOCOL.txt',RR/'actual-risk-recovery-20261027/code/engine.py',RR/'rs-h1-execution-20261025/code/sector_account.py',RR/'swf-pvr-combination-20261028/code/study.py']
(O/'SYNTHETIC.json').write_text(json.dumps(dict(passed=True,tests=results,seconds=time.monotonic()-start,source_methods_reused=True,real_ledger_and_admission=True,historical_accounts_run=0,new_economic_paths=0,source_sha256={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}),ensure_ascii=False,indent=2))
print('PASS',len(results),'seconds',time.monotonic()-start,flush=True)
