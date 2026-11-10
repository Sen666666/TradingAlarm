import unittest
from campaign_engine import dual_risk_capacity,run_campaign
import test_campaign_completion as completion


class DualRiskTests(unittest.TestCase):
    def test_giveback_uses_second_ceiling(self):
        q,initial,current=dual_risk_capacity({'winner':90000},{'winner':5000},1e6,100)
        self.assertEqual(initial,5000);self.assertEqual(current,90000);self.assertEqual(q,100)
        q,_,_=dual_risk_capacity({'winner':110000},{'winner':5000},1e6,100)
        self.assertEqual(q,0)

    def test_initial_risk_still_limits_entries(self):
        q,initial,_=dual_risk_capacity({'a':39000},{'a':39000},1e6,100)
        self.assertEqual(q,10);self.assertEqual(initial,39000)
        q,initial,_=dual_risk_capacity({'a':1000},{'a':5000},1e6,100)
        self.assertEqual(initial,1000);self.assertEqual(q,390)

    def test_incompatible_additions_rejected(self):
        a=completion.CompletionTests().asset()
        with self.assertRaisesRegex(ValueError,'noadd'):run_campaign({'a':a},buying_risk_mode='dual')


if __name__=='__main__':unittest.main()
