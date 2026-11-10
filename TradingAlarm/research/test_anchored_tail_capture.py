import unittest
import pandas as pd
from anchored_tail_capture import interval_coverage
class Tests(unittest.TestCase):
    def test_boundaries(self):
        ix=pd.date_range('2024-01-01',periods=5)
        def case(start,end,status='closed'):
            return interval_coverage(ix,pd.DataFrame([dict(entry_date=start,exit_date=end,mark_date=end,status=status)]))
        self.assertEqual(case('2024-01-01','2024-01-06')['category'],'full_interval')
        r=case('2024-01-02','2024-01-05');self.assertEqual(r['category'],'late_and_early');self.assertEqual(r['coverage'],.6)
        self.assertEqual(case('2024-01-06','2024-01-07')['category'],'no_participation')
        self.assertEqual(case('2024-01-01','2024-01-05','open_at_cutoff')['coverage'],1)
    def test_fragmentation(self):
        ix=pd.date_range('2024-01-01',periods=5)
        e=pd.DataFrame([dict(entry_date='2024-01-01',exit_date='2024-01-02',mark_date='2024-01-02',status='closed'),dict(entry_date='2024-01-04',exit_date='2024-01-06',mark_date='2024-01-06',status='closed')])
        self.assertEqual(interval_coverage(ix,e)['category'],'internal_gaps')
if __name__=='__main__':unittest.main()
