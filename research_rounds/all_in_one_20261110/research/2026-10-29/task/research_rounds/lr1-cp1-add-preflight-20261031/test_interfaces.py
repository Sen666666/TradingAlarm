"""Actual frozen LR/BP/Decimal-ledger tests; no price history/economic replay."""
from pathlib import Path
import importlib.util,sys,unittest,json,time,hashlib
from types import SimpleNamespace
from dataclasses import replace
from datetime import timedelta
from decimal import Decimal as D
O=Path(__file__).resolve().parent
RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
sys.path[:0]=[str(RR/'lot-risk-allocation-20261029/code'),str(RR/'probe-pyramid-pilot-20261029/code')]
import study as LR
import test_study as OLD
import test_sector_account as F
BP=LR.BP

def acc():
 return LR.Account('P1',SimpleNamespace(protocol={'fractional_split_policy':'floor_position_fraction_writeoff'}),SimpleNamespace(factor=lambda sid,at:D(1)))

def item(kind='core',q=None,clock=None):
 return dict(sid='A',quote=q or F.quote(),floor=D(5),kind=kind,clock=clock or F.CLOCK,
             weight=10 if kind=='add' else 1,group=0 if kind=='add' else 1,score=60,
             epoch=(0,1),reason='CP1_confirmation' if kind=='add' else 'I_early_probe',
             cap=300,budget=D(3000),risk_budget=D(2500))

def buy(a,i,q=100,at=None,eid='fill',capacity=10**8):
 at=at or i['clock'].earliest_execution_at
 a.reserve_quantity(i,q,D(10),F.FREE,at)
 return a.fill_buy('A',F.window(at=at,eid=eid,capacity=capacity,price=10,cash_due_at=at))

class Interfaces(unittest.TestCase):
 def test_actual_partial_fill_updates_last_buy_and_cancel_does_not_erase_core_lock(self):
  a=acc();i=item();f=buy(a,i,300,capacity=100);self.assertEqual(f.shares,100)
  self.assertEqual(a.last_buy['A'],D(10));self.assertEqual(a.core_epoch['A'],(0,1))
  a.cancel_buy('A');self.assertEqual(a.quantity('A'),100);self.assertEqual(a.last_buy['A'],D(10));a.check()
 def test_actual_add_exit_keeps_core(self):
  a=acc();buy(a,item());t=F.T+timedelta(days=3)
  c=F.admission.Clock(t,t+timedelta(days=1),t.date());i=item('add',clock=c)
  buy(a,i,at=c.earliest_execution_at,eid='add');t+=timedelta(days=3)
  c=F.admission.Clock(t,t+timedelta(days=1),t.date());a.sell('A',c,F.quote(),[2],'CP1_add_protection')
  r=a.fill_exit('A',F.window(at=c.earliest_execution_at,eid='sell',cash_due_at=c.earliest_execution_at))
  self.assertEqual(r.shares,100);self.assertEqual(a.quantity('A'),100);self.assertEqual(a.layers[0]['qty'],100);a.check()
 def test_full_exit_overrides_add_request_and_cancels_buy(self):
  a=acc();buy(a,item());t=F.T+timedelta(days=3);c=F.admission.Clock(t,t+timedelta(days=1),t.date())
  buy(a,item('add',clock=c),at=c.earliest_execution_at,eid='add')
  t+=timedelta(days=3);c=F.admission.Clock(t,t+timedelta(days=1),t.date())
  a.sell('A',c,F.quote(),[2],'CP1_add_protection');a.sell('A',c,F.quote(),[1,2],'ACT_pause')
  self.assertIsNone(a.exits['A'].remaining_target)
  r=a.fill_exit('A',F.window(at=c.earliest_execution_at,eid='all',cash_due_at=c.earliest_execution_at))
  self.assertEqual(r.shares,200);self.assertNotIn('A',a.last_buy);self.assertEqual(a.core_epoch['A'],(0,1));a.check()
 def test_split_dividend_conserve_layer_shares_without_new_buy(self):
  a=acc();buy(a,item());t=F.T+timedelta(days=3);c=F.admission.Clock(t,t+timedelta(days=1),t.date());buy(a,item('add',clock=c),at=c.earliest_execution_at,eid='add')
  t+=timedelta(days=3);before=a.last_buy['A'];n=len(a.trades)
  a.split(event_id='split',sid='A',ratio=D('1.3'),at=t,new_shares_sellable_at=t)
  a.accrue_dividend(event_id='d',sid='A',currency='CNY',net_local=D(20),ex_at=t,paid_at=None,source_id='synthetic',entitlement_basis='actual')
  self.assertEqual(a.quantity('A'),260);self.assertEqual(sum(z['qty'] for z in a.layers),260)
  self.assertEqual(sum(z['dividend'] for z in a.layers),20);self.assertEqual(a.last_buy['A'],before);self.assertEqual(len(a.trades),n);a.check()
 def test_native_order_event_deduplication(self):
  a=acc();i=item();a.reserve_quantity(i,300,D(10),F.FREE,F.CLOCK.earliest_execution_at)
  w=F.window(capacity=100);r=a.fill_buy('A',w);self.assertEqual(r.shares,100)
  self.assertIsNone(a.fill_buy('A',w));self.assertEqual(a.quantity('A'),100);a.check()
 def test_legacy_lr_reservation_ignores_account_delay_reproduced(self):
  a=acc();a.delay_events=1;i=item();a.reserve_quantity(i,100,D(10),F.FREE,F.CLOCK.earliest_execution_at)
  self.assertEqual(a.buys['A'].delay_remaining,0)
  self.assertEqual(a.fill_buy('A',F.window()).shares,100)
 def test_native_one_session_held_add_loses_delay_credit(self):
  a=acc();buy(a,item());t=F.T+timedelta(days=3);c=F.admission.Clock(t,t+timedelta(days=1),t.date())
  a.delay_events=1;i=item('add',clock=c);a.reserve_quantity(i,100,D(10),F.FREE,c.earliest_execution_at)
  a.buys['A'].delay_remaining=1 # minimal proposed direct native stress adaptation, not a policy repair
  self.assertIsNone(a.fill_buy('A',F.window(at=c.earliest_execution_at,eid='delay-add')))
  self.assertEqual(a.buys['A'].delay_remaining,0)
  a.expire_day_buys(c.earliest_execution_at+timedelta(hours=6))
  self.assertNotIn('A',a.buys);self.assertNotIn('A',a.daily_delay_credit);self.assertEqual(a.quantity('A'),100);a.check()
 def test_native_one_session_flat_order_gets_credit(self):
  a=acc();a.delay_events=1;i=item();a.reserve_quantity(i,100,D(10),F.FREE,F.CLOCK.earliest_execution_at)
  a.buys['A'].delay_remaining=1
  self.assertIsNone(a.fill_buy('A',F.window()))
  a.expire_day_buys(F.CLOCK.earliest_execution_at+timedelta(hours=6))
  self.assertIn('A',a.daily_delay_credit);self.assertEqual(a.quantity('A'),0);a.check()

if __name__=='__main__':
 t=time.monotonic();suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Interfaces),unittest.defaultTestLoader.loadTestsFromTestCase(OLD.Tests)])
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 report=dict(passed=result.wasSuccessful(),test_methods=result.testsRun,failures=[x[0].id() for x in result.failures],errors=[x[0].id() for x in result.errors],seconds=time.monotonic()-t,
             actual_old_BPLR_and_native_ledger=True,economic_paths_started=0,
             findings=['LR reservation hardcodes delay0','native expiry credit excludes held ADD','role risk_restore patch is not automatically CP1_ADD policy'])
 (O/'TEST_RESULTS.json').write_text(json.dumps(report,indent=2))
 sys.exit(0 if result.wasSuccessful() else 1)
