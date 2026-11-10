from study import *
import study,unittest
from datetime import timedelta
fixture=P.C.import_path('correction_fixture',P.BASE/'code/test_contracts.py')
class Checks(unittest.TestCase):
 def pair(self,strategy='COR',new=True,weak=True,event=True,sector='G0',ns=80,os=60):
  r,a,T,clock,stocks,sectors=fixture.Contracts().setup_rotation(new_sector=sector,event=event);a.__class__=Account;r.__class__=Runner;a.mode=strategy+'0';a.rotation_enabled=True;a.paired_bps=None;a.risk_state={'on':True};a.market.actions={}
  a.fills[:]=[replace(f,at=f.at-timedelta(days=20)) for f in a.fills];a.market.sessions['A']=[T+timedelta(days=i) for i in range(-15,6)];study.FIRST=[];study.WEEKS={T.date().isoformat()};study.SIGNALS={s.security_id:pd.DataFrame(dict(new_ok=[new],weak=[weak]),index=[pd.Timestamp(T.date())]) for s in stocks}
  stocks=tuple(replace(s,rank=E.admission.Rank(ns if s.security_id=='N' else os if s.security_id=='S0' else 95,T,T)) for s in stocks)
  r.start_pair(a,T,clock,stocks,sectors);a.market.window=lambda sid,at,side,m:fixture.window(sid=sid,at=at,cash_due_at=at,eid=f'{sid}:{at}:{side}')
  return r,a,T,clock,stocks,sectors
 def test_correction_requires_both(self):
  self.assertIsNotNone(self.pair()[1].swap);self.assertIsNone(self.pair(new=False)[1].swap);self.assertIsNone(self.pair(weak=False)[1].swap)
 def test_buffer_control_ignores_absolute_weakness(self):self.assertIsNotNone(self.pair(strategy='BUF',new=False,weak=False)[1].swap)
 def test_ACT_has_no_rotation(self):self.assertIsNone(self.pair(strategy='ACT')[1].swap)
 def test_new_original_event_required(self):self.assertIsNone(self.pair(event=False)[1].swap)
 def test_industry_constraints_hold(self):self.assertIsNone(self.pair(sector='G3')[1].swap)
 def test_gap_boundaries(self):self.assertIsNotNone(self.pair(ns=70,os=60)[1].swap);self.assertIsNone(self.pair(ns=69.99,os=60)[1].swap);self.assertIsNone(self.pair(ns=49.9,os=20)[1].swap)
 def test_risk_policy_binding(self):self.assertEqual(Runner.run_tech.__globals__['RISK_MODE'],'ACT20_BREAK')
 def test_no_sale_no_buy(self):
  r,a,T,c,_,_=self.pair();r.after_sales(a,c.earliest_execution_at);self.assertNotIn('N',a.buys)
 def test_real_cash_pair(self):
  r,a,T,c,_,_=self.pair();S=c.earliest_execution_at;a.available=D(0);r.preflight(a,S);self.assertTrue(r.allow_sale(a,'S0'));self.assertIsNotNone(a.fill_exit('S0',a.market.window('S0',S,'sell',1)));a.settle_due(S);r.after_sales(a,S);r.after_buys(a,S);self.assertGreater(a.quantity('N'),0);self.assertGreaterEqual(a.available,0)
 def test_pair_delay_per_leg(self):
  r,a,T,c,_,_=self.pair();S=c.earliest_execution_at;a.delay_events=1;a.exits['S0'].delay_remaining=1;self.assertIsNone(a.fill_exit('S0',a.market.window('S0',S,'sell',1)));S+=timedelta(days=1);self.assertIsNotNone(a.fill_exit('S0',a.market.window('S0',S,'sell',1)));a.settle_due(S);r.after_sales(a,S);r.after_buys(a,S);self.assertEqual(a.quantity('N'),0);r.after_buys(a,S+timedelta(days=1));self.assertGreater(a.quantity('N'),0)
 def test_support_preflight(self):
  r,a,T,c,_,_=self.pair();a.market.window=lambda sid,at,side,m:fixture.window(sid=sid,at=at,price=8 if sid=='N' else 10,cash_due_at=at);r.preflight(a,c.earliest_execution_at);self.assertFalse(r.allow_sale(a,'S0'))
 def test_ordinary_preempts(self):
  r,a,T,c,s,g=self.pair();ok,oid=a.reserve_budget(quote=a.market.quote('N',T),clock=c,gross_budget_cny=D(10000));self.assertTrue(ok);r.start_pair(a,T,c,s,g);self.assertIsNone(a.swap);self.assertIn('N',a.buys);self.assertNotIn('S0',a.exits)
 def test_initial_rank_band_and_reversibility(self):
  r,a,T,c,s,g=self.pair();u=perturb(s,c,1,E.admission);v=perturb(s,c,2,E.admission)
  for x,y in zip(s,u):self.assertEqual(int(x.rank.read(c)//10),int(y.rank.read(c)//10))
  self.assertEqual(perturb(s,c,0,E.admission),s);self.assertNotEqual([x.rank.score for x in u],[x.rank.score for x in v])
 def test_price_direction_and_amount_roles(self):
  idx=pd.bdate_range('2020-01-01',periods=100);c=100*np.exp(np.arange(100)*.01);f=pd.DataFrame({'close':c,'amount':1e8},index=idx);g=pd.DataFrame({'segment_id':0,'e0_target':True,'g_ready':True,'g_grade':2},index=idx);z=evidence(f,g);self.assertTrue(z.new_ok.iloc[-1]);self.assertFalse(z.weak.iloc[-1]);f.close=c[::-1];z=evidence(f,g);self.assertTrue(z.weak.iloc[-1]);self.assertFalse(z.new_ok.iloc[-1]);f.amount=0;z=evidence(f,g);self.assertFalse(z.new_ok.any() or z.weak.any())
if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Checks))
 if not result.wasSuccessful():sys.exit(1)
 save(O/'tests.json',{'passed':True,'tests':result.testsRun})
