import unittest
import pandas as pd
from monthly_ah_engine import run


class MonthlyAHTests(unittest.TestCase):
    def asset(self):
        idx=pd.bdate_range('2019-01-01',periods=400)
        price=pd.Series([100+i*.1 for i in range(400)],index=idx)
        raw=pd.DataFrame(dict(open=price,close=price,high=price+1,low=price-1,volume=1e7))
        return dict(raw=raw,signal=raw.copy(),currency='CNY',lot=100,dividends=[],splits=[])

    def test_split_preserves_account_value_and_causal_history(self):
        a=self.asset();idx=a['raw'].index;fx=pd.Series(1.,index=idx);args=(str(idx[280].date()),str(idx[-1].date()))
        old=run({'A':a},*args,policy='score_change',fx_override=fx)
        a['raw'].loc[idx[340]:,['open','high','low','close']]/=2
        a['splits']=[dict(date=str(idx[340].date()),ratio=2.)]
        new=run({'A':a},*args,policy='score_change',fx_override=fx)
        pd.testing.assert_frame_equal(old[1],new[1])
        self.assertEqual(old[2],new[2])

    def test_holiday_and_delay_use_eligible_opens(self):
        a=self.asset();b=self.asset();idx=a['raw'].index;start=idx[280]
        a['raw']=a['raw'].drop(start);a['signal']=a['signal'].drop(start)
        result=run({'A':a,'B':b},str(start.date()),str(idx[-1].date()),delay=1,fx_override=pd.Series(1.,index=idx))
        first=next(o for o in result[2] if o['symbol']=='A')
        self.assertEqual(first['date'],str(idx[282].date()))
        self.assertLess(first['signal_date'],first['date'])

    def test_future_crash_cannot_change_prior_fills(self):
        a=self.asset();idx=a['raw'].index;fx=pd.Series(1.,index=idx);args=(str(idx[280].date()),str(idx[-1].date()))
        old=run({'A':a},*args,policy='score_change',fx_override=fx)
        a['raw'].loc[idx[350]:,['open','high','low','close']]*=.5;a['signal']=a['raw'].copy()
        new=run({'A':a},*args,policy='score_change',fx_override=fx)
        pd.testing.assert_frame_equal(old[1].loc[:idx[349]],new[1].loc[:idx[349]])
        self.assertEqual(new[1]['w_A'].iloc[-1],0.)

if __name__=='__main__':unittest.main()
