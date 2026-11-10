import unittest
import numpy as np
import pandas as pd
from trajectory_break_diagnostic import forecast_frame
from adaptive_geometric_strength import fit_experts
class TestForecast(unittest.TestCase):
    def test_prefix_units_and_manual_forecast(self):
        rng=np.random.default_rng(331);ix=pd.date_range('2020-01-01',periods=100)
        p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,100))),index=ix);v=pd.Series(rng.uniform(1,10,100),index=ix)
        f=forecast_frame(p,v)
        pd.testing.assert_frame_equal(f.iloc[:70],forecast_frame(p.iloc[:70],v.iloc[:70]))
        np.testing.assert_allclose(f,forecast_frame(p*100,v*100),atol=1e-10,equal_nan=True)
        i=50;y=np.log(p.to_numpy());_,pred=fit_experts(y[i-21:i],v.iloc[i-21:i])
        scale=np.sqrt(np.mean(np.diff(y)[i-22:i-1]**2))
        np.testing.assert_allclose(f.iloc[i,:3],(y[i]-np.r_[pred,y[i-1]])/scale)
    def test_current_jump_does_not_change_prior_scale(self):
        ix=pd.date_range('2020-01-01',periods=60);p=pd.Series(np.exp(np.arange(60)*.01),index=ix);v=pd.Series(1.,index=ix)
        q=p.copy();q.iloc[-1]*=np.exp(-.1)
        diff=forecast_frame(q,v).iloc[-1,:3]-forecast_frame(p,v).iloc[-1,:3]
        np.testing.assert_allclose(diff,-10,atol=1e-10)
if __name__=='__main__':unittest.main()
