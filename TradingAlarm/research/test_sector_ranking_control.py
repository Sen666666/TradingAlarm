import unittest
import pandas as pd
from sector_ranking_control import random_priority
class Tests(unittest.TestCase):
    def test_seed_deterministic_and_outcomes_do_not_affect_priority(self):
        e=pd.DataFrame({'entry_date':['2024-01-01']*3,'symbol':['c','a','b'],'strength':[8.,9.,10.],'return15':[1.,-1.,2.]})
        changed=e.copy();changed['return15']=-999
        a=random_priority(e,9200);b=random_priority(changed,9200)
        pd.testing.assert_series_equal(a.strength,b.strength)
        pd.testing.assert_frame_equal(a.drop(columns='strength'),e.sort_values(['entry_date','symbol']).drop(columns='strength'))
if __name__=='__main__':unittest.main()
