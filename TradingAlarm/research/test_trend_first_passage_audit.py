import unittest
import pandas as pd
from trend_first_passage_audit import first_passage


class FirstPassageTests(unittest.TestCase):
    def test_order_and_ambiguity(self):
        f=pd.DataFrame([dict(open=100,high=131,low=89),dict(open=100,high=132,low=95)])
        self.assertEqual(first_passage(f,100),('ambiguous',0))
        f.loc[0,'open']=131
        self.assertEqual(first_passage(f,100),('up_first',0))
        f.loc[0,'open']=89
        self.assertEqual(first_passage(f,100),('down_first',0))
        f.iloc[0]=[100,101,99]
        self.assertEqual(first_passage(f,100),('up_first',1))
        self.assertEqual(first_passage(f.iloc[:1],100),('neither',1))


if __name__=='__main__':unittest.main()
