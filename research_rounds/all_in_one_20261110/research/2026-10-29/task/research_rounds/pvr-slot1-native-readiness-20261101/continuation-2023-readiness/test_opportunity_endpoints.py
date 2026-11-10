"""Analysis regressions only; no account initialization or financial replay."""
import unittest
from opportunity_endpoints import endpoint,summarize
class EndpointTests(unittest.TestCase):
    def test_fill_before_end(self):self.assertEqual(endpoint('2023-04-03T09:30:00+08:00','2023-04-04')['status'],'funded_before_attempt_end')
    def test_end_before_fill(self):self.assertEqual(endpoint('2023-04-05T09:30:00+08:00','2023-04-04')['status'],'industry_attempt_ended_before_funding')
    def test_same_day_open_before_end_close(self):self.assertEqual(endpoint('2023-04-04T09:30:00+08:00','2023-04-04')['status'],'funded_before_attempt_end')
    def test_exact_tie_completed_fill_first(self):self.assertEqual(endpoint('2023-04-04T15:10:00+08:00','2023-04-04')['status'],'funded_before_attempt_end')
    def test_unfunded_observed_end(self):self.assertEqual(endpoint(None,'2023-04-04')['status'],'industry_attempt_ended_before_funding')
    def test_unfunded_still_active(self):self.assertEqual(endpoint(None,None)['status'],'observation_cutoff_still_active')
    def test_end_exact_cutoff_is_not_censored(self):self.assertEqual(endpoint(None,'2023-12-29')['status'],'industry_attempt_ended_before_funding')
    def test_future_end_not_known_at_cutoff(self):self.assertEqual(endpoint(None,'2024-01-02')['status'],'observation_cutoff_still_active')
    def test_mutually_exclusive_denominator(self):
        gs=[dict(x=endpoint(None,None)),dict(x=endpoint(None,'2023-03-01')),dict(x=endpoint('2023-02-01T09:30:00+08:00',None))]
        s=summarize(gs,'x');self.assertEqual((s['groups'],s['funded_before_attempt_end'],s['industry_attempt_ended_before_funding'],s['still_active_at_observation_cutoff_right_censored']),(3,1,1,1))
if __name__=='__main__':unittest.main(verbosity=2)
