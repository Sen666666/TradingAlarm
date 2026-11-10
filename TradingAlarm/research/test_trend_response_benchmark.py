import unittest
import numpy as np
import pandas as pd
from trend_response_benchmark import paired_prices,exposures,DIVERGE,END


class ResponseTests(unittest.TestCase):
    def test_identical_prefix_and_future_separation(self):
        up,down=paired_prices(np.zeros(END),.5)
        pd.testing.assert_series_equal(up.iloc[:DIVERGE],down.iloc[:DIVERGE])
        self.assertGreater(up.iloc[-1],down.iloc[-1])
        a,b=exposures(up),exposures(down)
        for model in a:pd.testing.assert_series_equal(a[model].iloc[:DIVERGE],b[model].iloc[:DIVERGE])


if __name__=='__main__':unittest.main()
