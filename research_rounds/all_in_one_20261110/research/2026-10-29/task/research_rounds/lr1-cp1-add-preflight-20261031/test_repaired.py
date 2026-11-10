from test_interfaces import *
import adapter as M

class Repaired(unittest.TestCase):
 def setUp(self):M.CURRENT['cost']=1;LR.SLIP=D('.0005')
 def a(self):return M.Account('ADD_delay1',SimpleNamespace(protocol={'fractional_split_policy':'floor_position_fraction_writeoff'}),SimpleNamespace(factor=lambda sid,at:D(1)),True)
 def initial(self):
  a=self.a();buy(a,item());a.delay_events=1;return a
 def waiting(self):
  a=self.initial();t=F.T+timedelta(days=3);c=F.admission.Clock(t,t+timedelta(days=1),t.date());i=item('add',clock=c)
  a.use_cp(i);a.reserve_quantity(i,100,D(10),F.FREE,c.earliest_execution_at)
  self.assertEqual(a.buys['A'].delay_remaining,1)
  self.assertIsNone(a.fill_buy('A',F.window(at=c.earliest_execution_at,eid='wait')))
  close=c.earliest_execution_at+timedelta(hours=6);a.expire_day_buys(close)
  self.assertIn('A',a.add_credits);return a,i,close
 def new(self,at):return item('add',clock=F.admission.Clock(at,at+timedelta(hours=18),at.date()))
 def test_new_cp_same_cutoff_carries_wait_once(self):
  a,i,at=self.waiting();n=self.new(at);a.use_cp(n);a.reserve_quantity(n,100,D(10),F.FREE,n['clock'].earliest_execution_at)
  self.assertEqual(a.buys['A'].delay_remaining,0);self.assertNotIn('A',a.add_credits)
  f=a.fill_buy('A',F.window(at=n['clock'].earliest_execution_at,eid='afterwait'));self.assertEqual(f.shares,100)
  t=n['clock'].earliest_execution_at+timedelta(hours=6);a.expire_day_buys(t)
  n2=self.new(t);a.use_cp(n2);a.reserve_quantity(n2,100,D(10),F.FREE,n2['clock'].earliest_execution_at)
  self.assertEqual(a.buys['A'].delay_remaining,1)
 def test_old_cp_cannot_be_reused(self):
  a,i,at=self.waiting()
  with self.assertRaises(AssertionError):a.use_cp(i)
 def test_spent_credit_unfilled_order_cannot_roll_credit_again(self):
  a,i,at=self.waiting();n=self.new(at);a.use_cp(n);a.reserve_quantity(n,100,D(10),F.FREE,n['clock'].earliest_execution_at)
  self.assertEqual(a.buys['A'].delay_remaining,0)
  self.assertIsNone(a.fill_buy('A',F.window(at=n['clock'].earliest_execution_at,eid='not-buyable',buy_allowed=False)))
  a.expire_day_buys(n['clock'].earliest_execution_at+timedelta(hours=6))
  self.assertFalse(a.add_credits)
 def test_no_new_signal_leaves_cash_no_forced_buy(self):
  a,i,at=self.waiting();qty=a.quantity('A');a.expire_day_buys(at+timedelta(days=1))
  self.assertFalse(a.add_credits);self.assertFalse(a.buys);self.assertEqual(a.quantity('A'),qty)
 def test_expired_credit_does_not_transfer_to_next_cutoff(self):
  a,i,at=self.waiting();n=self.new(at+timedelta(days=1));a.use_cp(n);a.reserve_quantity(n,100,D(10),F.FREE,n['clock'].earliest_execution_at)
  self.assertEqual(a.buys['A'].delay_remaining,1)
 def test_structure_or_role_mismatch_has_no_credit(self):
  a,i,at=self.waiting();n=self.new(at);n['epoch']=(0,2)
  # Original P1 ADD admission is not newly filtered by the old core's epoch.
  # Only waiting credit is scoped; the newly accepted order must still wait.
  self.assertTrue(a.add_valid('A',at,n['epoch']));a.use_cp(n);a.reserve_quantity(n,100,D(10),F.FREE,n['clock'].earliest_execution_at)
  self.assertEqual(a.buys['A'].delay_remaining,1)
  a.cancel_buy('A');n['kind']='core';n['epoch']=(0,1);a.reserve_quantity(n,100,D(10),F.FREE,n['clock'].earliest_execution_at)
  self.assertEqual(a.buys['A'].delay_remaining,1)
 def test_core_exit_clears_credit(self):
  a,i,at=self.waiting();c=F.admission.Clock(at,at+timedelta(hours=18),at.date());a.sell('A',c,F.quote(),[1],'ACT_pause')
  self.assertNotIn('A',a.add_credits);self.assertFalse(a.add_valid('A',at,(0,1)))
 def test_insufficient_cash_cannot_consume_credit(self):
  a,i,at=self.waiting();a.available=D(100);n=self.new(at);a.use_cp(n)
  with self.assertRaises(AssertionError):a.reserve_quantity(n,100,D(10),F.FREE,n['clock'].earliest_execution_at)
  self.assertFalse(a.buys);self.assertFalse(any(x['kind']=='ADD_credit_consumed' for x in a.ops))
 def test_partial_fill_expiry_has_no_zero_fill_credit(self):
  a=self.initial();a.delay_events=0;t=F.T+timedelta(days=3);i=self.new(t);a.use_cp(i);a.reserve_quantity(i,300,D(10),F.FREE,i['clock'].earliest_execution_at)
  f=a.fill_buy('A',F.window(at=i['clock'].earliest_execution_at,eid='partial',capacity=100));self.assertEqual(f.shares,100)
  a.delay_events=1;a.expire_day_buys(i['clock'].earliest_execution_at+timedelta(hours=6));self.assertFalse(a.add_credits)
 def test_normal_and_cost2_have_no_credit_adapter_effect(self):
  for cost in (1,2):
   a=self.a();a.cost_multiplier=cost;buy(a,item());self.assertEqual(a.buys.get('A'),None);self.assertFalse(a.add_credits);self.assertFalse(a.ops)

if __name__=='__main__':
 t=time.monotonic();suite=unittest.TestSuite([unittest.defaultTestLoader.loadTestsFromTestCase(Interfaces),unittest.defaultTestLoader.loadTestsFromTestCase(OLD.Tests),unittest.defaultTestLoader.loadTestsFromTestCase(Repaired)])
 result=unittest.TextTestRunner(verbosity=2).run(suite)
 M.save(M.O/'REPAIRED_TEST_RESULTS.json',dict(passed=result.wasSuccessful(),top_level_tests=result.testsRun,nested_old_BP_tests=10,seconds=time.monotonic()-t,failures=[x[0].id() for x in result.failures],errors=[x[0].id() for x in result.errors]))
 sys.exit(0 if result.wasSuccessful() else 1)
