import unittest,math
from trend_overlap_price_audit import partition
class Tests(unittest.TestCase):
    def ep(self,start,end,p,q):return dict(entry_date=start,exit_date=end,status='closed',entry_price=p,exit_price=q,return15=q*.9985/(p*1.0015)-1)
    def test_delayed_entry_and_early_exit(self):
        e=self.ep('2026-01-01','2026-01-05',100,120);o=self.ep('2026-01-02','2026-01-04',110,125)
        r=partition(e,[o]);self.assertAlmostEqual(r['before'],math.log(1.1));self.assertAlmostEqual(r['covered'],math.log(125/110));self.assertAlmostEqual(r['after'],math.log(120/125));self.assertLess(r['identity_error'],1e-12)
    def test_no_overlap_and_open_terminal(self):
        e=dict(entry_date='2026-01-01',mark_date='2026-01-02',status='open_at_cutoff',entry_price=100,exit_price=110,return15=110/(100*1.0015)-1)
        r=partition(e,[]);self.assertAlmostEqual(r['none'],math.log(1.1));self.assertFalse(r['has_overlap'])
if __name__=='__main__':unittest.main()
