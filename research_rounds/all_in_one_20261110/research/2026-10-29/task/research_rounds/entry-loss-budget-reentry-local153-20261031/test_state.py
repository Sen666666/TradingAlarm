from core import *
T=load('budget_reentry_fixtures',S.RR/'rs-h1-execution-20261025/code/test_sector_account.py');base=T.T;res=[]
def clock(t):return A.Clock(t,t+timedelta(days=1),t.date())
def start(q=1000,K=D(10010)):
 a=Wallet(symbol='A',cycle_id='u',b=D('.1'),K=K,q=q,quote=T.quote(fees=T.MINIMUM),sellable=base);a.request_exit(T.quote(fees=T.MINIMUM),clock(base));op=clock(base).earliest_execution_at;f=a.fill_exit('A',T.window(at=op,price=8.8,fees=T.MINIMUM,cash_due_at=op,eid='first-sale'));a.settle_due(op);assert f and not a.quantity('A');return a,op

def restore(a,t,price=10,fresh=True,Q=True):return a.reserve_restore(clock=clock(t),quote=T.quote(price=price,fees=T.MINIMUM),floor=D(1),budget=a.available,fresh=fresh,Q=Q)
def fill(a,t,price=10,capacity=100000):return a.fill_buy('A',T.window(at=t,price=price,fees=T.MINIMUM,cash_due_at=t,capacity=capacity,eid='fill-'+str(t)),D(1))
def run(name,fn):fn();res.append(dict(name=name,passed=True));print(name,'PASS')
def high_whipsaw():
 a,op=start();cash=a.available;cl=op+timedelta(hours=6);assert restore(a,cl)[0];f=fill(a,clock(cl).earliest_execution_at);assert f and f.shares==800 and a.leg.K==f.gross_cny+f.fees_cny;assert a.leg.number==2 and a.available<cash;newt=f.at+timedelta(hours=6);assert a.leg.controller.close(V=D(7000),known=True,at=str(newt));a.request_exit(T.quote(fees=T.MINIMUM),clock(newt));ex=clock(newt).earliest_execution_at;f2=a.fill_exit('A',T.window(at=ex,price=8.8,fees=T.MINIMUM,cash_due_at=ex,eid='second-sale'));a.settle_due(ex);assert a.available<D(10010)*D('.8')
run('low_sale_high_restore_reloss_cumulative_not_reset_to_single_budget',high_whipsaw)
def lower_growth():
 a,op=start();cl=op+timedelta(hours=6);assert restore(a,cl,price=7)[0];f=fill(a,clock(cl).earliest_execution_at,price=7);assert f.shares>1000;assert not a.leg.controller.close(V=D(f.shares)*D(14),known=True,at='rally')
run('cheaper_restore_can_buy_more_without_external_money_then_rally',lower_growth)
def fresh_and_same_day():
 a,op=start();assert not restore(a,op-timedelta(seconds=1))[0];cl=op+timedelta(hours=6);assert not restore(a,cl,fresh=False)[0];assert restore(a,cl)[0];assert fill(a,cl) is None;assert fill(a,clock(cl).earliest_execution_at)
run('fully_sold_open_fresh_close_next_legal_buy_no_stale_signal',fresh_and_same_day)
def insufficient():
 a,op=start(q=100,K=D(1005));assert not restore(a,op+timedelta(hours=6))[0] and not a.buys
run('fresh_signal_insufficient_minimum_lot_no_injection',insufficient)
def partial():
 a,op=start();cl=op+timedelta(hours=6);restore(a,cl);bt=clock(cl).earliest_execution_at;f=fill(a,bt,capacity=100);n=a.leg.number;K=a.leg.K;f2=fill(a,bt+timedelta(hours=1),capacity=100);assert a.leg.number==n and a.leg.K==K+f2.gross_cny+f2.fees_cny;assert not restore(a,bt+timedelta(hours=6))[0]
run('partial_buy_adds_actual_cost_same_leg_no_false_flat',partial)
def delay_expiry():
 a,op=start();a.delay_events=1;cl=op+timedelta(hours=6);restore(a,cl);bt=clock(cl).earliest_execution_at;assert fill(a,bt) is None;a.expire_day_buys(bt+timedelta(hours=6));assert not restore(a,bt+timedelta(hours=6),fresh=False)[0];assert not a.buys
run('real_delayed_unfilled_order_expires_without_fresh_no_revival',delay_expiry)
def original_priority():
 a,op=start();cl=op+timedelta(hours=6);restore(a,cl);a.ended=True;a.cancel_buy('A');assert not a.buys and not restore(a,cl+timedelta(days=1))[0]
run('original_end_cancels_buy_and_no_cross_structure_restore',original_priority)
save(O/'STATE_TESTS.json',dict(passed=True,tests=res,original_ledger=True,economic_replay=False));print('PASS',len(res))
