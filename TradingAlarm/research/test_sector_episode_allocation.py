import unittest
import pandas as pd
from sector_episode_allocation import allocate
class Tests(unittest.TestCase):
    def test_cash_conservation_group_limit_and_future_price_independence(self):
        dates=pd.bdate_range('2024-01-02',periods=3);names=[f's{i}' for i in range(12)];marks=pd.DataFrame(10.,index=dates,columns=names)
        ep=pd.DataFrame([dict(symbol=s,entry_date='2024-01-02',signal_date='2024-01-01',exit_date='2024-01-04',entry_price=10.,exit_price=12.,strength=10-i*.1) for i,s in enumerate(names)])
        mp={(pd.Timestamp('2024-01-01'),s):'a' for s in names};gate={(pd.Timestamp('2024-01-01'),'a'):True}
        p,t=allocate(ep,marks,mp,gate,'stock_only',15);self.assertEqual(p.positions.iloc[0],9);self.assertAlmostEqual(p.cash.iloc[0],.1)
        c,u=allocate(ep,marks,mp,gate,'gate_group_cap',15);self.assertEqual(c.positions.iloc[0],3)
        self.assertAlmostEqual(u.pnl.sum(),c.nav.iloc[-1]-1)
        changed=marks.copy();changed.iloc[-1]=100
        p2,_=allocate(ep,changed,mp,gate,'stock_only',15);pd.testing.assert_frame_equal(p.iloc[:2],p2.iloc[:2])
        off,none=allocate(ep,marks,mp,{},'gate',15);self.assertTrue(none.empty);self.assertTrue(off.nav.eq(1).all())
if __name__=='__main__':unittest.main()
