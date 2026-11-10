"""Only fictitious rows; never loads a strategy, prices, or historical returns."""
import copy
import importlib.util
import pathlib
import unittest
from reporting import build_report, exact_permit_audit, normalize_native_actions, normalize_native_claims


class ReportSyntheticTests(unittest.TestCase):
    def fixture(self):
        args = dict(roster=['FICT_A', 'FICT_B', 'FICT_C'], windows=['W'],
                    arms=['base', 'joint'], lanes=['AB', 'PRICE'], expected_roster_size=3,
                    states=[], coverage=[], actions=[], claims=[], terminal_marks=[])
        for sid in args['roster']:
            for arm in args['arms']:
                for lane in args['lanes']:
                    k = dict(sid=sid, window='W', arm=arm, lane=lane)
                    args['states'].append(dict(k, status='NEVER_ENTERED'))
                    args['coverage'].append(dict(k, financial_covered=True, reason='SYNTHETIC_COMPLETE'))
        return args

    def setstate(self, a, sid='FICT_A', arm='joint', lane='PRICE', **values):
        for r in a['states']:
            if (r['sid'],r['arm'],r['lane']) == (sid,arm,lane):
                r.update(values)

    def action(self, a, side, q, price, fee, seq, **extra):
        r = dict(sid='FICT_A', window='W', arm='joint', lane='PRICE', round_id='R1',
                 role='PROBE', side=side, q=q, price=price, fee=fee,
                 day='2099-01-02', known_day='2099-01-02', sequence=seq)
        r.update(extra)
        a['actions'].append(r)
        return r

    def lane(self, result):
        return next(r for r in result['lane_rows'] if (r['sid'],r['arm'],r['lane']) == ('FICT_A','joint','PRICE'))

    def test_zero_fixed_denominator(self):
        r = build_report(**self.fixture())
        self.assertEqual(len(r['stock_rows']), 6)
        self.assertEqual(r['summary'][0]['common_covered_count'], 3)
        self.assertTrue(all(x['known_total_pnl'] == 0 for x in r['stock_rows']))
        self.assertFalse(r['comparison_release_ready'])

    def test_fifo_partial_buy_fee_and_open_net(self):
        a = self.fixture()
        self.setstate(a, status='OPEN_CENSORED')
        self.action(a,'BUY',10,10,2,1)
        self.action(a,'BUY',10,20,4,2)
        self.action(a,'SELL',15,30,3,3)
        a['terminal_marks'] = [dict(sid='FICT_A', window='W', arm='joint', lane='PRICE',
            round_id='R1', role='PROBE', q=5, verified=True, mark_raw=25,
            sell_slippage=.04, estimated_dated_sell_fee=2, terminal_day='2099-12-31')]
        r = self.lane(build_report(**a))
        self.assertAlmostEqual(r['trade_realized'], 243)
        self.assertAlmostEqual(r['remaining_cost'], 102)
        self.assertAlmostEqual(r['unrealized'], 16)
        self.assertAlmostEqual(r['known_total_pnl'],259)

    def test_claim_once_no_receivable_double_count(self):
        a = self.fixture()
        self.setstate(a,status='CLOSED')
        self.action(a,'BUY',10,10,1,1)
        self.action(a,'SELL',10,12,1,2)
        a['claims'] = [dict(sid='FICT_A', window='W', arm='joint', lane='PRICE',
            claim_id='C1', amount=8, receivable=8, legal_ex_confirmed=True, tax_scenario='NET80')]
        r = self.lane(build_report(**a))
        self.assertEqual(r['trade_realized'],18)
        self.assertEqual(r['known_total_pnl'],26)
        a['claims'].append(copy.deepcopy(a['claims'][0]))
        with self.assertRaises(ValueError): build_report(**a)

    def test_unknown_does_not_mark_to_endpoint(self):
        a = self.fixture()
        self.setstate(a,status='UNKNOWN', last_known_day='2099-01-02', last_known_mark=100)
        self.action(a,'BUY',10,10,1,1)
        r = self.lane(build_report(**a))
        self.assertIsNone(r['known_total_pnl'])
        self.assertIsNone(r['unrealized'])
        self.assertEqual(r['last_known_mark'],100)
        self.assertEqual(build_report(**a)['summary'][0]['common_covered_count'],2)

    def test_missing_state_unknown_not_zero(self):
        a = self.fixture()
        a['states'] = []
        r = build_report(**a)
        self.assertTrue(all(x['known_total_pnl'] is None for x in r['stock_rows']))

    def test_role_isolation_oversell_rejected(self):
        a = self.fixture()
        self.setstate(a,status='CLOSED')
        self.action(a,'BUY',10,10,1,1)
        self.action(a,'SELL',10,12,1,2,role='ADD')
        with self.assertRaises(ValueError): build_report(**a)

    def test_two_rounds_not_winner_only_and_lane_reconciliation(self):
        a = self.fixture()
        self.setstate(a,status='CLOSED')
        self.action(a,'BUY',10,10,0,1)
        self.action(a,'SELL',10,20,0,2)
        self.action(a,'BUY',10,20,0,3,round_id='R2')
        self.action(a,'SELL',10,5,0,4,round_id='R2',one_price_ohlc=True)
        r = build_report(**a)
        self.assertEqual(self.lane(r)['known_total_pnl'],-50)
        d = next(x for x in r['differences'] if x['sid']=='FICT_A')
        self.assertEqual(d['joint_minus_baseline'],-50)
        self.assertEqual(sum(d['lane_contributions'].values()),-50)
        self.assertTrue(self.lane(r)['one_price_ohlc_dependency'])

    def test_coverage_keeps_uncovered_economics_out_of_common(self):
        a = self.fixture()
        a['coverage'][-1]['financial_covered'] = False
        a['coverage'][-1]['reason'] = 'FICTITIOUS_GAP'
        r = build_report(**a)
        self.assertEqual(r['summary'][0]['fixed_denominator'],3)
        self.assertEqual(r['summary'][0]['common_covered_count'],2)
        self.assertEqual(r['summary'][0]['arm_only_covered_sids'],['FICT_C'])

    def test_exact_permit_fields_and_multiplicity(self):
        p = [dict(event_id='E', permission=1),dict(event_id='E',permission=1)]
        self.assertTrue(exact_permit_audit(p,p)['exact'])
        self.assertFalse(exact_permit_audit(p,p[:1])['exact'])
        self.assertFalse(exact_permit_audit(p,[dict(event_id='E',permission=2)]*2)['exact'])

    def test_missing_verified_mark_does_not_lose_principal(self):
        a=self.fixture()
        self.setstate(a,status='OPEN_CENSORED')
        self.action(a,'BUY',10,10,2,1)
        r=self.lane(build_report(**a))
        self.assertEqual(r['trade_realized'],0)
        self.assertEqual(r['remaining_cost'],102)
        self.assertIsNone(r['unrealized'])

    def test_fixed_production_roster_guard(self):
        a=self.fixture()
        del a['expected_roster_size']
        with self.assertRaises(ValueError): build_report(**a)

    def test_ambiguous_clock_and_nonfinite_rejected(self):
        a=self.fixture()
        self.setstate(a,status='CLOSED')
        self.action(a,'BUY',10,10,1,1)
        self.action(a,'SELL',10,12,1,1)
        with self.assertRaises(ValueError): build_report(**a)
        a['actions'][1]['sequence']=2
        a['actions'][1]['price']=float('nan')
        with self.assertRaises(ValueError): build_report(**a)

    def test_native_conversion_split_sell_all_and_claim(self):
        a=self.fixture()
        self.setstate(a,status='CLOSED')
        rd=dict(round_id='R1',sid='FICT_A',window='W',arm='joint',owner_lane='PRICE')
        raw=[dict(round_id='R1',day='2099-01-02',side=side,q=q,price=p,fee=f)
             for side,q,p,f in [('buy_core',10,10,1),('buy_add',5,20,2),('sell_all',15,20,3)]]
        a['actions']=normalize_native_actions(raw,[rd])
        self.assertEqual(len(a['actions']),4)
        self.assertEqual(sum(x['fee'] for x in a['actions'] if x['side']=='SELL'),3)
        a['claims']=normalize_native_claims([dict(owner_round_id='R1',key=['W','joint','FICT_A','E'],
            amount=8,core_amount=6,recognized=True,settled=False)],[rd])
        a['closed_cash_checks']=[dict(rd,lane='PRICE',cash_plus_receivable=102)]
        r=build_report(**a)
        self.assertEqual(self.lane(r)['known_total_pnl'],102)
        self.assertEqual(len(r['closed_round_reconciliation']),1)
        a['closed_cash_checks'][0]['cash_plus_receivable']=110
        with self.assertRaises(ValueError): build_report(**a)

    def test_share_actions_unadmitted(self):
        a=self.fixture()
        a['stock_adjustments']=[dict(quantity_factor=2)]
        with self.assertRaisesRegex(ValueError,'UNADMITTED'): build_report(**a)

    def test_price_distribution_includes_losers_unknown(self):
        a=self.fixture()
        self.setstate(a,status='CLOSED')
        self.action(a,'BUY',10,10,0,1)
        self.action(a,'SELL',10,5,0,2)
        r=build_report(**a)
        d=next(x for x in r['lane_distributions'] if x['arm']=='joint' and x['lane']=='PRICE')
        self.assertEqual(d['losses'],1)
        self.assertEqual(d['known_mean'],-50)


if __name__ == '__main__':
    unittest.main(verbosity=2)
