import unittest
import numpy as np
import pandas as pd
from strategy_signals import build_signals
from geometric_strength import geometric_frame,strength_exposure
from adaptive_geometric_strength import adaptive_frame
class Tests(unittest.TestCase):
    def test_all_six_parity_and_prefix(self):
        rng=np.random.default_rng(15);idx=pd.date_range('2020-01-01',periods=140);p=np.exp(np.cumsum(rng.normal(0,.03,140)))
        raw=pd.DataFrame({'close':p,'volume':np.exp(rng.normal(8,1,140))},index=idx);raw.loc[idx[[60,61]],'volume']=0
        sig=pd.DataFrame({'close':p*1.3},index=idx);valid=raw.index[raw.volume.gt(0)]
        for prefix in ('','linear_','adaptive_'):
            for joint in (False,True):
                name=prefix+'geometry_price'+('_volume' if joint else '')
                if prefix=='adaptive_':s=adaptive_frame(sig.close.loc[valid],raw.close.loc[valid],raw.volume.loc[valid],joint).strength
                else:s=geometric_frame(sig.close.loc[valid],raw.close.loc[valid],raw.volume.loc[valid],joint,degree=1 if prefix=='linear_' else 2).strength
                expected=strength_exposure(s).reindex(idx,method='ffill').fillna(0)
                actual=build_signals({'x':{'raw':raw,'signal':sig}},name)['x']
                pd.testing.assert_series_equal(actual,expected)
                pd.testing.assert_series_equal(actual[:100],build_signals({'x':{'raw':raw[:100],'signal':sig[:100]}},name)['x'])
if __name__=='__main__':unittest.main()
