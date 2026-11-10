import unittest
import pandas as pd
from peer_gate_signal import gate_exposure
class Tests(unittest.TestCase):
    def test_reject_no_late_entry_hold_then_exit(self):
        b=pd.Series([0.,1.,1.,0.,1.,1.,0.]);g=pd.Series([False,False,True,True,True,False,False])
        self.assertEqual(gate_exposure(b,g).tolist(),[0,0,0,0,1,1,0])
        pd.testing.assert_series_equal(gate_exposure(b,g*0+True),b)
    def test_missing_gate_is_closed(self):
        b=pd.Series([1.,1.,0.,1.]);g=pd.Series([True],index=[3])
        self.assertEqual(gate_exposure(b,g).tolist(),[0,0,0,1])
if __name__=='__main__':unittest.main()
