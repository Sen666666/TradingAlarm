from common import *
from engine import Account,Runner
from test_sector_account import quote,window,marks,FREE,RULE,fx,T
from decimal import Decimal as D
from datetime import timedelta
from dataclasses import replace
import unittest,types

class FixedFacts:
 def __init__(self,floor=9,factor=1):self.f,self.k=D(str(floor)),D(str(factor))
 def floor(self,*args):return self.f
 def factor(self,*args):return self.k

class Contracts(unittest.TestCase):
 def account(self,mode='I',floor=9,cash=1000000):
  a=Account(initial_cash=cash);a.mode=mode;a.facts=FixedFacts(floor);a.current_nav=D(cash);return a
 def buy(self,a,budget=150000):
  clock=admission.Clock(T,T+timedelta(days=1),T.date());return a.reserve_budget(quote=quote(),clock=clock,gross_budget_cny=D(budget))
 def test_small_budget_no_borrowing(self):
  a=self.account(cash=1000);ok,_=self.buy(a);self.assertTrue(ok);self.assertGreaterEqual(a.available,0);self.assertEqual(a.buys['A'].budget_cny,D(1000))
 def test_half_budget_and_nav_growth(self):
  a=self.account('H50');self.buy(a);self.assertEqual(a.buys['A'].budget_cny,D(75000))
  b=self.account('H50',cash=2000000);self.buy(b,300000);self.assertEqual(b.buys['A'].budget_cny,D(150000))
 def test_risk_limits_size_without_moving_floor(self):
  a=self.account('RB1');self.buy(a);o=a.buys['A'];self.assertLess(o.budget_cny,D(150000));self.assertEqual(a.intents[o.order_id]['floor_signal'],D(9));r=a.fill_buy('A',window());self.assertIsNotNone(r)
  bound=next(x for x in a.audit_log if x['kind']=='risk_fill_bound');self.assertLessEqual(bound['estimated_loss'],D(10000))
 def test_risk_gap_reduces_only(self):
  a=self.account('RB1');self.buy(a);before=a.buys['A'].target_shares;r=a.fill_buy('A',window(price=12));self.assertLess(r.shares,before);bound=[x for x in a.audit_log if x['kind']=='risk_fill_bound'][-1];self.assertLessEqual(bound['estimated_loss'],bound['risk_budget'])
 def test_open_below_support_releases_cash(self):
  a=self.account();self.buy(a);self.assertIsNone(a.fill_buy('A',window(price=8)));self.assertEqual(a.available,D(1000000));self.assertFalse(a.positions);self.assertIn('A',a.rearm)
 def test_split_factor_protects_correct_coordinate(self):
  a=self.account();self.buy(a);a.facts.k=D(2);r=a.fill_buy('A',window(price=5));self.assertIsNotNone(r)
 def test_risk_minimum_cannot_force_one_lot(self):
  a=self.account('RB1',floor=1,cash=1000);ok,_=self.buy(a,150);self.assertFalse(ok);self.assertEqual(a.available,D(1000))
 def setup_rotation(self,amount=15,new_sector='G0',event=True):
  a=self.account('AMT15');clock=admission.Clock(T,T+timedelta(days=1),T.date());qmap={}
  for i in range(6):
   s=f'S{i}';qmap[s]=quote(sid=s,sector='G'+str(i//2));ok,_=a.reserve_budget(quote=qmap[s],clock=clock,gross_budget_cny=D(100000));self.assertTrue(ok)
  for i in range(6):a.fill_buy(f'S{i}',window(sid=f'S{i}'))
  at=T+timedelta(days=2);clock=admission.Clock(at,at+timedelta(days=1),at.date());qmap['N']=quote(sid='N',sector=new_sector)
  market=types.SimpleNamespace(quote=lambda s,t:qmap[s]);market.marks=lambda t,ids:{s:marks(t,sid=s)['A' if False else s] for s in ids}
  values={f'S{i}':10 if i==0 else 20+i for i in range(6)};values['N']=amount
  market.raw={s:pd.DataFrame([dict(observed_bar=True,valid_price=True,amount=float(v),amount_unit='CNY')],index=[pd.Timestamp(at.date())]) for s,v in values.items()};market.sessions={'A':[at+timedelta(days=i) for i in range(1,6)]};a.market=market
  def fact(v):return admission.Fact(v,at,at,source_id='synthetic',observed_at=at)
  sectors=[admission.Sector(g,fact(True),admission.Rank(80,at,at)) for g in sorted({q.sector_id for q in qmap.values()})]
  stocks=[admission.Security(s,fact(s),fact(q.sector_id),fact(True),fact(event if s=='N' else True),fact(20e9),fact(True),admission.Rank(80,at,at)) for s,q in qmap.items()]
  r=Runner.__new__(Runner);r.market=market;r.facts=FixedFacts();return r,a,at,clock,tuple(stocks),tuple(sectors)
 def test_rotation_exact_1_5_and_original_cap(self):
  r,a,at,c,ss,gg=self.setup_rotation();r.start_swap(a,at,c,ss,gg);self.assertEqual(a.swap['candidate'],'N');self.assertEqual(a.swap['victim'],'S0');self.assertEqual(a.swap['ratio'],D('1.5'));self.assertEqual(len(a.positions),6);self.assertNotIn('N',a.buys)
 def test_rotation_below_threshold(self):
  r,a,at,c,ss,gg=self.setup_rotation(amount=14.999);r.start_swap(a,at,c,ss,gg);self.assertIsNone(a.swap)
 def test_amount_alone_cannot_create_signal(self):
  r,a,at,c,ss,gg=self.setup_rotation(amount=1000,event=False);r.start_swap(a,at,c,ss,gg);self.assertIsNone(a.swap)
 def test_cross_sector_one_for_one_cannot_hide_fourth_sector(self):
  r,a,at,c,ss,gg=self.setup_rotation(amount=1000,new_sector='G3');r.start_swap(a,at,c,ss,gg);self.assertIsNone(a.swap)
 def test_pending_normal_exit_is_not_rotated(self):
  r,a,at,c,ss,gg=self.setup_rotation();a.normal_exits={'S0'};a.request_exit(a.market.quote('S0',at),c);r.start_swap(a,at,c,ss,gg);self.assertIsNone(a.swap)
 def test_rotation_no_parallel_second_pair(self):
  r,a,at,c,ss,gg=self.setup_rotation();r.start_swap(a,at,c,ss,gg);first=a.swap['id'];r.start_swap(a,at,c,ss,gg);self.assertEqual(a.swap['id'],first);self.assertEqual(a.counts['rotation_started'],1)
 def test_unfilled_sale_expires_without_buying(self):
  r,a,at,c,ss,gg=self.setup_rotation();r.start_swap(a,at,c,ss,gg);due=at+timedelta(days=2);cc=admission.Clock(due,due+timedelta(days=1),due.date());r.advance_swap(a,due,cc);self.assertIsNone(a.swap);self.assertNotIn('S0',a.exits);self.assertNotIn('N',a.buys);self.assertEqual(a.quantity('S0'),10000)
 def test_normal_exit_upgrade_is_irrevocable(self):
  r,a,at,c,ss,gg=self.setup_rotation();r.start_swap(a,at,c,ss,gg);a.normal_exits={'S0'};a.request_exit(a.market.quote('S0',at),c);due=at+timedelta(days=2);cc=admission.Clock(due,due+timedelta(days=1),due.date());r.advance_swap(a,due,cc);self.assertIn('S0',a.exits);self.assertEqual(a.exits['S0'].purpose,'structure_exit')

if __name__=='__main__':
 suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contracts);result=unittest.TextTestRunner(verbosity=2).run(suite)
 if result.wasSuccessful():write(HERE/'technical/synthetic.json',dict(passed=True,tests=result.testsRun,real_share_cash_ledger_used=True))
 else:sys.exit(1)
