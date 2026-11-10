"""Actual hooks + original Decimal ledger and original admission. No historical returns."""
import wire as w
from datetime import timedelta
from types import SimpleNamespace
import time,shutil
O=w.O;root=O/('synthetic-'+str(len(list(O.glob('synthetic-*')))));root.mkdir(exist_ok=False);shutil.copyfile(w.RR/'pvr-act-comparison-20261027/execution-rules-v2.json',root/'execution-rules-v2.json');t0=time.monotonic()
R,E,_,_,_,_=w.setup('TECH',root,False);ad=E.admission
T=w.load('full_rb_ledger_fixtures',w.RR/'rs-h1-execution-20261025/code/test_sector_account.py');D=w.D
checks=[]
def passed(name,**kw):checks.append(dict(name=name,passed=True,**kw))
class Feed:
 epoch='E0-1';price=10;negative=False;factor=1
 def context(self,sid,at):return dict(source_id=sid+'|source=0',unit_id=sid+'|unit=0',source_segment=0,structure_id=self.epoch,decision_at=at)
 def observation(self,sid,at,c):
  b=at.date().toordinal();r=w.NegativeReceipt(sid+'|neg|'+str(b),sid,sid+'|source=0',b) if self.negative else None
  return dict(bar=b,raw_close=self.price,factor=self.factor,unit_id=sid+'|unit=0',negative=r,sigma=.02 if r else None,updated_floor=8,floor_known=True,event_feed_known=True),{}
feed=Feed();Account=w.account_class(E.Account,feed,True)
def fresh():
 a=Account(initial_cash=10000);a.facts=SimpleNamespace(floor=lambda *_:D(8),factor=lambda *_:D(1));return a
def clock(at):return ad.Clock(at,at+timedelta(days=1),at.date())
def packet(at,buy=True):
 f=lambda x:ad.Fact(x,at,at,observed_at=at);s=ad.Security('A',f('A'),f('G'),f(True),f(buy),f(20e9),f(True),ad.Rank(80,at,at));g=ad.Sector('G',f(True),ad.Rank(70,at,at));return (s,),(g,)
def commit(a,at,stocks=None,previous=(),completions=(),buy=True,price=10):
 ss,gs=packet(at,buy);ss=stocks or ss;cl=clock(at)
 return E.ledger.commit_cutoff(a,decision_factory=lambda **kw:ad.decide(clock=cl,variant='S0',securities=ss,sectors=gs,**kw),clock=cl,quotes={'A':T.quote(price=price,fees=T.MINIMUM)},marks=T.marks(at,price) if a.quantity('A') else {},previous=previous,bootstrap=not previous,completed_exits=completions)
def start(partial=False):
 a=fresh();at=T.T;a.reserve_budget(quote=T.quote(fees=T.MINIMUM),clock=clock(at),gross_budget_cny=2000)
 f=a.fill_buy('A',T.window(at=at+timedelta(days=1),capacity=100 if partial else 1000,fees=T.MINIMUM));assert f and 'A' in a.rb_states;return a
def trigger(a):
 feed.price=10;feed.negative=True;at=T.T+timedelta(days=2);ss,_=packet(at);w.process(a,ss,clock(at),ad.Fact,feed);c=a.rb_states['A'];assert c.phase=='PROTECTED'
 feed.price=9.5;feed.negative=False;at+=timedelta(days=1);ss,_=packet(at);s=w.process(a,ss,clock(at),ad.Fact,feed);assert c.exit_locked;ack=commit(a,at,stocks=s,price=9.5);assert 'A' in a.exits and 'A' not in a.buys;return at,ack
def sold(a,at,capacity=1000):
 return a.fill_exit('A',T.window(at=at,eid='sell-'+str(at),price=9.5,capacity=capacity,fees=T.MINIMUM,cash_due_at=at))
a=start(True);cid=a.rb_states['A'].cycle_id;at,ack=trigger(a);assert a.quantity('A')==100 and a.rb_states['A'].cycle_id==cid;passed('partial_buy_keeps_position_and_risk_cancels_remainder',shares=100)
bad=T.window(at=at+timedelta(days=1),eid='blocked-sell',sell_allowed=False);assert a.fill_exit('A',bad) is None;assert a.rb_states['A'].exit_locked and a.quantity('A')==100;ss,_=packet(bad.at);d=commit(a,bad.at,previous=ack.memories);assert 'A' not in d.accepted;passed('blocked_sale_retains_exit_responsibility_no_fake_reentry')
saleat=at+timedelta(days=2);sold(a,saleat);a.settle_due(saleat);assert not a.quantity('A') and 'A' not in a.rb_states;flatcash=a.available
at2=saleat+timedelta(hours=6);stale=commit(a,at2,previous=d.memories,completions=tuple(a.completed),buy=False);assert not stale.accepted;passed('cleared_exit_without_new_I_does_not_revive_old_intent')
nextday=at2+timedelta(days=1);same=commit(a,nextday,previous=stale.memories);assert same.accepted==('A',);order=a.buys['A'];assert order.created_at==nextday;f=a.fill_buy('A',T.window(at=clock(nextday).earliest_execution_at,eid='reentry-1',fees=T.MINIMUM));assert f and a.rb_meta['A']['context']['structure_id']=='E0-1' and a.rb_states['A'].cycle_id!=cid;passed('same_structure_new_signal_uses_real_cash_new_controller',available_after_sale=str(flatcash))
a=start();at,ack=trigger(a);saleat=at+timedelta(days=1);sold(a,saleat);a.settle_due(saleat);close=saleat+timedelta(hours=6);ack2=commit(a,close,previous=ack.memories,completions=tuple(a.completed));assert ack2.accepted==('A',);assert a.buys['A'].earliest_at>close;assert a.fill_buy('A',T.window(at=clock(close).earliest_execution_at,eid='same-day-next-open',fees=T.MINIMUM));passed('flat_open_then_new_close_signal_allowed_next_legal_open')
a=start();at,ack=trigger(a);saleat=at+timedelta(days=1);sold(a,saleat,100);assert a.quantity('A')>0 and a.rb_states['A'].exit_locked;no=commit(a,saleat+timedelta(hours=6),previous=ack.memories);assert not no.accepted;passed('partial_exit_still_occupies_and_does_not_reset')
sold(a,saleat+timedelta(days=1));a.settle_due(saleat+timedelta(days=1));feed.epoch='E0-2';later=saleat+timedelta(days=1,hours=6);new=commit(a,later,previous=no.memories,completions=tuple(a.completed));assert new.accepted==('A',);a.fill_buy('A',T.window(at=clock(later).earliest_execution_at,eid='new-epoch',fees=T.MINIMUM));assert a.rb_meta['A']['context']['structure_id']=='E0-2' and not a.rb_states['A'].seen;passed('true_new_structure_real_fill_resets_without_replaying_receipts')
a=fresh();a.reserve_budget(quote=T.quote('B',price=10),clock=clock(T.T),gross_budget_cny=9900);ack=commit(a,T.T,price=100);assert not ack.accepted and ack.rejected;passed('other_reservation_blocks_unfunded_recovery_no_injection',reasons=ack.rejected)
rp=w.load('full_rb_synthetic_risk',w.RR/'actual-risk-recovery-20261027/code/risk_policy.py');state=dict(on=True,peak=D(10000),saw_off=False,previous_fast=False,episode=0);state,_,event=rp.advance(state,D(7900),False,True,False,'ACT20_BREAK');assert event=='pause';a=fresh();a.risk_state=state;ss,_=packet(T.T);ss=rp.override(a,ss,clock(T.T),'ACT20_BREAK',ad.Fact);assert ss[0].buy_allowed.read(clock(T.T)) is False;state,_,event=rp.advance(state,D(7900),True,True,False,'ACT20_BREAK');assert not state['on'];passed('original_ACT_pause_blocks_new_entries_until_own_recovery')
# Repeated attempts pay original minimum commission each round; no synthetic cash reset.
a=start();mem=()
for i in range(2):
 at=T.T+timedelta(days=2+5*i);feed.price=10;feed.negative=True;ss,_=packet(at);w.process(a,ss,clock(at),ad.Fact,feed);at+=timedelta(days=1);feed.price=9.5;feed.negative=False;ss,_=packet(at);ss=w.process(a,ss,clock(at),ad.Fact,feed);ack=commit(a,at,stocks=ss,previous=mem,price=9.5);sat=at+timedelta(days=1);sold(a,sat);a.settle_due(sat);cl=sat+timedelta(hours=6);ack=commit(a,cl,previous=ack.memories,completions=(a.completed[-1],));assert ack.accepted==('A',);mem=ack.memories;a.fill_buy('A',T.window(at=clock(cl).earliest_execution_at,eid='repeat-'+str(i),fees=T.MINIMUM))
assert a.fees_cny==D(25) and len(a.fills)==5 and a.balance(cl+timedelta(days=1),T.marks(cl+timedelta(days=1)))['nav']<D(10000);passed('two_same_structure_retries_keep_all_five_order_fees',fees=str(a.fees_cny),fills=5)
a=start();at=T.T+timedelta(days=2);feed.price=10;feed.negative=True;ss,_=packet(at);w.process(a,ss,clock(at),ad.Fact,feed);q=a.quantity('A');at+=timedelta(days=1);a.split(event_id='synthetic-split',sid='A',ratio=2,at=at,new_shares_sellable_at=at);feed.price=5;feed.factor=2;feed.negative=False;ss,_=packet(at);w.process(a,ss,clock(at),ad.Fact,feed);assert a.quantity('A')==2*q and not a.rb_states['A'].exit_locked and a.rb_states['A'].shares==2*q;passed('original_split_updates_actual_quantity_economic_boundary_unchanged');feed.factor=1
assert all(x['passed'] for x in checks)
elapsed=time.monotonic()-t0;budget=O/'COMPUTE_TIME.json';record=w.read(budget) if budget.exists() else dict(seconds=0,stages=[]);record['seconds']+=elapsed;record['stages'].append(dict(stage='synthetic',seconds=elapsed,status='complete'));budget.write_text(w.json.dumps(record,indent=2));(O/'SYNTHETIC.json').write_text(w.json.dumps(dict(passed=True,actual_ledger_admission_hooks=True,checks=checks,seconds=elapsed),indent=2,default=str));print(checks)
