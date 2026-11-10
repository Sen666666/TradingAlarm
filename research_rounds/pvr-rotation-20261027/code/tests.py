from study import *
import unittest
fixture=C.import_path('pvr_rotation_contract_fixture',P.BASE/'code/test_contracts.py')

class RotationTests(unittest.TestCase):
 def test_bound_account_risk_is_ACT20(self):self.assertEqual(Runner.run_tech.__globals__['RISK_MODE'],'ACT20_BREAK')
 def pair(self,newscore=80,oldscore=60,new_sector='G0',event=True):
  r,a,T,clock,stocks,sectors=fixture.Contracts().setup_rotation(new_sector=new_sector,event=event)
  a.__class__=Account;r.__class__=Runner;a.rotation_enabled=True;a.paired_bps=None;a.risk_state={'on':True};a.market.actions={}
  stocks=tuple(replace(s,rank=E.admission.Rank(newscore if s.security_id=='N' else oldscore if s.security_id=='S0' else 90,T,T)) for s in stocks)
  r.start_pair(a,T,clock,stocks,sectors)
  a.market.window=lambda sid,at,side,m:fixture.window(sid=sid,at=at,cash_due_at=at,eid=f'{sid}:{at}:{side}')
  return r,a,T,clock
 def test_exact_gap_inclusive(self):
  r,a,_,_=self.pair(75,60);self.assertEqual(a.swap['victim'],'S0');self.assertEqual(a.swap['score_gap'],15)
 def test_gap_too_small(self):self.assertIsNone(self.pair(74.999,60)[1].swap)
 def test_positive_evidence_required(self):self.assertIsNone(self.pair(50,20)[1].swap)
 def test_no_new_event(self):self.assertIsNone(self.pair(event=False)[1].swap)
 def test_cannot_release_fourth_industry(self):self.assertIsNone(self.pair(new_sector='G3')[1].swap)
 def test_unknown_score_cannot_victimize(self):self.assertIsNone(choose(90,{'a':None,'b':float('nan')}))
 def test_tie_is_deterministic(self):self.assertEqual(choose(80,{'z':60,'a':60}),'a')
 def test_preflight_rejects_gap_below_support_before_sale(self):
  r,a,T,c=self.pair();a.market.window=lambda sid,at,side,m:fixture.window(sid=sid,at=at,price=8 if sid=='N' else 10,cash_due_at=at)
  r.preflight(a,c.earliest_execution_at);self.assertFalse(r.allow_sale(a,'S0'));self.assertEqual(a.quantity('S0'),10000)
 def test_preflight_requires_full_sale_capacity(self):
  r,a,T,c=self.pair();a.market.window=lambda sid,at,side,m:fixture.window(sid=sid,at=at,capacity=100 if sid=='S0' else 100000,cash_due_at=at)
  r.preflight(a,c.earliest_execution_at);self.assertFalse(r.allow_sale(a,'S0'))
 def test_preflight_keeps_structure_exit_priority(self):
  r,a,T,c=self.pair();a.market.window=lambda *args:None;a.normal_exits={'S0'};a.request_exit(a.market.quote('S0',T),c)
  r.preflight(a,c.earliest_execution_at);self.assertTrue(r.allow_sale(a,'S0'))
 def test_sale_then_buy_uses_real_cash_and_frozen_origin(self):
  r,a,T,c=self.pair();S=c.earliest_execution_at;a.available=ZERO;r.preflight(a,S);self.assertTrue(r.allow_sale(a,'S0'))
  self.assertIsNotNone(a.fill_exit('S0',a.market.window('S0',S,'sell',1)));a.settle_due(S);r.after_sales(a,S)
  o=a.buys['N'];self.assertEqual(a.intents[o.order_id]['decision_at'],T);self.assertLessEqual(o.budget_cny,a.available+o.budget_cny)
  self.assertIsNone(a.fill_buy('N',a.market.window('N',S,'buy',1)));r.after_buys(a,S);self.assertGreater(a.quantity('N'),0);self.assertGreaterEqual(a.available,ZERO);self.assertEqual(a.fills[-1].at,S+timedelta(seconds=1))
 def test_each_leg_consumes_own_delay_once(self):
  r,a,T,c=self.pair();S=c.earliest_execution_at;a.delay_events=1;a.exits['S0'].delay_remaining=1
  self.assertIsNone(a.fill_exit('S0',a.market.window('S0',S,'sell',1)));S+=timedelta(days=1)
  self.assertIsNotNone(a.fill_exit('S0',a.market.window('S0',S,'sell',1)));a.settle_due(S);r.after_sales(a,S);r.after_buys(a,S);self.assertEqual(a.quantity('N'),0)
  r.after_buys(a,S+timedelta(days=1));self.assertGreater(a.quantity('N'),0)
 def test_no_sale_never_funds_pair(self):
  r,a,T,c=self.pair();r.after_sales(a,c.earliest_execution_at);self.assertNotIn('N',a.buys)
 def test_sell_timeout_releases_only_rotation_exit(self):
  r,a,T,c=self.pair();r.valid_intent=lambda *x:True;at=T+timedelta(days=2);r.close_pair(a,at,c);self.assertIsNone(a.swap);self.assertNotIn('S0',a.exits)
 def test_account_pause_cancels_pair(self):
  r,a,T,c=self.pair();a.risk_state['on']=False;r.close_pair(a,T,c);self.assertIsNone(a.swap);self.assertNotIn('N',a.buys)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(RotationTests))
 if result.wasSuccessful():save(O/'synthetic.json',{'passed':True,'tests':result.testsRun,'real_cash_share_ledger':True})
 else:sys.exit(1)
