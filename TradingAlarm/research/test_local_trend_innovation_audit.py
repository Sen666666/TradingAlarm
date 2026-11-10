import unittest
import numpy as np
import pandas as pd
from local_trend_innovation_audit import response_labels


class InnovationLabelTests(unittest.TestCase):
    def test_transient_and_permanent_displacement(self):
        index=pd.RangeIndex(5);forecast=pd.Series(0.,index=index);slope=forecast.copy();scale=pd.Series(.1,index=index)
        for prices,expected in [([.2,0,0,0,0],0),([.2,.2,.2,.2,.2],1)]:
            result=response_labels(pd.Series(prices),forecast,slope,scale,1)
            self.assertAlmostEqual(result.retention.iloc[0],expected)
            self.assertTrue(np.isnan(result.retention.iloc[-1]))

    def test_extrapolated_drift_and_zero_exclusion(self):
        p=pd.Series([.2,.3,.4,.5]);f=pd.Series([0.,.1,.2,.5]);s=pd.Series(.1,index=p.index);scale=pd.Series(.1,index=p.index)
        r=response_labels(p,f,s,scale,2)
        self.assertAlmostEqual(r.retention.iloc[0],1)
        self.assertAlmostEqual(r.departure_from_drift.iloc[0],0)


if __name__=='__main__':unittest.main()
