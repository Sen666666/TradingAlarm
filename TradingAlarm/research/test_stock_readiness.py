import unittest
import pandas as pd
from audit_retired_readiness import inspect_history


class StockReadinessTests(unittest.TestCase):
    def sample(self):
        master = dict(symbol='000001.SZ', code='sz.000001', ipoDate='2000-01-01', outDate='2020-01-03')
        row = dict(date='2020-01-02', code='sz.000001', open='10', high='11', low='9', close='10', volume='100', amount='1000', tradestatus='1', isST='0', adjustflag='3')
        return master, dict(symbol=master['symbol'], rows=[row])

    def test_valid_raw_data_does_not_pass_execution_gate(self):
        master, data = self.sample()
        result = inspect_history(data, master)
        self.assertTrue(result['structurally_valid'])
        self.assertFalse(result['execution_ready'])

    def test_wrong_volume_units_are_rejected(self):
        master, data = self.sample()
        data['rows'][0]['volume'] = '1'
        self.assertIn('vwap_outside_bar_requires_review', inspect_history(data, master)['errors'])

    def test_suspension_is_not_positive_volume_trade(self):
        master, data = self.sample()
        data['rows'][0].update(tradestatus='0', volume='0', amount='0')
        result = inspect_history(data, master)
        self.assertEqual(result['positive_volume_rows'], 0)
        self.assertIsNone(result['last_positive_volume_date'])

    def test_duplicate_and_after_delisting_dates_are_rejected(self):
        master, data = self.sample()
        data['rows'] *= 2
        self.assertIn('invalid_duplicate_or_unsorted_dates', inspect_history(data, master)['errors'])
        data['rows'] = [dict(data['rows'][0], date='2020-01-06')]
        self.assertIn('dates_outside_requested_lifetime', inspect_history(data, master)['errors'])

    def test_silent_full_page_truncation_is_not_complete(self):
        master, data = self.sample()
        master['outDate']='2024-01-01'
        row=data['rows'][0]
        data['rows']=[dict(row,date=str(d.date())) for d in pd.bdate_range('2010-01-01',periods=2000)]
        self.assertIn('suspected_incomplete_pagination',inspect_history(data,master)['errors'])


if __name__ == '__main__':
    unittest.main()
