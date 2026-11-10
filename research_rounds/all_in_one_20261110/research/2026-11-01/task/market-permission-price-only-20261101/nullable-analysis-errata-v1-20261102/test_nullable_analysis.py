import unittest
from datetime import date,datetime
import numpy as np
import pandas as pd
from nullable_analysis import pending_time,analysis_scope,candidate_inputs,cached_flag,MISSING

class NullableTests(unittest.TestCase):
 def test_none_absent(self):self.assertEqual(pending_time(None)['kind'],'ABSENT')
 def test_nan_absent(self):
  for x in [float('nan'),np.float64('nan'),pd.NA,pd.NaT]:
   with self.subTest(value=repr(x)):self.assertEqual(pending_time(x)['kind'],'ABSENT')
 def test_true_pending(self):
  for x in ['2026-05-06',date(2026,5,6),datetime(2026,5,6,15,10),pd.Timestamp('2026-05-06')]:
   with self.subTest(value=repr(x)):
    self.assertEqual(pending_time(x),dict(kind='PENDING',date='2026-05-06',reason=None))
    self.assertFalse(analysis_scope(dict(mode='ACTIVE',permit_next_open=True,pending_failure_at=x),True)['permit'])
 def test_missing_is_unknown(self):
  self.assertEqual(pending_time()['kind'],'UNKNOWN')
  s=analysis_scope(dict(mode='ACTIVE',permit_next_open=True),True)
  self.assertFalse(s['support']);self.assertFalse(s['permit']);self.assertFalse(s['mature'])
 def test_invalid_not_absent(self):
  for x in [0,1,False,True,'','bad','2026-02-30',[],{},np.array([np.nan])]:
   with self.subTest(value=repr(x)):self.assertEqual(pending_time(x)['kind'],'UNKNOWN')
 def test_none_nan_same_scope(self):
  a=analysis_scope(dict(mode='ACTIVE',permit_next_open=True,pending_failure_at=None),True)
  b=analysis_scope(dict(mode='ACTIVE',permit_next_open=True,pending_failure_at=float('nan')),True)
  self.assertEqual(a,b);self.assertTrue(a['support']);self.assertTrue(a['permit']);self.assertTrue(a['mature'])
 def test_active_not_permit_or_mature(self):
  s=analysis_scope(dict(mode='ACTIVE',permit_next_open=False,pending_failure_at=None),False)
  self.assertTrue(s['support']);self.assertFalse(s['permit']);self.assertFalse(s['mature'])
 def test_ended_not_resurrected(self):
  s=analysis_scope(dict(mode='ENDED',permit_next_open=True,pending_failure_at=None),True)
  self.assertFalse(s['support']);self.assertFalse(s['permit']);self.assertFalse(s['mature'])
 def test_missing_permit_does_not_grant(self):self.assertFalse(analysis_scope(dict(mode='ACTIVE',pending_failure_at=None),True)['permit'])

class InputGuardTests(unittest.TestCase):
 def test_cached_01_flag_decode_no_unknown_default(self):
  for x in [1,1.,np.int64(1),np.bool_(True)]:self.assertIs(cached_flag(x),True)
  for x in [0,0.,np.int64(0),False]:self.assertIs(cached_flag(x),False)
  for x in [None,np.nan,pd.NA,MISSING,2,-1,'1',[]]:self.assertIsNone(cached_flag(x))
 def setUp(self):self.good=dict(stock_Q=True,I_valid=True,canonical_known=True,raw_close=11.,factor=2.,I_floor=20.,CP1_floor=21.)
 def test_complete(self):self.assertEqual(candidate_inputs(self.good),dict(eligible=True,reasons=[],raw_floor=10.5))
 def test_unknown_protection_not_zero(self):
  for f in ['I_floor','CP1_floor']:
   for x in [None,np.nan,pd.NA,0,-1,float('inf'),False,MISSING]:
    with self.subTest(field=f,value=repr(x)):
     r=dict(self.good);r.pop(f) if x is MISSING else r.update({f:x});out=candidate_inputs(r)
     self.assertFalse(out['eligible']);self.assertIsNone(out['raw_floor'])
 def test_unknown_factor_not_one_or_zero(self):
  for x in [None,np.nan,pd.NA,0,-1,float('inf'),False,MISSING]:
   with self.subTest(value=repr(x)):
    r=dict(self.good);r.pop('factor') if x is MISSING else r.update(factor=x);self.assertFalse(candidate_inputs(r)['eligible'])
 def test_unknown_qualification_does_not_grant(self):
  for f in ['stock_Q','I_valid','canonical_known']:
   for x in [None,np.nan,pd.NA,False,1,MISSING]:
    with self.subTest(field=f,value=repr(x)):
     r=dict(self.good);r.pop(f) if x is MISSING else r.update({f:x});self.assertFalse(candidate_inputs(r)['eligible'])
 def test_unknown_price_does_not_grant(self):
  for x in [None,np.nan,pd.NA,0,-1,float('inf')]:
   with self.subTest(value=repr(x)):
    self.assertFalse(candidate_inputs(dict(self.good,raw_close=x))['eligible'])
 def test_at_line_rejected(self):self.assertFalse(candidate_inputs(dict(self.good,raw_close=10.5))['eligible'])

if __name__=='__main__':unittest.main(verbosity=2)
