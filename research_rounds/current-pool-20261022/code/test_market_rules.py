"""Synthetic rule mechanics, not assertions that these test versions are real."""
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'sector-stock-20261021/code'))
from market_rules import quantity_version,market_identity_on,sellable_at,a_sellable_at,RuleUnavailable

TZ=ZoneInfo('Asia/Shanghai')
def at(d):return datetime.fromisoformat(d+'T09:30:00').replace(tzinfo=TZ)
def row(**kw):
    return dict({'from':'2024-01-01','to':None,'source_id':'synthetic_test_only','basis':'official_rule','verification_status':'verified'},**kw)
def rule(minimum=100,step=100):
    return dict(rule_id='synthetic_only',buy_minimum=minimum,buy_step=step,sell_step=100,allow_full_exit_odd=True,fill_step=1)


class MarketRulesTest(unittest.TestCase):
    def test_unknown_has_no_default_lot(self):
        with self.assertRaises(RuleUnavailable):quantity_version({},'A','2024-01-02')
    def test_minimum_and_step_remain_distinct(self):
        result=quantity_version({'quantity_versions':{'A':[row(rule=rule(200,1))]}},'A','2024-01-02')
        self.assertEqual(result.quantity.buy_floor(199),0);self.assertEqual(result.quantity.buy_floor(251),251)
    def test_no_current_snapshot_backfill(self):
        with self.assertRaises(RuleUnavailable):quantity_version({'quantity_versions':{'A':[row(rule=rule())]}},'A','2015-01-01')
    def test_proxy_requires_explicit_freeze(self):
        r=row(rule=rule());r.update(basis='explicit_research_proxy',proxy_id='today_lot_backfill')
        m={'quantity_versions':{'A':[r]}}
        with self.assertRaises(RuleUnavailable):quantity_version(m,'A','2024-01-02')
        self.assertEqual(quantity_version(m,'A','2024-01-02',['today_lot_backfill']).status,'explicit_proxy')
    def test_to_is_exclusive_and_versions_cannot_overlap(self):
        first=row(rule=rule());first['to']='2024-02-01';second=row(rule=rule(200,1));second['from']='2024-02-01'
        m={'quantity_versions':{'A':[first,second]}};self.assertEqual(quantity_version(m,'A','2024-02-01').quantity.buy_minimum,200)
        first['to']='2024-02-02'
        with self.assertRaises(ValueError):quantity_version(m,'A','2024-02-01')
    def test_a_t1_skips_weekend(self):
        self.assertEqual(a_sellable_at(at('2024-01-05'),[at('2024-01-05'),at('2024-01-08')]),at('2024-01-08'))
    def test_missing_calendar_never_becomes_next_natural_day(self):
        with self.assertRaises(RuleUnavailable):a_sellable_at(at('2024-01-05'),[at('2024-01-05')])
    def test_explicit_zero_lag_preserves_execution_time(self):
        fill=at('2024-01-05');self.assertEqual(sellable_at(fill,[fill],0),fill)
    def test_neeq_cannot_become_bse_by_current_suffix(self):
        m={'venue_versions':{'920000.BJ':[row(venue='NEEQ')]}}
        with self.assertRaises(RuleUnavailable):market_identity_on(m,'920000.BJ','2024-01-02')
    def test_unknown_bse_listing_stays_unknown(self):
        with self.assertRaises(RuleUnavailable):market_identity_on({},'920000.BJ','2024-01-02')
    def test_global_venue_floor_does_not_create_listing(self):
        m={'venue_not_before':{'BSE':{'from':'2021-11-15','source_id':'synthetic'}},'venue_versions':{'920000.BJ':[row(venue='BSE')]}}
        with self.assertRaises(RuleUnavailable):market_identity_on(m,'920000.BJ','2022-01-01')
    def test_unverified_rule_is_unknown(self):
        r=row(rule=rule());r['verification_status']='pending'
        with self.assertRaises(RuleUnavailable):quantity_version({'quantity_versions':{'A':[r]}},'A','2024-01-02')


if __name__=='__main__':unittest.main(verbosity=2)
