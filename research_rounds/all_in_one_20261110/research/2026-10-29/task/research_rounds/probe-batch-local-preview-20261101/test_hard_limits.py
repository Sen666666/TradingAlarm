"""Direct original hard-limit regression checks on the same planning functions."""
import unittest,json,copy,ast,inspect,textwrap
import planner as P
from test_planner import state,item,assign,AT

class HardLimits(unittest.TestCase):
 def test_probe_capital_still_blocks(self):
    old=P.N.Lot('old','OLD','T','E-T','probe',1000,100,99.99,attempt='A-T')
    s=state({'S':0,'T':0},cash=900000,lots=[old],prices={'OLD':100});i=item('X','S');assign(s,[i],{'X':'S'});r=P.plan(s,[i],AT);self.assertFalse(r['orders']);self.assertIn('pool_capital',str(r['rejected']))
 def test_sector_total_across_old_attempts_and_pools_still_blocks(self):
    old=P.N.Lot('old','OLD','S','OLD','confirmed',100,190,194.9,attempt='old-attempt')
    s=state({'S':0},cash=980500,lots=[old],prices={'OLD':195});i=item('X','S');assign(s,[i],{'X':'S'});r=P.plan(s,[i],AT);self.assertFalse(r['orders']);self.assertIn('sector_capital',str(r['rejected']))
 def test_sector_risk_still_blocks(self):
    old=P.N.Lot('old','OLD','S','OLD','confirmed',1000,90,80,attempt='old-attempt')
    s=state({'S':2},cash=900000,lots=[old],prices={'OLD':100});i=item('X','S');assign(s,[i],{'X':'S'});r=P.plan(s,[i],AT);self.assertFalse(r['orders']);self.assertIn('sector_risk',str(r['rejected']))
 def test_stock_cap_still_blocks_overnight_passive_overweight(self):
    old=P.N.Lot('old','X','S','OLD','confirmed',10000,10,14.99,attempt='old-attempt')
    s=state({'S':2},cash=850000,lots=[old],prices={'X':15});i=item('X','S',p='15',floor='14.9');assign(s,[i],{'X':'S'});r=P.plan(s,[i],AT);self.assertFalse(r['orders']);self.assertIn('stock_capital',str(r['rejected']))
 def test_original_cash_reserve_and_unpaid_AR_not_spendable(self):
    s=state(cash=50000,receivables=950000);i=item('X','S');assign(s,[i],{'X':'S'});r=P.plan(s,[i],AT);self.assertFalse(r['orders']);self.assertIn('cash_or_original_reserve',str(r['rejected']))
 def test_confirmed_cannot_borrow_overrisk_probe(self):
    lots=[P.N.Lot('conf','OLD','T','OLD','confirmed',6000,99,99.99,attempt='old'),P.N.Lot('probe','P','U','OLD','probe',500,20,8,attempt='old')]
    s=state({'S':2,'T':1,'U':0},cash=390000,lots=lots,prices={'OLD':100,'P':20});i=item('X','S');assign(s,[i],{'X':'S'});r=P.plan(s,[i],AT);self.assertFalse(r['orders']);self.assertIn('pool_capital',str(r['rejected']));self.assertIn('probe_risk',str(r['rejected']))
 def test_Bdiag_does_not_silently_reintroduce_account_three_percent(self):
    lots=[P.N.Lot(str(k),'O'+str(k),'T'+str(k),'OLD','confirmed',1000,18,14,attempt='old') for k in range(4)]
    prices={'O'+str(k):20 for k in range(4)};s=state({'S':2,**{'T'+str(k):1 for k in range(4)}},cash=920000,lots=lots,prices=prices);i=item('X','S',p='10',floor='5',target=2000);assign(s,[i],{'X':'S'});r=P.plan(s,[i],AT);self.assertTrue(r['orders']);self.assertGreater(r['nominal_risk'],.03*s.nav)
 def test_unused_sector_status_is_not_an_admission_input(self):
    for fn in [P.N.Contract.migrate,P.N.Contract.valid,P.N.Contract.request]:
        tree=ast.parse(textwrap.dedent(inspect.getsource(fn)))
        reads=[n for n in ast.walk(tree) if isinstance(n,ast.Attribute) and n.attr=='status' and isinstance(n.ctx,ast.Load) and isinstance(n.value,ast.Name) and n.value.id=='s']
        self.assertFalse(reads,fn.__name__)
    s=state({'S':1});i=item('X','S',target=1000);assign(s,[i],{'X':'S'});a=P.plan(s,[i],AT)
    s.sectors['S'].status=None;b=P.plan(s,[i],AT);self.assertEqual(a['orders'],b['orders']);self.assertEqual(a['nominal_risk'],b['nominal_risk'])

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(HardLimits);r=unittest.TextTestRunner(verbosity=2).run(suite)
    (P.O/'HARD_LIMIT_RESULTS.json').write_text(json.dumps(dict(tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),passed=r.wasSuccessful(),scope='same pure planning functions, original Bdiag checks and explicit unused-field read-set proof'),indent=2)+'\n')
    raise SystemExit(not r.wasSuccessful())
