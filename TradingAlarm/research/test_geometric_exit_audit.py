import unittest
import numpy as np
import pandas as pd
from geometric_exit_audit import linear_velocity,future_window
class Tests(unittest.TestCase):
    def test_linear_fit(self):
        x=np.arange(21);y=4+.02*x;v=np.arange(1,22)
        self.assertAlmostEqual(linear_velocity(y,v),.02)
        self.assertAlmostEqual(linear_velocity(y+12,v*8),.02)
    def test_future_window_boundaries(self):
        f=pd.DataFrame({'signal_close':range(10)},index=pd.date_range('2025-12-27',periods=10))
        w=future_window(f,'2025-12-27',5)
        self.assertEqual(w.index[0],pd.Timestamp('2025-12-27'));self.assertEqual(w.index[-1],pd.Timestamp('2025-12-31'))
        self.assertIsNone(future_window(f,'2025-12-28',5));self.assertIsNone(future_window(f,'2026-01-04',5))
if __name__=='__main__':unittest.main()
