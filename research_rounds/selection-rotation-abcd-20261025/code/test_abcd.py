"""Causal ranking and new controller boundary tests, before financial outcomes."""
from common_abcd import *
sys.path.append(str(OLD/'code'))
from types import SimpleNamespace as NS
from datetime import datetime,timedelta,timezone
from decimal import Decimal as D
from unittest.mock import patch
import unittest,pandas as pd
import sector_stock_admission as a
import selection_abcd as select
from rotation_abcd import Controller
from board_abcd import returns,percentile,interleave,gate_or,build

class FakeAccount:
 def __init__(self,held):
  self.positions={sid:NS(shares=100,sector_id=sec) for sid,sec in held.items()};self.exits={};self.buys={};self.audit_log=[];self.nav=D(1000000)
 def occupancy(self,at):return [a.Occupancy(s,s,p.sector_id,at,True,exit_latched=s in self.exits) for s,p in self.positions.items()]
 def balance(self,*args):return {'nav':self.nav}
 def request_exit(self,q,clock):self.exits[q.security_id]=NS(quote=q)
 def cancel_buy(self,s):self.buys.pop(s,None)

class Tests(unittest.TestCase):
 def test_percentile_and_missing(self):
  x=np.array([[1,1,2,np.nan],[np.nan]*4]);actual=percentile(x,3)
  np.testing.assert_allclose(actual[0,:3],[100/3,100/3,250/3]);self.assertTrue(np.isnan(actual[1]).all())
 def test_endpoint_segment(self):
  c=np.arange(1,9,dtype=float).reshape(4,2);s=np.ones(c.shape);s[3,0]=2;c[0,1]=np.nan
  r=returns(c,s,2);self.assertTrue(np.isnan(r[2,1]));self.assertTrue(np.isnan(r[3,0]));self.assertEqual(r[2,0],4)
 def test_queues_missing_long(self):
  self.assertEqual(interleave(['a','b'],['a','c','d']),['a','c','b','d'])
  np.testing.assert_allclose(gate_or(np.array([1,0,np.nan]),np.array([np.nan,np.nan,np.nan])),[1,0,np.nan],equal_nan=True)
 def scenario(self,i,account,ctrl,*,fresh=True,tie=False,missing=False,own=False,price=10,mode='C',stock_challenge=False):
  at=datetime(2020,1,1,tzinfo=timezone.utc)+timedelta(days=i);clock=a.Clock(at,at+timedelta(days=1),at.date())
  def fact(v):return a.Fact(v,at,at,observed_at=at)
  sectors={s:a.Sector(s,fact(True),a.Rank(v,at,at)) for s,v in {'N':100,'G1':80,'G2':70,'O':60 if not tie else 100}.items()}
  if tie:sectors={s:a.Sector(s,fact(True),a.Rank(100,at,at)) for s in sectors}
  stocksector={'n':'N','o':'O','o2':'O','a':'G1','b':'G2'}
  if stock_challenge:stocksector['newO']='O'
  stocks={s:a.Security(s,fact(s),fact(sec),fact(True),fact(True),fact(2e10),fact(False if own and s=='o' else True),a.Rank(100,at,at)) for s,sec in stocksector.items()}
  if stock_challenge:stocks={s:a.Security(s,fact(s),fact(sec),fact(True),fact(True),fact(2e10),fact(True),a.Rank(100 if s=='newO' else 60,at,at)) for s,sec in stocksector.items()}
  if missing:sectors['N']=a.Sector('N',fact(None),a.Rank(100,at,at))
  row=NS(i=i,allowed=lambda s:True,get=lambda s,k:100 if s in ['N','newO'] else 60)
  quotes={s:NS(security_id=s,sector_id=sec,read_price=lambda at:D(price),fx=NS(read=lambda at:D(1)),quantity=NS(buy_minimum=100)) for s,sec in stocksector.items()}
  select.BUY={str(at.date()):{'newO' if stock_challenge else 'n'} if fresh else set()};select._row=row;select._elig={};select.set_account(mode)
  with patch.object(select,'facts',return_value=(stocks,sectors,row)):
   return ctrl.advance(account,None,clock,mode,quotes,{},{}),quotes
 def fixture(self):return FakeAccount({'o':'O','o2':'O','a':'G1','b':'G2'}),Controller()
 def test_three_distinct_closes_sector_all_exits(self):
  ac,c=self.fixture()
  self.assertIsNone(self.scenario(0,ac,c)[0]['plan']);self.assertIsNone(self.scenario(1,ac,c)[0]['plan']);r,_=self.scenario(2,ac,c)
  self.assertEqual(r['plan']['outgoing'],'O');self.assertEqual(set(ac.exits),{'o','o2'});self.assertEqual(len(ac.positions),4);self.assertEqual(ac.nav,D(1000000));self.assertIn('O',c.banned_sectors)
  with self.assertRaises(ValueError):self.scenario(2,ac,c)
 def test_missing_resets_and_tie_does_not_force(self):
  ac,c=self.fixture();self.scenario(0,ac,c);self.scenario(1,ac,c,missing=True);self.scenario(2,ac,c);self.assertIsNone(self.scenario(3,ac,c)[0]['plan'])
  ac,c=self.fixture()
  for i in range(4):self.assertIsNone(self.scenario(i,ac,c,tie=True)[0]['plan'])
 def test_fresh_fire_lot_and_own_exit(self):
  for kw in [dict(fresh=False),dict(price=2000),dict(own=True)]:
   ac,c=self.fixture()
   for i in range(3):r,_=self.scenario(i,ac,c,**kw);self.assertIsNone(r['plan'])
 def test_no_unban_while_actual_occupancy(self):
  ac,c=self.fixture();c.banned_sectors={'N'};ac.positions['n']=NS(sector_id='N',shares=100)
  self.scenario(0,ac,c);self.assertIn('N',c.banned_sectors)
  del ac.positions['n'];self.scenario(1,ac,c);self.assertNotIn('N',c.banned_sectors)
 def test_stock_replacement_C_and_D(self):
  for mode in ['C','D']:
   ac=FakeAccount({'o':'O','o2':'O'});c=Controller()
   for i in range(3):r,_=self.scenario(i,ac,c,stock_challenge=True,mode=mode)
   self.assertEqual(r['plan']['kind'],'stock');self.assertEqual(r['plan']['incoming'],'newO');self.assertEqual(len(ac.exits),1)
   self.assertIn(r['plan']['outgoing'],c.banned_stocks)

if __name__=='__main__':
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));assert result.wasSuccessful()
 write(HERE/'technical/unit-tests-v2.json',dict(passed=True,tests=result.testsRun,recorded_at=now(),new_economic_runs=0))
