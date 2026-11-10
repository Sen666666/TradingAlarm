"""Small exactness tests; no account replay, file mutation or trading."""
import copy
import unittest
import resume_baseline as B


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        self.rows = [dict(at='2022-12-30 15:10:00+08:00', available='84360.525699312823', positions={'A': 100}),
                     dict(at='2023-01-03 15:10:00+08:00', available='84360.525699312824', positions={'A': 100, 'B': 200})]

    def test_identical_all_fields(self):
        got = B.compare_records(self.rows, copy.deepcopy(self.rows))
        self.assertTrue(got['passed'])
        self.assertEqual(got['prefix_records'], 2)
        self.assertEqual(got['continuation_records'], 1)
        self.assertEqual(got['expected_sha256'], got['actual_sha256'])

    def test_subcent_difference_never_tolerated(self):
        changed = copy.deepcopy(self.rows)
        changed[1]['available'] = '84360.525699312823'
        got = B.compare_records(self.rows, changed)
        self.assertFalse(got['passed'])
        self.assertEqual(got['first_difference']['path'], '$.available')
        self.assertEqual(got['first_difference']['row'], 1)

    def test_holdings_difference_never_masked_by_equal_cash(self):
        changed = copy.deepcopy(self.rows)
        changed[1]['positions']['B'] = 201
        got = B.compare_records(self.rows, changed)
        self.assertFalse(got['passed'])
        self.assertEqual(got['first_difference']['path'], '$.positions.B')

    def test_sequence_matters(self):
        got = B.compare_records(self.rows, self.rows[::-1])
        self.assertFalse(got['passed'])
        self.assertEqual(got['first_difference']['row'], 0)

    def test_missing_record_fails(self):
        got = B.compare_records(self.rows, self.rows[:1])
        self.assertFalse(got['passed'])
        self.assertEqual(got['first_difference']['reason'], 'record_count_mismatch')

    def test_future_reference_excluded_only(self):
        future = self.rows + [dict(at='2023-05-04 15:10:00+08:00', available='1')]
        self.assertTrue(B.compare_records(future, self.rows)['passed'])
        self.assertFalse(B.compare_records(future, future)['passed'])

    def test_nested_audit_timestamps(self):
        fill = dict(kind='fill', receipt=dict(at='2023-01-03 09:30:00+08:00'))
        dividend = dict(kind='dividend_accrual', receivable=dict(ex_at='2023-01-04 00:00:00+08:00'))
        self.assertEqual(B.row_day(fill), '2023-01-03')
        self.assertEqual(B.row_day(dividend), '2023-01-04')
        self.assertTrue(B.compare_records([fill, dividend], [fill, dividend])['passed'])

    def test_financial_string_never_coerced_to_float(self):
        self.assertIsNotNone(B.first_difference('84360.525699312823', float('84360.525699312823')))


if __name__ == '__main__':
    unittest.main(verbosity=2)
