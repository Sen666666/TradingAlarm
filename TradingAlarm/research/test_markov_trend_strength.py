import itertools,unittest
import numpy as np
import pandas as pd
from markov_trend_strength import filter_states,markov_frame,MEANS
class Tests(unittest.TestCase):
 def test_enumerated_state_paths(self):
    x=np.array([1.,2.,-1.,3.]);w=np.array([1.,.5,2.,1.]);t=np.full((3,3),1/42);np.fill_diagonal(t,20/21)
    for n in range(1,5):
        total=np.zeros(3)
        for states in itertools.product(range(3),repeat=n):
            probability=1/3
            for j,state in enumerate(states):
                if j:probability*=t[states[j-1],state]
                probability*=np.exp(-.5*w[j]*(x[j]-MEANS[state])**2)
            total[states[-1]]+=probability
        total/=total.sum();np.testing.assert_allclose(filter_states(x[:n],w[:n]).iloc[-1,1:],total)
 def test_prefix_scale_and_symmetry(self):
    x=np.r_[np.ones(20),-np.ones(20)];a=filter_states(x);b=filter_states(-x);np.testing.assert_allclose(a.up_weight,b.down_weight)
    self.assertLess(a.strength.iloc[-1],5);np.testing.assert_allclose(a.iloc[:,1:].sum(axis=1),1)
    ix=pd.date_range('2020-01-01',periods=100);rng=np.random.default_rng(444);p=pd.Series(np.exp(np.cumsum(rng.normal(0,.02,100))),index=ix);v=pd.Series(rng.uniform(1,10,100),index=ix)
    f=markov_frame(p,v,True);pd.testing.assert_frame_equal(f.iloc[:70],markov_frame(p.iloc[:70],v.iloc[:70],True));np.testing.assert_allclose(f,markov_frame(p*100,v*100,True),atol=1e-10,equal_nan=True)
 def test_memoryless_control(self):
    a=filter_states([3,-1,2],memory=False);b=filter_states([2],memory=False);np.testing.assert_allclose(a.iloc[-1],b.iloc[-1])
if __name__=='__main__':unittest.main()
