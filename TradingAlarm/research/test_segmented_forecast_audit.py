import unittest
import pandas as pd
import numpy as np
from segmented_forecast_audit import forward_labels
class Tests(unittest.TestCase):
    def test_forward_alignment_and_censoring(self):
        p=pd.Series([100.,110.,121.,133.1]);a=forward_labels(p,2)
        np.testing.assert_allclose(a.iloc[:2],np.log(1.21));self.assertTrue(a.iloc[2:].isna().all())
if __name__=='__main__':unittest.main()
