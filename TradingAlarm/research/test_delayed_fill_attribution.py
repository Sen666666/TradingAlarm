import unittest
import pandas as pd
from delayed_fill_attribution import decompose
class Tests(unittest.TestCase):
    def test_entry_exit_and_open_fee_identity(self):
        f=pd.DataFrame([dict(entry_price_base=100.,entry_price_delay=99.,exit_price_base=110.,exit_price_delay=112.,status_base='closed',status_delay='open_at_cutoff',return15_base=110*.9985/(100*1.0015)-1,return15_delay=112/(99*1.0015)-1)])
        r=decompose(f).iloc[0];self.assertLess(r.identity_error,1e-12);self.assertGreater(r.entry_effect,0);self.assertGreater(r.exit_mark_effect,0);self.assertGreater(r.fee_effect,0)
if __name__=='__main__':unittest.main()
