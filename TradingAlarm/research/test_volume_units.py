import unittest
import numpy as np
import pandas as pd
from volume_units import split_consistent_volume
from adaptive_geometric_strength import adaptive_frame
from strategy_signals import build_signals
class Tests(unittest.TestCase):
    def test_split_invariance(self):
        rng=np.random.default_rng(21);ix=pd.date_range('2024-01-01',periods=120);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,120))),index=ix);v=pd.Series(np.exp(rng.normal(8,1,120)),index=ix)
        splitprice=p.copy();splitvolume=v.copy();splitprice.iloc[60:]/=2;splitvolume.iloc[60:]*=2
        events=[{'date':str(ix[60].date()),'ratio':2}];fixed=split_consistent_volume(splitvolume,events)
        pd.testing.assert_series_equal(fixed,v)
        np.testing.assert_allclose(adaptive_frame(p,p,v),adaptive_frame(p,splitprice,fixed),atol=1e-12,equal_nan=True)
        pd.testing.assert_series_equal(split_consistent_volume(splitvolume[:50],events),v[:50])
        raw=pd.DataFrame({'close':splitprice,'volume':splitvolume})
        original=raw.copy(deep=True)
        build_signals({'x':{'raw':raw,'signal':pd.DataFrame({'close':p}),'splits':events}},'adaptive_geometry_price_volume_split_units')
        pd.testing.assert_frame_equal(raw,original)
    def test_reverse_and_invalid(self):
        ix=pd.date_range('2024-01-01',periods=4);v=pd.Series([10.,10.,5.,5.],index=ix)
        np.testing.assert_allclose(split_consistent_volume(v,[{'date':'2024-01-03','ratio':.5}]),10)
        with self.assertRaises(ValueError):split_consistent_volume(v,[{'date':'2024-01-03','ratio':0}])
if __name__=='__main__':unittest.main()
