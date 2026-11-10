"""Synthetic native ledger callback tests. Altered capacity, not historical economic paths."""
from dataclasses import replace
from decimal import Decimal as D
from datetime import timedelta
import copy,json,traceback
import inputs as I
import conditional_engine as E
J=I.J

def new(data,case,arm):
 args=I.single(data,case['sid']);r=E.Runner(*args,case,arm);r.warm(data['calendar']);E.seed_plan(r);return r

def main():
 data=I.load();c=data['cases'][0];tests={};details=[]
 for arm in E.ARMS:
  r=new(data,c,arm);a=r.account;i=a.pending[0];at=i['clock'].earliest_execution_at;m=r.market;m.set_phase(at,'OPEN');nativewindow=m.window
  def synthetic_window(sid,t,side,cost):
   w=nativewindow(sid,t,side,cost)
   return replace(w,capacity_shares=37,event_id=w.event_id+':SYNTHETIC37')if w else None
  m.window=synthetic_window;r.opening(a,at)
  assert a.quantity(r.sid)==37 and r.sid in a.buys
  w=synthetic_window(r.sid,at,'buy',1);w=replace(w,event_id=w.event_id+':SECOND37')
  a.fill_buy(r.sid,w)
  assert a.quantity(r.sid)==74 and len(a.layers)==2 and len(r.profit_events)==1
  assert all(x['kind']==('probe_mobile'if arm==E.ARMS[1]else'add')for x in a.layers)
  assert a.core_epoch==({r.sid:tuple(c['seed_core_epoch'])}if c['seed_core_epoch']is not None else {})
  assert all(x['floor']==i['I_floor']if arm==E.ARMS[1]else x['floor']==i['guard_floor']for x in a.layers)
  book=r.cost_book.sync(a);before=book.cost;qty=book.qty
  x=dict(known_open=D('1'),price=D('1.0005'),schedule=w.fees)
  assert not r.profit_permission(a,dict(i,kind='add'),x,at)
  assert a.quantity(r.sid)==qty and not a.exits
  # Native cancellation acknowledgement; no old ticket gets revived.
  a.cancel_buy(r.sid);assert not a.buys and all(o.status not in ('open','cancel_pending')for o in a.budget.orders.values())
  # Apply a synthetic split through original ledger callback, not a hand-edited quantity.
  actionat=at+timedelta(minutes=1);m.set_phase(actionat,'ACTION');a.split(event_id='SYNTHETIC_SPLIT2',sid=r.sid,ratio=D(2),at=actionat,new_shares_sellable_at=w.sellable_at);r.cost_book.sync(a)
  assert a.quantity(r.sid)==qty*2 and book.cost==before and all(x['kind']==('probe_mobile'if arm==E.ARMS[1]else'add')for x in a.layers)
  # Dividend doesn't reduce remaining cost. The native entitlement is explicit.
  a.accrue_dividend(event_id='SYNTHETIC_DIVIDEND',sid=r.sid,currency='CNY',net_local=D(8),ex_at=actionat,paid_at=None,source_id='synthetic',entitlement_basis='synthetic_previous_inventory');r.cost_book.sync(a);assert book.cost==before
  # Same-day sale remains barred by original sellable clock.
  t=actionat+timedelta(minutes=1);clock=replace(i['clock'],decision_at=actionat,earliest_execution_at=t);a.sell(r.sid,clock,i['quote'],[z['id']for z in a.live(r.sid)],'SYNTHETIC_EXIT');m.set_phase(t,'OPEN')
  sellw=replace(w,event_id=w.event_id+':SYNTHETIC_SELL_T0',at=t,cash_due_at=t,raw_open=D(10),execution_price=D('9.995'),capacity_shares=99999)
  n=len(a.trades);a.fill_exit(r.sid,sellw);assert len(a.trades)==n and r.sid in a.exits
  # Pending exit wins over any new buy intent in native OPEN ordering.
  a.pending=[dict(i,clock=replace(i['clock'],earliest_execution_at=t))];m.window=lambda sid,t,side,cost:None
  r.opening(a,t);assert not a.buys and r.sid in a.exits and len(a.trades)==n
  details.append(dict(arm=arm,synthetic_partial_fills=2,first_fill=37,second_fill=37,post_split_qty=a.quantity(r.sid),remaining_cost=book.cost,core_epoch=a.core_epoch,profit_event_count=len(r.profit_events),pending_exit=True))
 # Real missing window checked only as read-only proxy availability: no position/fill.
 jc=next(z for z in data['cases']if z['round_id']==2897);r=new(data,jc,E.ARMS[1]);missing=[]
 for day in ['2026-01-30','2026-02-02','2026-02-03','2026-02-04','2026-02-05']:
  at=J.M.N.iso(day+'T09:30:00+08:00');r.market.set_phase(at,'OPEN');assert r.market.window(r.sid,at,'sell',1)is None;missing.append(day)
 tests.update(native_partial_order_identity=True,probe_does_not_consume_CORE=True,CP_guard_and_I_responsibility_separate=True,partial_remaining_not_retested_as_ADD=True,loss_blocks_ADD_not_holding=True,native_cancel_ack=True,native_split_and_dividend_cost_bridge=True,native_T1_prevents_same_day_sell=True,pending_exit_blocks_new_buy=True,Jiangfeng_missing_OPEN_UNKNOWN=missing,economic_paths=0,synthetic_capacities_only=True)
 # Refresh audited derived source and freeze after the reviewed profit migration correction.
 I.save('NATIVE_DIFF_FINAL_REVIEW.json',E.DIFFS);I.save('SOURCE_FREEZE_FINAL_REVIEW.json',I.SOURCES);I.save('SYNTHETIC_CALLBACK_TESTS.json',dict(passed=True,tests=tests,details=details,real_orders=False,historical_economic_paths=0))
 print('SYNTHETIC_CALLBACKS_PASS')
if __name__=='__main__':
 try:main()
 except BaseException:
  (I.O/('SYNTHETIC_FAILURE_'+str(__import__('time').time_ns())+'.txt')).write_text(traceback.format_exc());raise
