import unittest
from ths_signal_adjustment import signal_frame


class AdjustmentTests(unittest.TestCase):
    def history(self):
        return dict(symbol='X',bars=[dict(date=d,open=p,high=p,low=p,close=p,volume=100,amount=100*p) for d,p in [('2020-01-02',10.),('2020-01-03',4.9),('2020-01-06',5.)]])
    def rights(self):
        return dict(symbol='X',records=[{'1':20200103,'471':'2020-01-03(每十股 转增10.00股 红利2.00元)$'}])
    def test_combined_cash_and_shares_are_ex_price_neutral(self):
        f=signal_frame(self.history(),self.rights())
        self.assertAlmostEqual(f.signal_close.iloc[0],f.signal_close.iloc[1])
        self.assertAlmostEqual(f.factor.iloc[1],10/4.9)
    def test_future_event_does_not_rewrite_past(self):
        h=self.history();r=self.rights();a=signal_frame(h,r)
        r['records'][0]['471']='2020-01-03(每十股 转增10.00股 红利3.00元)$'
        b=signal_frame(h,r)
        self.assertEqual(a.signal_close.iloc[0],b.signal_close.iloc[0])
    def test_subscription_and_empty_response_not_assumed_free(self):
        r=self.rights();r['records'][0]['471']='2020-01-03(每十股 配股3.00股 配股价3.00元)$'
        with self.assertRaises(ValueError):signal_frame(self.history(),r)
        r['records']=[]
        with self.assertRaises(ValueError):signal_frame(self.history(),r)

    def test_event_without_quote_stays_on_date_and_cannot_fill(self):
        h=self.history();h['bars'].pop(1)
        frame=signal_frame(h,self.rights())
        event=frame.loc['2020-01-03']
        self.assertFalse(event.bar_allows_trade)
        self.assertTrue(event.synthetic_event_bar)
        self.assertAlmostEqual(event.close,4.9)
        self.assertAlmostEqual(event.signal_close,10.)
        self.assertAlmostEqual(frame.loc['2020-01-06','signal_close'],5*10/4.9)

    def test_optional_reference_tick_is_not_dividend_rounding(self):
        h=self.history();h['bars'][0].update(open=1.77,high=1.77,low=1.77,close=1.77)
        r=self.rights();r['records'][0]['471']='2020-01-03(每十股 红利0.25元)$'
        exact=signal_frame(h,r);rounded=signal_frame(h,r,reference_tick=.01)
        self.assertAlmostEqual(exact.factor.iloc[1],1.77/1.745)
        self.assertAlmostEqual(rounded.factor.iloc[1],1.77/1.75)
        self.assertEqual(exact.signal_close.iloc[0],rounded.signal_close.iloc[0])
        with self.assertRaises(ValueError):signal_frame(h,r,reference_tick=0)


if __name__=='__main__':unittest.main()
