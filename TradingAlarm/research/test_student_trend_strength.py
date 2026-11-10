import itertools,unittest
import numpy as np
import pandas as pd
from markov_trend_strength import filter_states,markov_frame,MEANS


class StudentTests(unittest.TestCase):
    def test_enumeration_and_extreme_observation(self):
        x=np.array([1.,8.,-2.]);t=np.full((3,3),1/42);np.fill_diagonal(t,20/21);total=np.zeros(3)
        for states in itertools.product(range(3),repeat=3):
            probability=1/3
            for j,state in enumerate(states):
                if j:probability*=t[states[j-1],state]
                probability*=(1+(x[j]-MEANS[state])**2/3)**-3
            total[states[-1]]+=probability
        total/=total.sum();np.testing.assert_allclose(filter_states(x,student=True).iloc[-1,1:],total)
        normal=filter_states([20]).iloc[0].up_weight
        robust=filter_states([20],student=True).iloc[0].up_weight
        self.assertLess(robust,normal)
        f=filter_states(x,student=True);g=filter_states(-x,student=True);np.testing.assert_allclose(f.up_weight,g.down_weight)

    def test_prefix_and_units(self):
        rng=np.random.default_rng(705);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,150))));v=pd.Series(rng.uniform(1,10,150))
        f=markov_frame(p,v,True,student=True)
        pd.testing.assert_frame_equal(f.iloc[:100],markov_frame(p.iloc[:100],v.iloc[:100],True,student=True))
        np.testing.assert_allclose(f,markov_frame(p*100,v*10,True,student=True),atol=1e-10)


if __name__=='__main__':unittest.main()
