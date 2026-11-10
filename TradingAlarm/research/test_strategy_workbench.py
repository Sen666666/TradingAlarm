import unittest
import pandas as pd
import test_monthly_ah as fixtures
from monthly_ah_engine import run
from strategy_signals import build_signals,period_metrics


class WorkbenchTests(unittest.TestCase):
    def test_daily_pending_delay_is_not_reset_forever(self):
        a=fixtures.MonthlyAHTests().asset();idx=a['raw'].index;assets={'A':a}
        result=run(assets,str(idx[280].date()),str(idx[-1].date()),policy='score_change',delay=1,fx_override=pd.Series(1.,index=idx),signals=build_signals(assets,'short21'),cadence='daily')
        self.assertEqual(result[2][0]['date'],str(idx[281].date()))
        self.assertEqual(len(result[2]),1)

    def test_short_signal_warmup_and_future_independence(self):
        a=fixtures.MonthlyAHTests().asset();idx=a['raw'].index
        for name,h in [('short21',21),('medium63',63),('long252',252)]:
            before=build_signals({'A':a},name)['A']
            self.assertTrue(before.iloc[:h].eq(0).all())
            changed=dict(a,signal=a['signal'].copy());changed['signal'].loc[idx[350]:,'close']*=.1
            after=build_signals({'A':changed},name)['A']
            pd.testing.assert_series_equal(before.iloc[:350],after.iloc[:350])

    def test_2026_carry_in_nav_not_first_close(self):
        p=pd.DataFrame({'nav':[1.,1.1,.99],'cash':[0.,0.,0.],'fees':[0.,1.,1.]},index=pd.to_datetime(['2025-12-31','2026-01-02','2026-01-05']))
        m=period_metrics(p,'2026-01-01','2026-12-31')
        self.assertAlmostEqual(m['return_fraction'],-.01)
        self.assertAlmostEqual(m['max_drawdown'],-.1)

if __name__=='__main__':unittest.main()
