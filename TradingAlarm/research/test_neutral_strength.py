import unittest,math
import numpy as np
import pandas as pd
from neutral_trend_strength import neutral_regimes,neutral_frame
class Tests(unittest.TestCase):
    def test_long_strength_neutral_exit(self):
        f=neutral_regimes(np.r_[np.ones(50),np.zeros(30)])
        np.testing.assert_allclose(f.bullish_strength,10*f.up_probability)
        self.assertGreater(f.bullish_strength.iloc[49],9)
        self.assertLess(f.bullish_strength.iloc[-1],5)
        self.assertLess(neutral_regimes(np.zeros(80)).bullish_strength.iloc[-1],2)
    def test_enumerated_partitions(self):
        y=np.array([.2,1.4,-.3,.7]);hazard=.2;weight=up=neutral=0.
        for bits in range(2**(len(y)-1)):
            cuts=[0]+[i+1 for i in range(len(y)-1) if bits>>i&1]+[len(y)]
            likelihood=hazard**(len(cuts)-2)*(1-hazard)**(len(y)-len(cuts)+1)
            for a,b in zip(cuts[:-1],cuts[1:]):
                n=b-a;s=y[a:b].sum();bf=math.exp(s*s/(2*(1+n)))/math.sqrt(1+n)
                likelihood*=.5*(1+bf)
            probup=.5*(1+math.erf(s/math.sqrt(2*(1+n))))
            weight+=likelihood;neutral+=likelihood/(1+bf);up+=likelihood*bf/(1+bf)*probup
        r=neutral_regimes(y,hazard).iloc[-1]
        self.assertAlmostEqual(r.neutral_probability,neutral/weight);self.assertAlmostEqual(r.up_probability,up/weight)
    def test_flat_direction_jump(self):
        f=neutral_regimes(np.zeros(80));self.assertAlmostEqual(f.strength.iloc[-1],5);self.assertGreater(f.neutral_probability.iloc[-1],.8)
        s=neutral_regimes(np.r_[np.ones(50),-8]).strength
        self.assertGreater(s.iloc[-2],9);self.assertLess(s.iloc[-1],5)
        r=neutral_regimes(np.column_stack([np.zeros(51),np.r_[np.zeros(50),8]]));self.assertAlmostEqual(r.strength.iloc[-1],5)
    def test_prefix_units(self):
        rng=np.random.default_rng(5);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,120))));v=pd.Series(np.exp(rng.normal(5,1,120)))
        f=neutral_frame(p,p,v);pd.testing.assert_frame_equal(f[:90],neutral_frame(p[:90],p[:90],v[:90]))
        np.testing.assert_allclose(f,neutral_frame(p*10,p*10,v*7),atol=1e-10,equal_nan=True)
        np.testing.assert_allclose(f[['neutral_probability','up_probability','down_probability']].dropna().sum(axis=1),1)
if __name__=='__main__':unittest.main()
