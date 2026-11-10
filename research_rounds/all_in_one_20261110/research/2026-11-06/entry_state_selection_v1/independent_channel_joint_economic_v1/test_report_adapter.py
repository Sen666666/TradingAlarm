"""Fictional ledgers only. No engine runner or historical PRICE input."""
import copy
from decimal import Decimal
from types import SimpleNamespace as NS
import unittest
import pandas as pd
from report_adapter import build_comparison, financial_coverage,industry_delay_diagnostics


def fixture(lane='AB', arm='A_UNION_B'):
    sid, rid = 'FICTION', 'r1'
    days = [pd.Timestamp('2001-01-01'), pd.Timestamp('2001-01-02')]
    rd = dict(round_id=rid, sid=sid, window='2022', arm=arm, owner_lane=lane,
              event_id='event1', status='COMPLETE_CONDITIONAL_STOCK_ROUND',
              entry_day=days[0], exit_day=days[1], status_day=days[1])
    acts = [dict(round_id=rid, sid=sid, window='2022', arm=arm, day=days[0], side='buy_core', q=100, price=10, fee=5),
            dict(round_id=rid, sid=sid, window='2022', arm=arm, day=days[0], side='buy_add', q=100, price=10, fee=5),
            dict(round_id=rid, sid=sid, window='2022', arm=arm, day=days[1], side='sell_all', q=200, price=12, fee=5)]
    engine = NS(rounds=[rd], actions=acts, claims={}, END=days[1],
        archives={rid:dict(owner_lane=lane, cash=Decimal('385'), receivable=Decimal(0))},
        ev=pd.DataFrame([dict(event_id='event1',sid=sid,day=days[0],I_qualified=True,PVR_score=5, original_extra='unchanged')]),
        raw={sid:{d:dict(raw_open=12,raw_high=12,raw_low=12,raw_close=12) for d in days}},
        getmeta=lambda *a: (None,None,None), fee=lambda *a: Decimal(5),
        local_actions=lambda sid:dict(coverage_evidence=[dict(path='fiction',sha256='fixture')],events=[],unresolved=[]),
        read=lambda path:dict(records=[{'fiction': True}]), sha=lambda path:'fixture', EVENT_AT={})
    return engine


class AdapterTests(unittest.TestCase):
    def compare(self, b=None, j=None):
        b = b or fixture()
        j = j or NS(s=fixture('PRICE','A_UNION_B_PLUS_PRICE'),arm='A_UNION_B_PLUS_PRICE',
                       offer_audit=[dict(owner_lane='PRICE',PVR_known=False,result='APPLICATION')],price_audit=[],books={})
        return build_comparison(b,j,['FICTION','ZERO'],'2022',expected_roster_size=2,winners=[],market_receipts=[])

    def test_full_cash_and_independent_core(self):
        r = self.compare()
        self.assertEqual(len(r['lane_rows']),8)
        self.assertTrue(r['permit_exact_verified'])
        self.assertEqual(len(r['closed_round_reconciliation']),2)
        self.assertEqual(r['core_independent_dated_fee_diagnostics'][0]['closed_net'],190)
        self.assertEqual(r['lane_rows'][0]['known_total_pnl'],385)
        self.assertEqual(next(x for x in r['pvr_stage_diagnostics'] if x['lane']=='PRICE' and x['stage']=='APPLICATION' and x['pvr_group']=='UNKNOWN')['count'],1)
        self.assertEqual(r['differences'][0]['lane_contributions'],{'AB':-385,'PRICE':385})

    def test_permits_compare_original_extra_fields(self):
        j=NS(s=fixture('PRICE','A_UNION_B_PLUS_PRICE'),arm='A_UNION_B_PLUS_PRICE')
        j.s.ev.loc[0,'original_extra']='changed'
        r=self.compare(j=j)
        self.assertFalse(r['permit_exact_verified'])

    def test_missing_rights_source_never_covered(self):
        b=fixture();b.local_actions=lambda sid:dict(events=[])
        r=self.compare(b=b)
        row=next(x for x in r['lane_rows'] if x['sid']=='FICTION' and x['arm']=='baseline' and x['lane']=='AB')
        self.assertFalse(row['financial_covered'])
        self.assertIn('NO_RIGHTS_SOURCE',row['coverage_reason'])

    def test_unknown_does_not_get_endpoint(self):
        b=fixture();b.rounds[0]['status']='UNKNOWN_RAW';b.actions=b.actions[:2]
        r=self.compare(b=b)
        row=next(x for x in r['lane_rows'] if x['sid']=='FICTION' and x['arm']=='baseline' and x['lane']=='AB')
        self.assertIsNone(row['known_total_pnl'])
        self.assertEqual(row['remaining_cost'],2010)

    def test_open_combined_fee_once(self):
        b=fixture();b.rounds[0]['status']='OPEN_CENSORED_AT_END';b.actions=b.actions[:2]
        b.archives['r1']['last_known_mark_day']=b.END
        r=self.compare(b=b)
        marks=[m for m in r['terminal_marks'] if m['arm']=='baseline']
        self.assertEqual(sum(m['estimated_dated_sell_fee'] for m in marks),5)
        self.assertEqual(len(marks),2)

    def test_cash_mismatch_fails(self):
        b=fixture();b.archives['r1']['cash']=0
        with self.assertRaisesRegex(ValueError,r'cash\+receivable mismatch'):
            self.compare(b=b)

    def test_unadmitted_quantity_fails(self):
        b=fixture();b.actions[0]['quantity_factor']=2
        with self.assertRaisesRegex(ValueError,'UNADMITTED'):
            self.compare(b=b)

    def test_all_actions_posterior_flags(self):
        r=self.compare()
        self.assertEqual(len(r['normalized_actions']),8)
        self.assertTrue(all(a['one_price_hl'] and a['one_price_ohlc'] for a in r['normalized_actions']))
        self.assertFalse(r['comparison_release_ready'])

    def test_fixed_1709_denominator(self):
        roster=['FICTION']+['ZERO'+str(i) for i in range(1708)]
        r=build_comparison(fixture(),NS(s=fixture('PRICE','A_UNION_B_PLUS_PRICE'),arm='A_UNION_B_PLUS_PRICE'),roster,'2022',winners=[],market_receipts=[])
        self.assertEqual(len(r['stock_rows']),3418)
        self.assertTrue(all(x['fixed_denominator']==1709 for x in r['summary']))

    def test_native_permit_nan_mask(self):
        b=fixture();j=fixture('PRICE','A_UNION_B_PLUS_PRICE')
        b.ev['original_missing']=float('nan');j.ev['original_missing']=float('nan')
        self.assertTrue(self.compare(b=b,j=NS(s=j,arm='A_UNION_B_PLUS_PRICE'))['permit_exact_verified'])
        j.ev['original_missing']=0
        self.assertFalse(self.compare(b=b,j=NS(s=j,arm='A_UNION_B_PLUS_PRICE'))['permit_exact_verified'])

    def test_retained_ab_exact(self):
        j=fixture('AB','A_UNION_B_PLUS_PRICE')
        r=self.compare(j=NS(s=j,arm='A_UNION_B_PLUS_PRICE'))
        self.assertTrue(r['retained_ab_path_exact'][0]['actions_exact'])

    def test_active_pending_not_false_zero(self):
        j=fixture('PRICE','A_UNION_B_PLUS_PRICE')
        pending=dict(sid='ZERO',round_id='pending',state='BUY_PENDING',owner_lane='PRICE')
        r=self.compare(j=NS(s=j,arm='A_UNION_B_PLUS_PRICE',states={'ZERO':pending}))
        row=next(x for x in r['lane_rows'] if x['sid']=='ZERO' and x['lane']=='PRICE' and x['arm']=='joint')
        self.assertIsNone(row['known_total_pnl'])

    def test_known_no_submit_round_equals_true_zero(self):
        b=fixture();b.actions=[];b.archives['r1']={}
        b.rounds[0]['status']='PRECHECK_Q0_NO_SUBMIT';b.rounds[0]['entry_day']=None
        r=self.compare(b=b)
        rs=[x for x in r['lane_rows'] if x['arm']=='baseline' and x['lane']=='AB']
        self.assertTrue(all(x['status']=='NEVER_ENTERED' and x['known_total_pnl']==0 and x['comparable'] for x in rs))

    def test_industry_delay_and_left_truncation(self):
        rows=[]
        for day,passed in [('2001-01-01',False),('2001-01-03',True)]:
            rows.append(dict(sid='FICTION',identity='fiction',root_day='2001-01-01',day=day,born=day=='2001-01-01',
                sector_known=True,sector_observed_today=True,sector_rs_ready_fresh=True,sector_up=passed))
        r=industry_delay_diagnostics(rows,pd.date_range('2001-01-01','2001-01-03'),'2022')
        self.assertEqual(r[0]['industry_delay_sessions'],2)
        r=industry_delay_diagnostics(rows[1:],pd.date_range('2001-01-01','2001-01-03'),'2022')
        self.assertTrue(r[0]['left_truncated'])
        self.assertIsNone(r[0]['industry_delay_sessions'])

    def test_ab_raw_application_not_false_zero(self):
        r=self.compare()
        self.assertEqual(sum(x['count'] for x in r['pvr_stage_diagnostics'] if x['lane']=='AB' and x['stage']=='APPLICATION'),1)
        self.assertTrue(any(x['source']=='ORIGINAL_RAW_AB_PERMIT' for x in r['request_execution_identity_join']))

    def test_holding_sessions_actual_calendar(self):
        b=fixture();b.cal=pd.date_range('2001-01-01','2001-01-02')
        r=self.compare(b=b)
        d=next(x for x in r['round_risk_holding_diagnostics'] if x['arm']=='baseline')
        self.assertEqual(d['holding_sessions'],2)
        self.assertFalse(d['net_loss_above_3000'])
        self.assertEqual(d['gap_status'],'UNKNOWN_NO_FROZEN_EXIT_PROTECTION')

    def test_after_birth_window_add_gets_own_receipt(self):
        j=fixture('PRICE','A_UNION_B_PLUS_PRICE')
        audit=[dict(round_id='r1',sid='FICTION',day='2002-01-02',role='ADD',
            event='PROXY_FULL_FILL_NOT_ACTUAL',receipt_id="(('FICTION','source','2001-01-01'),'2002-01-01')")]
        r=self.compare(j=NS(s=j,arm='A_UNION_B_PLUS_PRICE',price_audit=audit,offer_audit=[],books={}))
        row=next(x for x in r['request_execution_identity_join'] if x['lane']=='PRICE')
        self.assertEqual(row['execution_roles'],['ADD'])
        self.assertFalse(row['consumes_initial_slot'])
        self.assertFalse(row['add_consumes_initial_slot'])
        self.assertEqual(row['signal_day'],'2002-01-01 00:00:00')


if __name__=='__main__':
    unittest.main()
