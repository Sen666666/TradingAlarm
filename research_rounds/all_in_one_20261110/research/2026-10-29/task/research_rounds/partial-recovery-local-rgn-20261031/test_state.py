from local import *
from types import SimpleNamespace
T=load('rgn_original_ledger_tests',RR/'rs-h1-execution-20261025/code/test_sector_account.py');base=T.T;res=[]
def c(at):return A.Clock(at,at+__import__('datetime').timedelta(days=1),at.date())
def mk(arm='G',delay=0,cash=10000,cap=400):return RiskSlice(sid='A',unit_id='u',group='g',cap=cap,old_B=9,seed_at=base,cash=cash,delay=delay)
def order(a,at,arm='R',floor=8,fresh=True,Q=True):return a.submit(arm=arm,clock=c(at),quote=T.quote(fees=T.MINIMUM),floor=floor,native_I=fresh,Q=Q,budget=a.available)
def fill(a,at,capacity=100000):return a.fill_buy('A',T.window(at=at,capacity=capacity,fees=T.MINIMUM,cash_due_at=at,eid=str(at)),factor=1)
def ob(price=10,factor=1,event=0,floor=8):return dict(raw_close=price,factor=factor,event=event,source_known=True,segment=0,event_known=True,floor=floor,floor_known=True)
def run(name,fn):fn();res.append(dict(name=name,passed=True));print(name,'PASS',flush=True)
def gate():
 a=mk();t=base+__import__('datetime').timedelta(days=1);assert not order(a,t,arm='G',floor=8)[0];assert a.gate_B==9;assert order(a,t+__import__('datetime').timedelta(days=1),arm='G',floor=9)[0];assert fill(a,t+__import__('datetime').timedelta(days=1)) is None;assert fill(a,c(t+__import__('datetime').timedelta(days=1)).earliest_execution_at).shares==400
run('gate_uses_floor_not_price_and_next_legal_fill',gate)
def stale():
 a=mk();at=base+__import__('datetime').timedelta(days=1);assert not order(a,at,fresh=False)[0];assert not order(a,at,Q=False)[0];assert not order(a,at,arm='N')[0];assert a.available==10000
run('fresh_Q_and_N_no_revival',stale)
def partial():
 a=mk();at=base+__import__('datetime').timedelta(days=1);order(a,at);op=c(at).earliest_execution_at;assert fill(a,op,100).shares==100;cid=a.controller.cycle_id;cl=op+__import__('datetime').timedelta(hours=6);a.close(clock=c(cl),quote=T.quote(),ob=ob(event=-1),sigma=.02,full=False);B=a.controller.boundary;assert fill(a,op+__import__('datetime').timedelta(hours=1),100).shares==100;assert a.controller.cycle_id==cid and a.controller.boundary==B
run('partial_buy_does_not_reset_controller',partial)
def waiting():
 a=mk();at=base+__import__('datetime').timedelta(days=1);a.close(clock=c(at),quote=T.quote(),ob=ob(price=2,event=-1),sigma=.5,full=False);assert a.gate_B==9 and a.controller is None
run('cash_negative_event_cannot_lower_old_B',waiting)
def partial_exit():
 a=mk();at=base+__import__('datetime').timedelta(days=1);order(a,at);op=c(at).earliest_execution_at;fill(a,op);cl=op+__import__('datetime').timedelta(hours=6);a.close(clock=c(cl),quote=T.quote(),ob=ob(event=-1),sigma=.02,full=False);cross=cl+__import__('datetime').timedelta(days=1);a.expire_day_buys(cross);a.close(clock=c(cross),quote=T.quote(),ob=ob(price=9.5),sigma=None,full=False);ex=c(cross).earliest_execution_at;assert a.fill_exit('A',T.window(at=ex,capacity=100,fees=T.MINIMUM)).shares==100;assert a.quantity('A')==300 and not order(a,ex+__import__('datetime').timedelta(hours=6))[0];a.fill_exit('A',T.window(at=ex+__import__('datetime').timedelta(days=1),fees=T.MINIMUM,eid='next-real-open'));assert a.quantity('A')==0 and a.gate_B>9 and a.controller.phase=='CLOSED',(a.quantity('A'),a.gate_B,a.controller.phase,a.exits)
run('only_executed_exit_releases_restore_partial_stays_pending',partial_exit)
def fullpriority():
 a=mk();at=base+__import__('datetime').timedelta(days=1);order(a,at);a.close(clock=c(at+__import__('datetime').timedelta(hours=1)),quote=T.quote(),ob=ob(floor=9),sigma=.02,full=True);assert not a.buys and a.ended and not order(a,at+__import__('datetime').timedelta(days=1),floor=10)[0]
run('full_exit_cancels_pending_and_terminates_old_contract',fullpriority)
def units():
 a=mk();at=base+__import__('datetime').timedelta(days=1);order(a,at);op=c(at).earliest_execution_at;fill(a,op);cl=op+__import__('datetime').timedelta(hours=6);a.close(clock=c(cl),quote=T.quote(),ob=ob(event=-1),sigma=.02,full=False);B=a.controller.boundary;a.split(event_id='sp',sid='A',ratio=D(2),at=cl+__import__('datetime').timedelta(days=1),new_shares_sellable_at=cl+__import__('datetime').timedelta(days=1));a.close(clock=c(cl+__import__('datetime').timedelta(days=1)),quote=T.quote(price=5),ob=ob(price=5,factor=2),sigma=None,full=False);assert a.controller.boundary==B and not a.exits and a.cap==800 and a.quantity('A')==800
run('split_same_economic_B_and_actual_shares',units)
def delay():
 a=mk(delay=1);at=base+__import__('datetime').timedelta(days=1);order(a,at);op=c(at).earliest_execution_at;assert fill(a,op) is None;cl=op+__import__('datetime').timedelta(hours=6);a.expire_day_buys(cl);assert order(a,cl)[0];assert a.buys['A'].delay_remaining==0;assert fill(a,c(cl).earliest_execution_at).shares==400
 b=mk(delay=1);order(b,at);fill(b,op);b.expire_day_buys(cl);assert not order(b,cl,fresh=False)[0];later=cl+__import__('datetime').timedelta(days=1);b.expire_day_buys(later);order(b,later);assert b.buys['A'].delay_remaining==1
run('delay_credit_requires_real_wait_and_new_signal_at_same_cutoff',delay)
def money():
 a=mk(cash=1000);at=base+__import__('datetime').timedelta(days=1);ok,why=order(a,at);assert not ok and why=='insufficient_budget_or_quantity' and a.available==1000
run('no_external_cash_to_meet_minimum_lot',money)
save(O/'STATE_TESTS.json',dict(passed=True,tests=res,real_ledger=True,original_RB2=True,history_or_economic_paths=0))
