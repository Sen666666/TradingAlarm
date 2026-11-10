"""Reporting-only temporal regressions; zero account/strategy execution."""
import unittest,json
from pathlib import Path
import analyze as A

class Tests(unittest.TestCase):
    def test_exit_before_later_attempt_end(self):
        self.assertEqual(A.wait_endpoint(None,'probe','2025-07-17 09:30:00+08:00','2025-09-23'),'exited_without_observed_migration')
    def test_attempt_end_before_later_exit(self):
        self.assertEqual(A.wait_endpoint(None,'probe','2025-09-24 09:30:00+08:00','2025-09-23'),'attempt_ended_before_observed_migration')
    def test_same_day_open_exit_precedes_attempt_ending_close(self):
        self.assertEqual(A.wait_endpoint(None,'probe','2025-09-23 09:30:00+08:00','2025-09-23'),'exited_without_observed_migration')
    def test_exact_timestamp_tie_has_explicit_exit_first_convention(self):
        self.assertEqual(A.wait_endpoint(None,'probe','2025-09-23 15:10:00+08:00','2025-09-23'),'exited_without_observed_migration')
    def test_still_active_wait_is_censored(self):
        self.assertEqual(A.wait_endpoint(None,'probe',None,None),'still_probe_right_censored')
    def test_migration_observed_on_same_close_as_end_allowed(self):
        self.assertEqual(A.wait_endpoint('2025-09-23','confirmed','2025-09-24 09:30:00+08:00','2025-09-23'),'observed_migrated')
    def test_after_end_migration_is_rejected(self):
        with self.assertRaises(AssertionError):A.wait_endpoint('2025-09-24','confirmed',None,'2025-09-23')

if __name__=='__main__':
    r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
    A.save('analysis-errata-20261101/REGRESSION_GATE.json',dict(passed=r.wasSuccessful(),tests=r.testsRun,errors=len(r.errors),failures=len(r.failures),account_paths=0))
    raise SystemExit(not r.wasSuccessful())
