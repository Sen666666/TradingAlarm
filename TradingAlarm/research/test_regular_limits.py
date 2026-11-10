import unittest
from audit_regular_limit_hypothesis import rounded_limits
class LimitArithmeticTests(unittest.TestCase):
 def test_decimal_half_up(self):
  self.assertEqual(rounded_limits('10.05','.1'),(9.05,11.06))
  self.assertEqual(rounded_limits('3.45','.1'),(3.11,3.8))
 def test_invalid(self):
  for price in ['nan','inf','0','-1']:
   with self.assertRaises(ValueError):rounded_limits(price,.1)
if __name__=='__main__':unittest.main()
