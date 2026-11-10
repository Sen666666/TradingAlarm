import unittest
import pandas as pd
from workbench_period_report import describe


class PeriodReportTests(unittest.TestCase):
    def test_carry_in_and_initial_cash_drawdown(self):
        p=pd.DataFrame(dict(nav=[.8,.9,.72,1.08],cash=[0.]*4,fees=[0.]*4),
                       index=pd.to_datetime(['2024-01-02','2024-12-31','2025-01-02','2025-12-31']))
        r=describe(p)
        self.assertAlmostEqual(r['years'][0]['return_fraction'],-.1)
        self.assertAlmostEqual(r['years'][1]['return_fraction'],.2)
        self.assertAlmostEqual(r['years'][1]['pnl_cny'],180000.)
        self.assertAlmostEqual(r['max_drawdown'],-.28)
        self.assertEqual(r['peak'],'initial_cash')
        self.assertEqual(r['trough'],'2025-01-02')

    def test_drawdown_peak_can_precede_calendar_year(self):
        p=pd.DataFrame(dict(nav=[1.5,1.2,1.05],cash=[0.]*3,fees=[0.]*3),
                       index=pd.to_datetime(['2024-12-30','2024-12-31','2025-01-02']))
        r=describe(p)
        self.assertAlmostEqual(r['max_drawdown'],-.3)
        self.assertAlmostEqual(r['years'][1]['max_drawdown'],-.125)
        self.assertEqual(r['peak'],'2024-12-30')


if __name__=='__main__':unittest.main()
