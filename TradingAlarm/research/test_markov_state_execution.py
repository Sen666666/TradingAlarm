import unittest
import numpy as np
import pandas as pd
from markov_state_execution import map_state_exposure
class Tests(unittest.TestCase):
 def test_states_ties_missing(self):
    f=pd.DataFrame([[np.nan]*3,[.2,.3,.5],[np.nan]*3,[.1,.7,.2],[.1,.45,.45],[.4,.2,.4],[.1,.2,.7]],columns=['down_weight','neutral_weight','up_weight'])
    self.assertEqual(map_state_exposure(f).tolist(),[0,1,1,0,0,0,1]);pd.testing.assert_series_equal(map_state_exposure(f.iloc[:4]),map_state_exposure(f).iloc[:4])
if __name__=='__main__':unittest.main()
