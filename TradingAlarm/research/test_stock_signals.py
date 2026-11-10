import unittest
import pandas as pd
from stock_signal_data import retired_signal_frame, stock_features


class StockSignalTests(unittest.TestCase):
    def data(self):
        rows=[]
        for date in pd.bdate_range('2020-01-01', periods=300):
            rows.append(dict(date=str(date.date()), open='10',high='10',low='10',close='10',volume='100',amount='1000',tradestatus='1'))
        history=dict(symbol='X',rows=rows)
        factors=dict(symbol='X',rows=[dict(dividOperateDate='2019-01-01',backAdjustFactor='1')])
        return history,factors

    def test_future_factor_never_backfills_past(self):
        h,f=self.data();before=stock_features(retired_signal_frame(h,f))
        f['rows'].append(dict(dividOperateDate=h['rows'][280]['date'],backAdjustFactor='2'))
        after=stock_features(retired_signal_frame(h,f))
        pd.testing.assert_frame_equal(before.iloc[:280],after.iloc[:280])

    def test_split_is_neutral_to_signal_price(self):
        h,f=self.data();event=h['rows'][260]['date']
        f['rows'].append(dict(dividOperateDate=event,backAdjustFactor='2'))
        for row in h['rows'][260:]:
            row.update(open='5',high='5',low='5',close='5')
        frame=retired_signal_frame(h,f)
        self.assertTrue(frame.signal_close.eq(10).all())
        self.assertFalse(stock_features(frame).entry_signal.any())

    def test_missing_anchor_fails_closed(self):
        h,f=self.data();f['rows'][0]['dividOperateDate']='2020-02-01'
        with self.assertRaises(ValueError):retired_signal_frame(h,f)

    def test_future_prices_do_not_change_prior_features(self):
        h,f=self.data();before=stock_features(retired_signal_frame(h,f))
        h['rows'][-1].update(open='20',high='20',low='20',close='20')
        after=stock_features(retired_signal_frame(h,f))
        pd.testing.assert_frame_equal(before.iloc[:-1],after.iloc[:-1])


if __name__=='__main__':unittest.main()
