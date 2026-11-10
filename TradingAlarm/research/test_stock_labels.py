import unittest
import numpy as np
import pandas as pd
from stock_rank_diagnostic import forward_labels


class StockLabelTests(unittest.TestCase):
    def frame(self):
        return pd.DataFrame(dict(date=pd.bdate_range('2020-01-01',periods=160),
                                 signal_close=np.arange(1,161,dtype=float),
                                 observed_bar=True,positive_volume=True))

    def test_forward_return_starts_after_signal(self):
        frame=self.frame();labels=forward_labels(frame)
        self.assertAlmostEqual(labels.forward_21.iloc[0],23/2-1)
        self.assertTrue(labels.forward_126.iloc[-127:].isna().all())

    def test_missing_endpoint_not_shifted_to_next_available_day(self):
        frame=self.frame();frame.loc[22,'observed_bar']=False
        labels=forward_labels(frame)
        self.assertTrue(pd.isna(labels.forward_21.iloc[0]))
        self.assertAlmostEqual(labels.forward_21.iloc[1],24/3-1)


if __name__=='__main__':unittest.main()
