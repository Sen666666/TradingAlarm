import unittest
from multihorizon_turnover_audit import classify


class TurnoverAuditTests(unittest.TestCase):
    def test_delayed_fill_uses_frozen_decision(self):
        decisions = [dict(date='2020-01-02', scores={'A':1}),
                     dict(date='2020-02-03', scores={'A':1}),
                     dict(date='2020-03-02', scores={'A':0})]
        orders = [dict(date='2020-02-10', signal_date='2020-01-31', symbol='A',
                       units=-2, raw_open=100, fee=.3),
                  dict(date='2020-03-03', signal_date='2020-02-28', symbol='A',
                       units=-10, raw_open=90, fee=1.35)]
        result = classify(decisions, orders)
        self.assertEqual(result['score_unchanged']['notional'], 200)
        self.assertEqual(result['score_changed']['notional'], 900)

    def test_obsolete_target_cannot_silently_cross_month(self):
        decisions = [dict(date='2020-01-02', scores={'A':1}),
                     dict(date='2020-02-03', scores={'A':0})]
        with self.assertRaises(AssertionError):
            classify(decisions, [dict(date='2020-02-04', signal_date='2019-12-31',
                                      symbol='A', units=1, raw_open=100, fee=.15)])


if __name__ == '__main__':
    unittest.main()
