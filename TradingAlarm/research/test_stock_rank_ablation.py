import unittest
import numpy as np
import pandas as pd
from stock_walkforward_rank import FEATURES,fit
from stock_rank_ablation import fit_features
class AblationTests(unittest.TestCase):
 def sample(self):
  rng=np.random.default_rng(123);d=pd.DataFrame(rng.normal(size=(20,5)),columns=FEATURES);d['date']=pd.to_datetime(['2020-01-01']*10+['2020-02-01']*10);d['forward_21']=rng.normal(size=20);return d
 def test_full_equals_original(self):
  d=self.sample();np.testing.assert_allclose(fit(d),fit_features(d,FEATURES),atol=1e-12)
 def test_omitted_feature_cannot_affect_refit(self):
  d=self.sample();kept=FEATURES[:-1];a=fit_features(d,kept);d[FEATURES[-1]]=10000;np.testing.assert_array_equal(a,fit_features(d,kept))
if __name__=='__main__':unittest.main()
