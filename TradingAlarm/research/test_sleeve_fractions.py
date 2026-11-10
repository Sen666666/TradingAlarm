import unittest
import pandas as pd
from monthly252_sleeve_comparison import endpoints

class SleeveFractionTests(unittest.TestCase):
    def test_reinvestment_residual_cash_and_never_traded(self):
        t=pd.DataFrame([dict(symbol='A',cutoff='2026-10-16',scenario='base',status='closed',return15=.2,return30=.2,fraction=.5),dict(symbol='A',cutoff='2026-10-16',scenario='base',status='closed',return15=-.1,return30=-.1,fraction=.5)])
        r=endpoints(t,['A','B'],'fraction')[0]
        self.assertAlmostEqual(r['equal_initial_sleeve_return'],((1+.5*.2)*(1-.5*.1)-1)/2)
    def test_terminal_zero_keeps_uninvested_cash(self):
        t=pd.DataFrame([dict(symbol='A',cutoff='2026-10-16',scenario='base',status='terminal_unknown',return15=.2,return30=.2,fraction=.3)])
        rows=endpoints(t,['A'],'fraction')
        self.assertAlmostEqual(rows[0]['equal_initial_sleeve_return'],.06)
        self.assertAlmostEqual(rows[1]['equal_initial_sleeve_return'],-.3)
        self.assertAlmostEqual(endpoints(t,['A'])[1]['equal_initial_sleeve_return'],-1.)

if __name__=='__main__':unittest.main()
