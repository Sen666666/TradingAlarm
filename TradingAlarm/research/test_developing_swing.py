import unittest
import numpy as np
import pandas as pd
from swing_structure_strength import swing_frame
class Tests(unittest.TestCase):
 def test_causal_and_preserved_confirmations(self):
    rng=np.random.default_rng(824);ix=pd.date_range('2020-01-01',periods=250);p=pd.Series(np.exp(np.cumsum(rng.normal(.001,.025,250))),index=ix)
    old,events=swing_frame(p);new,ne=swing_frame(p,True);self.assertEqual(events,ne)
    prefix,_=swing_frame(p.iloc[:150],True);pd.testing.assert_frame_equal(new.iloc[:150],prefix)
    units,_=swing_frame(p*10,True);np.testing.assert_allclose(new.strength,units.strength,atol=1e-10,equal_nan=True)
    self.assertTrue((old.strength.fillna(5)!=new.strength.fillna(5)).any())
if __name__=='__main__':unittest.main()
