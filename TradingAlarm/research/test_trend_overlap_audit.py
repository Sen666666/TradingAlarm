import unittest
import pandas as pd
from trend_overlap_audit import interval_overlap
class Tests(unittest.TestCase):
    def test_exclusive_exit_and_union(self):
        days=pd.date_range('2026-01-01',periods=5)
        ep=dict(entry_date='2026-01-01',exit_date='2026-01-05',status='closed')
        later=dict(entry_date='2026-01-05',mark_date='2026-01-05',status='open_at_cutoff')
        self.assertEqual(interval_overlap(days,ep,[later])['kind'],'none')
        other=dict(entry_date='2026-01-02',exit_date='2026-01-04',status='closed')
        r=interval_overlap(days,ep,[other,other]);self.assertEqual(r['coverage'],.5);self.assertEqual(r['first_coverage_delay'],1);self.assertEqual(r['trailing_uncovered'],1)
    def test_open_lastmark_inclusive(self):
        days=pd.date_range('2026-01-01',periods=5);ep=dict(entry_date='2026-01-01',mark_date='2026-01-05',status='open_at_cutoff')
        self.assertEqual(interval_overlap(days,ep,[ep])['covered_bars'],5)
if __name__=='__main__':unittest.main()
