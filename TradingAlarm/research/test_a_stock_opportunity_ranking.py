import unittest
import pandas as pd
from a_stock_opportunity_ranking import rank_candidates


class RankTests(unittest.TestCase):
    def test_only_same_date_scores_affect_rank(self):
        frame=pd.DataFrame(dict(date=['2022-01-03']*5+['2022-01-04']*5,
            momentum126_21=[1,2,3,4,5]*2,atr_fraction=[.01,.02,.03,.04,.05]*2))
        ranked=rank_candidates(frame)
        self.assertEqual(ranked.atr_fraction_quintile.tolist(),[1,2,3,4,5]*2)
        self.assertEqual(ranked.momentum126_21_quintile.tolist(),[5,4,3,2,1]*2)
        frame.loc[5:,'atr_fraction']=100.
        frame.loc[5:,'momentum126_21']=-100.
        pd.testing.assert_frame_equal(ranked.iloc[:5],rank_candidates(frame).iloc[:5])

    def test_ties_receive_equal_rank_and_missing_score_not_selected(self):
        f=pd.DataFrame(dict(date=['2022-01-03']*5,momentum126_21=[1,1,1,1,None],atr_fraction=[1]*5))
        r=rank_candidates(f)
        self.assertEqual(r.atr_fraction_quintile.nunique(),1)
        self.assertTrue(pd.isna(r.momentum126_21_quintile.iloc[-1]))


if __name__=='__main__':unittest.main()
