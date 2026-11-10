"""Synthetic mechanics only; real quote/fee identity is tested separately."""
import unittest
from types import SimpleNamespace as NS
import pandas as pd
import numpy as np
from limits_v3 import *
def exposure(sid='s1',rid='r1',sector='A',pool='probe',qty=1,mark='10',floor='9',fee='0',status='live'):
 return Exposure(sid,rid,sector,pool,qty,D(mark),D(floor),D(fee),status)
def snap(cash=None,nav='1200000',daily='1200000',holdings=(),pending=(),unknown=(),recv='0'):
 if cash is None:cash=str(D(nav or '1200000')-D(recv)-sum((x.capital for x in holdings),D(0)))
 return Snapshot(D(cash),D(recv),None if nav is None else D(nav),D(daily),tuple(holdings),tuple(pending),tuple(unknown),'SYNTHETIC')
class LimitsTests(unittest.TestCase):
 def test_01_cash_retention_uses_daily_not_round_nav(self):
  b=ReserveBook(snap(cash='195',nav='1000',daily='1000',recv='805'))
  p=exposure(pool='confirmed',qty=10,mark='10',floor='10')
  self.assertIn('cash_or_original_reserve',b.reasons(p))
 def test_02_sector_one_percent_risk_is_separate(self):
  h=exposure(sid='old',pool='confirmed',qty=1,mark='100000',floor='88000',status='held')
  b=ReserveBook(snap(holdings=(h,)))
  self.assertIn('sector_risk',b.reasons(exposure(pool='confirmed',mark='10',floor='9')))
 def test_03_probe_industry_all_includes_confirmed(self):
  h=exposure(sid='old',pool='confirmed',mark='23995',floor='23995',status='held')
  b=ReserveBook(snap(holdings=(h,)))
  self.assertIn('sector_capital',b.reasons(exposure(mark='10',floor='10')))
 def test_04_confirmed_ten_percent_not_two_or_twenty(self):
  h=exposure(sid='old',pool='confirmed',mark='50000',floor='50000',status='held')
  b=ReserveBook(snap(holdings=(h,)))
  self.assertNotIn('sector_capital',b.reasons(exposure(pool='confirmed',mark='60000',floor='60000')))
  self.assertIn('sector_capital',b.reasons(exposure(pool='confirmed',mark='80000',floor='80000')))
 def test_05_exact_post_fee_probe_risk_boundary(self):
  for risk,ok in [('5999.08',True),('5999.90',False)]:
   h=exposure(sid='old',sector='B',mark='80000',floor=str(D('80000')-D(risk)),status='held')
   b=ReserveBook(snap(holdings=(h,)))
   p=exposure(mark='10000',floor='10000',fee='22.8')
   self.assertEqual('probe_risk' not in b.reasons(p),ok)
   self.assertEqual((b.snapshot.nav-p.fee)*D('.005'),D('5999.886'))
 def test_06_pending_and_cancel_pending_fees_stay_reserved(self):
  p=exposure(sid='old',sector='B',mark='20000',floor='20000',fee='5',status='cancel_pending')
  b=ReserveBook(snap(pending=(p,)))
  self.assertEqual(b.reserved_cash,D('20005'));self.assertEqual(b.unbooked_buy_fees,D('5'))
  self.assertEqual(b.resources(pool='probe'),(D('20000'),D('0')))
 def test_07_new_reservations_do_not_debit_or_fill(self):
  b=ReserveBook(snap());before=b.snapshot.cash
  self.assertEqual(b.reserve(exposure()),[])
  self.assertEqual(b.snapshot.cash,before);self.assertEqual(len(b.orders),1)
  self.assertEqual(b.reserve(exposure()),['stock_order_pending'])
 def test_08_unknown_blocks_all_new_risk(self):
  b=ReserveBook(snap(nav=None,unknown=({'round_id':'old','qty':100},)))
  self.assertEqual(b.reasons(exposure(pool='confirmed')),['NAV_OR_ASSET_UNKNOWN'])
 def test_09_closed_old_round_claim_is_in_wallet_not_new_round(self):
  at=pd.Timestamp('2022-01-06');old={'sid':'s1','cash':D('50'),'receivable':D('20'),'core':0,'add':0}
  new={'sid':'s1','cash':D('-10'),'receivable':D(0),'core':0,'add':0}
  m=NS(archives={'old':old,'new':new},cal=pd.DatetimeIndex(['2022-01-05','2022-01-06']))
  s=snapshot_from_ab(m,{},at,seed_cash=D('1000'),daily_planning_nav=D('1000'),pool_by_round={})
  self.assertEqual(s.cash,D('1040'));self.assertEqual(s.receivable,D('20'));self.assertEqual(s.nav,D('1060'))
  self.assertEqual(new['cash'],D('-10'));self.assertEqual(new['receivable'],D(0))
 def test_10_unknown_archive_qty_is_not_released(self):
  at=pd.Timestamp('2022-01-06');st={'sid':'s1','cash':D('-100'),'receivable':D('20'),'core':10,'add':2}
  m=NS(archives={'r1':st},cal=pd.DatetimeIndex(['2022-01-05','2022-01-06']))
  s=snapshot_from_ab(m,{'s1':{'state':'UNKNOWN','round_id':'r1'}},at,seed_cash=D('1000'),daily_planning_nav=D('1000'),pool_by_round={})
  self.assertIsNone(s.nav);self.assertEqual(s.cash,D('900'));self.assertEqual(s.receivable,D('20'))
  self.assertEqual((s.unknown[0]['core'],s.unknown[0]['add']),(10,2));self.assertEqual(st['core'],10)
 def test_11_nav_uses_open_gross_not_net_liquidation(self):
  at=pd.Timestamp('2022-01-06');before=pd.Timestamp('2022-01-05')
  st={'sid':'s1','sector':'A','cash':D('-100'),'receivable':D('20'),'core':10,'add':0,'fac':D('1'),'origin':('source',)}
  raw=NS(get=lambda day,default:{'raw_open':12,'raw_close':999999,'adjustment_factor':1})
  facts=NS(get=lambda day,default:{'i_floor':10 if day==before else 99999})
  m=NS(archives={'r1':st},cal=pd.DatetimeIndex([before,at]),raw={'s1':raw},facts={'s1':facts},finite=np.isfinite,np=np,lineage=lambda z:('source',))
  s=snapshot_from_ab(m,{'s1':{'state':'HELD','round_id':'r1'}},at,seed_cash=D('1000'),daily_planning_nav=D('1000'),pool_by_round={'r1':'probe'})
  self.assertEqual(s.nav,D('1040'));self.assertEqual(s.holdings[0].mark,D('12'));self.assertEqual(s.holdings[0].floor,D('10'))
 def test_12_decimal_invalid_and_global_probe_cap(self):
  with self.assertRaises(ValueError):exposure(qty=0)
  with self.assertRaises(ValueError):exposure(status='uncertain')
  for kw in ({'qty':True},{'qty':1.5},{'sid':''},{'rid':' '},{'sector':''}):
   with self.assertRaises(ValueError):exposure(**kw)
  with self.assertRaises(ValueError):snap(cash='1000',nav='999')
  with self.assertRaises(ValueError):snap(holdings=(exposure(status='live'),))
  with self.assertRaises(ValueError):snap(pending=(exposure(status='held'),))
  with self.assertRaises(ValueError):snap(unknown=({'reason':'x'},))

  with self.assertRaises(ValueError):Snapshot(1.2,D(0),D('1000'),D('1000'),(),(),(),'bad')
  h=exposure(sid='old',sector='B',mark='119990',floor='119990',status='held')
  b=ReserveBook(snap(holdings=(h,)))
  self.assertIn('pool_capital',b.reasons(exposure(mark='20',floor='20',fee='5')))
if __name__=='__main__':unittest.main()
