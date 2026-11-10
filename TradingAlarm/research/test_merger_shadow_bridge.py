import unittest
import numpy as np
import pandas as pd
from merger_shadow_bridge import bridge
class MergerBridgeTests(unittest.TestCase):
 def data(self):
  idx=pd.bdate_range('2020-01-01',periods=240)
  parent=pd.DataFrame(dict(signal_close=20.,observed_bar=True,positive_volume=True),index=idx[:210])
  child=pd.DataFrame(dict(signal_close=30.,observed_bar=True,positive_volume=True),index=idx[220:])
  return idx,parent,child
 def test_value_jump_and_gap(self):
  idx,p,c=self.data();out,f=bridge(p,c,idx,idx[209],idx[220],10.,15.,.5)
  self.assertEqual(f,.5);self.assertEqual(out.loc[idx[220],'signal_close'],15.)
  self.assertTrue((out.signal_close.iloc[:220]==20.).all())
  self.assertFalse(out.observed_bar.iloc[210:220].any())
  self.assertTrue(out.observed_bar.iloc[220:].all())
 def test_no_future_effect_and_scale_invariance(self):
  idx,p,c=self.data();out,_=bridge(p,c,idx,idx[209],idx[220],10.,15.,.5)
  changed=c.copy();changed.loc[idx[230]:,'signal_close']*=2
  other,_=bridge(p,changed,idx,idx[209],idx[220],10.,15.,.5)
  pd.testing.assert_frame_equal(out.iloc[:230],other.iloc[:230])
  c.signal_close*=3;scaled,_=bridge(p,c,idx,idx[209],idx[220],10.,15.,.5)
  pd.testing.assert_frame_equal(out,scaled)
 def test_bad_terms_rejected(self):
  idx,p,c=self.data()
  with self.assertRaises(ValueError):bridge(p,c,idx,idx[209],idx[220],10.,15.,0.)
if __name__=='__main__':unittest.main()
