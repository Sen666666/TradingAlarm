import unittest
import pandas as pd
from prepare_a import normalize,merge_frames


def raw(dates=('2026-05-14','2026-05-15'),source='tushare'):
 return pd.DataFrame([{'trade_date':d,'open':10.,'high':11.,'low':9.,'close':10.5,
                       'volume':1000.,'amount':1000.,'source':source} for d in dates])

class CacheTests(unittest.TestCase):
 def test_units_avoid_false_volume_jump(self):
  a=normalize(raw(),'tushare_raw','old')
  ths=raw(('2026-05-15','2026-05-18'));ths['volume']*=100;ths['amount']*=1000
  b=normalize(ths,'ths_raw','new');merged,conflicts,check=merge_frames(a,b,'A')
  self.assertTrue(check['accepted']);self.assertEqual(conflicts,[])
  self.assertEqual(list(merged.volume),[100000.]*3);self.assertEqual(list(merged.amount),[1000000.]*3)
  self.assertEqual(merged.iloc[1].source_path,'old');self.assertEqual(merged.iloc[2].source_path,'new')
 def test_conflicting_source_not_silently_spliced(self):
  a=normalize(raw(),'tushare_raw','old');x=raw(('2026-05-15','2026-05-18'));x['volume']*=100;x['amount']*=1000;x.loc[0,'close']=10.8
  b=normalize(x,'ths_raw','new');merged,conflicts,check=merge_frames(a,b,'A')
  self.assertFalse(check['accepted']);self.assertEqual(len(conflicts),1);pd.testing.assert_frame_equal(merged,a)
 def test_no_overlap_is_explicit_bridge_gap(self):
  a=normalize(raw(),'tushare_raw','old');b=normalize(raw(('2026-05-18',)),'ths_raw','new')
  merged,conflicts,check=merge_frames(a,b,'A');self.assertEqual(check['reason'],'no_overlap_requires_bridge');pd.testing.assert_frame_equal(merged,a)
 def test_unverified_units_rejected(self):
  with self.assertRaises(ValueError):normalize(raw(source='unknown'),'tushare_raw','old')
 def test_duplicate_date_rejected(self):
  with self.assertRaises(ValueError):normalize(raw(('2026-05-15','2026-05-15')),'tushare_raw','old')
 def test_bad_OHLC_rejected(self):
  x=raw();x.loc[0,'low']=20
  with self.assertRaises(ValueError):normalize(x,'tushare_raw','old')

if __name__=='__main__':unittest.main(verbosity=2)
