import unittest
import pandas as pd
from strength_state_duration import state_episodes
class Tests(unittest.TestCase):
    def test_censoring_and_reentry(self):
        s=pd.Series([1,1,1,0,0,1,1,0,0,0,0,1],index=pd.date_range('2023-12-30',periods=12))
        e=state_episodes(s,end='2024-01-10')
        self.assertEqual(len(e),3);self.assertTrue(e[0]['left_censored']);self.assertEqual(e[0]['sessions'],1);self.assertTrue(e[0]['reentry5'])
        self.assertFalse(e[1]['left_censored']);self.assertEqual(e[1]['sessions'],2);self.assertIsNone(e[1]['reentry5']);self.assertTrue(e[2]['right_censored'])
    def test_entry_after_flat(self):
        s=pd.Series([0,0,1,1,0,0,0],index=pd.date_range('2024-01-01',periods=7));e=state_episodes(s)
        self.assertEqual(len(e),1);self.assertFalse(e[0]['left_censored']);self.assertEqual(e[0]['sessions'],2)
if __name__=='__main__':unittest.main()
