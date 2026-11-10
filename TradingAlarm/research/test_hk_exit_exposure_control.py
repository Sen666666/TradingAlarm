import unittest
import pandas as pd
from hk_exit_exposure_control import calibration
class CalibrationTests(unittest.TestCase):
 def test_future_signals_cannot_change_frozen_scale(self):
  idx=pd.bdate_range('2021-01-01','2023-01-01');a=pd.Series(1.,index=idx);b=pd.Series(.5,index=idx)
  before=calibration(a,b);a.loc['2022':]=0;b.loc['2022':]=1
  self.assertEqual(before,calibration(a,b));self.assertEqual(before['scale'],.5)
 def test_empty_exposure_rejected_and_no_leverage(self):
  idx=pd.bdate_range('2021-01-01','2021-12-31');a=pd.Series(0.,index=idx);b=pd.Series(1.,index=idx)
  with self.assertRaises(ValueError):calibration(a,b)
  a[:]=.5;self.assertEqual(calibration(a,b)['scale'],1.)
if __name__=='__main__':unittest.main()
