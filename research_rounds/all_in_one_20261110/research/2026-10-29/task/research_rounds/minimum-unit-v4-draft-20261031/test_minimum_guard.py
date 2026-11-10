"""Hand-written synthetic minimum-gate expectations; no market/history."""
import json,unittest
from pathlib import Path
from minimum_guard import View,Holding,Pending,check,D

def hold(stock='OLD',sector='OTHER',pool='confirmed',qty=100,mark='100',floor='99',role='core',sell=False):
 return Holding(stock,sector,pool,qty,D(mark),D(floor),role,sell)
class Tests(unittest.TestCase):
 def test_100_original_target_feasible(self):self.assertTrue(check(View(),price=D(190),floor=D(189))['accepted'])
 def test_200_original_target_feasible(self):self.assertTrue(check(View(),unit=200,price=D(90),floor=D(89))['accepted'])
 def test_probe_target_exception_cannot_cross_same_two_percent_hard_limit(self):
  r=check(View(),price=D(300),floor=D(299),allow_target_exception=True)
  self.assertFalse(r['accepted']);self.assertIn('sector_capital',r['hard_reasons']['probe'])
 def test_confirmed_target_only_pending_and_hypothetical_one_unit(self):
  r=check(View(),level=1,price=D(300),floor=D(299));self.assertEqual(r['reason'],'target_exception_policy_not_frozen')
  r=check(View(),level=1,price=D(300),floor=D(299),allow_target_exception=True)
  self.assertTrue(r['accepted']);self.assertEqual((r['quantity'],r['pool']),(100,'confirmed'))
 def test_all_sector_roles_share_capital(self):
  for role in ('core','mobile'):
   v=View(holdings=[hold(sector='S',pool='confirmed',qty=110,mark='100',role=role)])
   r=check(v,price=D(100),floor=D(99));self.assertFalse(r['accepted']);self.assertIn('sector_capital',r['hard_reasons']['probe'])
 def test_cancel_pending_not_released_then_real_ack(self):
  v=View(orders=[Pending('OLD','S','probe',100,D(150),D(149),D(0))]);v.cancel('OLD')
  self.assertFalse(check(v,price=D(100),floor=D(99))['accepted']);before=v.available;v.cancel_ack('OLD')
  self.assertGreater(v.available,before);self.assertTrue(check(v,price=D(100),floor=D(99),receipt='fresh2')['accepted'])
 def test_pending_sell_still_counts(self):
  v=View(holdings=[hold(sector='S',pool='probe',qty=100,mark='150',sell=True)])
  self.assertFalse(check(v,price=D(100),floor=D(99))['accepted']);v.acknowledged_full_clear('OLD')
  self.assertTrue(check(v,price=D(100),floor=D(99),receipt='new-after-real-clear')['accepted'])
 def test_fee_moves_exact_nominal_boundary(self):
  v=View(holdings=[hold(sector='S',qty=700,mark='100',floor='99.99')])
  self.assertTrue(check(v,level=1,price=D(300),floor=D(299),allow_target_exception=True)['accepted'])
  r=check(v,level=1,price=D(300),floor=D(299),fee=D(5),allow_target_exception=True)
  self.assertFalse(r['accepted']);self.assertIn('sector_capital',r['hard_reasons']['confirmed'])
 def test_gap_rechecked_not_fill_at_old_quote(self):
  v=View(holdings=[hold(sector='S',qty=700,mark='100',floor='99.99')])
  self.assertTrue(check(v,level=1,price=D(300),floor=D(299),allow_target_exception=True)['accepted'])
  self.assertFalse(check(v,level=1,price=D(400),floor=D(299),allow_target_exception=True)['accepted'])
 def test_two_sectors_serial_reserve_shared_pool(self):
  v=View(holdings=[hold(stock='L'+str(i),sector='O'+str(i),pool='probe',qty=100,mark='196',floor='195.9') for i in range(5)])
  self.assertTrue(check(v,stock='A',sector='S',price=D(15),floor=D('14.9'),reserve=True)['accepted'])
  self.assertFalse(check(v,stock='B',sector='T',price=D(15),floor=D('14.9'),receipt='other',reserve=True)['accepted'])
  self.assertEqual(len(v.orders),1)
 def test_too_large_single_unit_rejected(self):
  r=check(View(),level=2,price=D(7000),floor=D(6999),allow_target_exception=True)
  self.assertFalse(r['accepted']);self.assertIn('stock_capital',r['hard_reasons']['confirmed']);self.assertIn('pool_capital',r['hard_reasons']['confirmed'])
 def test_exactly_filling_shared_pool_is_original_hard_resource_legal(self):
  v=View(holdings=[hold(qty=5790,mark='100',floor='99.99')])
  r=check(v,level=1,price=D(210),floor=D(209),allow_target_exception=True)
  self.assertTrue(r['accepted']);self.assertEqual(r['hard_reasons']['confirmed'],[]);self.assertEqual(r['policy_reasons'],[])
  pending=check(v,level=1,price=D(210),floor=D(209))
  self.assertTrue(pending['minimum_hard_capacity_feasible']);self.assertEqual(pending['hard_reasons']['confirmed'],[])
  self.assertFalse(pending['accepted']);self.assertEqual(pending['policy_reasons'],['target_exception_policy_not_frozen'])
  fee_cross=check(v,level=1,price=D(210),floor=D(209),fee=D(5),allow_target_exception=True)
  self.assertFalse(fee_cross['accepted']);self.assertIn('pool_capital',fee_cross['hard_reasons']['confirmed'])
 def test_passive_growth_not_forced_sold_but_no_repeat_exception(self):
  v=View(holdings=[hold(stock='A',sector='S',qty=100,mark='500',floor='499')]);before=v.holdings[0].qty
  r=check(v,level=1,price=D(300),floor=D(299),allow_target_exception=True)
  self.assertEqual(r['reason'],'exception_requires_actual_flat');self.assertEqual(v.holdings[0].qty,before)
 def test_old_receipt_not_reused_across_pool_alias(self):
  v=View();self.assertTrue(check(v,receipt='canonical',reserve=True)['accepted'])
  v.cancel('A');v.cancel_ack('A')
  self.assertEqual(check(v,level=1,receipt='canonical')['reason'],'old_or_consumed_receipt')
 def test_actual_clear_and_truly_fresh_reentry(self):
  v=View();self.assertTrue(check(v,level=1,price=D(300),floor=D(299),allow_target_exception=True,reserve=True)['accepted'])
  v.acknowledged_fill('A');v.acknowledged_full_clear('A')
  self.assertFalse(check(v,level=1,price=D(300),floor=D(299),receipt='new',allow_target_exception=True)['accepted'])
  self.assertTrue(check(v,level=1,price=D(300),floor=D(299),receipt='genuinely-new',allow_target_exception=True)['accepted'])
 def test_probe_risk_retained(self):
  v=View(holdings=[hold(pool='probe',qty=1000,mark='10',floor='5.1')]);r=check(v,price=D(10),floor=D(8))
  self.assertFalse(r['accepted']);self.assertIn('probe_risk',r['hard_reasons']['probe'])
 def test_sector_risk_retained(self):
  v=View(holdings=[hold(sector='S',qty=100,mark='100',floor='1')]);r=check(v,level=1,price=D(100),floor=D(98))
  self.assertFalse(r['accepted']);self.assertIn('sector_risk',r['hard_reasons']['confirmed'])
 def test_account_risk_retained_in_v4_draft(self):
  v=View(holdings=[hold(qty=1000,mark='40',floor='10.1')]);r=check(v,level=1,price=D(10),floor=D(8))
  self.assertFalse(r['accepted']);self.assertIn('account_risk',r['hard_reasons']['confirmed'])
 def test_noncash_equity_cannot_be_spent_or_break_reserve(self):
  v=View(noncash_equity=D(899500));r=check(v,level=1,price=D(10),floor=D(9),fee=D(5))
  self.assertFalse(r['accepted']);self.assertIn('cash_and_original_reserve',r['hard_reasons']['confirmed'])
 def test_pending_same_stock_not_flat_exception(self):
  v=View(orders=[Pending('A','S','probe',100,D(10),D(9),D(0),'cancel_pending')])
  self.assertEqual(check(v,level=1,price=D(300),floor=D(299),allow_target_exception=True)['reason'],'existing_order_responsibility')
 def test_unknown_and_original_permission(self):
  self.assertEqual(check(View(),floor=None)['reason'],'unknown_price_or_floor')
  self.assertFalse(check(View(),Q=None)['accepted']);self.assertFalse(check(View(),ACT=False)['accepted'])
 def test_above_market_floor_does_not_mean_free_risk(self):self.assertEqual(check(View(),price=D(100),floor=D(101))['reason'],'invalid_price_or_protection')

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Tests);r=unittest.TextTestRunner(verbosity=2).run(suite)
 Path(__file__).with_name('SYNTHETIC_RESULTS.json').write_text(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful(),scope='minimum-gate pure fixture, no sizing/ledger integration or history',exception_default=False,new_numeric_exception_cap_not_selected=True),indent=2)+'\n')
 raise SystemExit(not r.wasSuccessful())
