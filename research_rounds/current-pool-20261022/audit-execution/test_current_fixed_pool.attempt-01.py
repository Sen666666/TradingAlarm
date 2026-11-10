"""Synthetic selection-clock tests; no prices, accounts or network."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

import sector_stock_admission as admission
from current_fixed_pool import (SelectionEvidence, PoolLine, SelectionFact,
                                HistoricalInputs, build_security, decide_current_pool)

UTC = timezone.utc
PAST = datetime(2020, 1, 2, 9, tzinfo=UTC)
TODAY = datetime(2026, 10, 22, 9, tzinfo=UTC)
CLOCK = admission.Clock(PAST, PAST + timedelta(days=1), PAST.date())
EVIDENCE = SelectionEvidence('synthetic-current-pool', 'a' * 64, TODAY, 'synthetic-only')


def fact(value, **kw):
    return admission.Fact(value, PAST, PAST, source_id='synthetic-market', **kw)


def line(sid='A', **kw):
    values = dict(security_id=sid, market='A', issuer_id=sid, sector_id='G',
                  company_cap_cny=20e9, current_stock=True)
    values.update(kw)
    return PoolLine(**values)


def history(sid='A', **kw):
    values = dict(security_id=sid, common_ready=fact(True), market_buyable=fact(True),
                  trend_up=fact(True), rank=admission.Rank(.5, PAST, PAST))
    values.update(kw)
    return HistoricalInputs(**values)


def run(lines=None, historical=None, **kw):
    values = dict(evidence=EVIDENCE, lines=lines if lines is not None else [line()],
                  historical=historical if historical is not None else [history()],
                  clock=CLOCK, variant='S0', bootstrap=True,
                  sectors=[admission.Sector('G', fact(True), admission.Rank(.5, PAST, PAST))])
    values.update(kw)
    return decide_current_pool(**values)


class CurrentPoolTests(unittest.TestCase):
    def test_explicit_current_choice_and_label_without_backdating(self):
        result = run()
        self.assertEqual(result.decision.selected, ('A',))
        self.assertEqual(result.research_basis, 'current_pool_historical_development')
        self.assertEqual(result.evidence.observed_at, TODAY)
        self.assertEqual(result.evidence.snapshot_sha256, 'a' * 64)
        s = build_security(line(), history(), EVIDENCE)
        self.assertEqual(s.company_cap_cny.evidence.observed_at, TODAY)
        self.assertFalse(hasattr(s.company_cap_cny, 'known_at'))

    def test_original_snapshot_guard_unchanged(self):
        original = admission.Fact('G', TODAY, TODAY, observed_at=TODAY, basis='snapshot')
        self.assertIsNone(original.read(CLOCK))
        self.assertIsNone(original.read(CLOCK, for_execution=True))

    def test_fixed_cap_boundary_and_unknown(self):
        self.assertFalse(run([line(company_cap_cny=10e9)]).decision.eligibility[0].q)
        self.assertTrue(run([line(company_cap_cny=10e9 + 1)]).decision.eligibility[0].q)
        self.assertIsNone(run([line(company_cap_cny=None)]).decision.eligibility[0].q)

    def test_current_hk_selection_not_historical_southbound_chain(self):
        h = line(market='H', southbound_selected=True)
        self.assertEqual(run([h]).decision.selected, ('A',))
        self.assertFalse(run([replace(h, southbound_selected=False)]).decision.eligibility[0].q)
        self.assertIsNone(run([replace(h, southbound_selected=None)]).decision.eligibility[0].q)

    def test_current_stock_flag_does_not_create_prelisting_availability(self):
        self.assertEqual(run(historical=[history(market_buyable=fact(False))]).decision.selected, ())
        future_listing = admission.Fact(True, TODAY, TODAY, source_id='future-listing')
        r = run(historical=[history(market_buyable=future_listing)])
        self.assertIsNone(r.decision.eligibility[0].q)

    def test_future_signals_and_unknown_coverage_remain_unknown(self):
        future = replace(fact(True), known_at=PAST + timedelta(seconds=1))
        self.assertIsNone(run(historical=[history(trend_up=future)]).decision.eligibility[0].q)
        for variant in ('T0', 'T1', 'S0'):
            self.assertIsNone(run(historical=[history(common_ready=fact(None))],
                                  variant=variant).decision.eligibility[0].q)

    def test_selection_types_cannot_replace_dynamic_facts_or_rank(self):
        static = SelectionFact('issuer_id', 'A', EVIDENCE)
        with self.assertRaises(ValueError):
            history(trend_up=static)
        with self.assertRaises(ValueError):
            history(market_buyable=static)
        with self.assertRaises(ValueError):
            history(rank=static)
        with self.assertRaises(ValueError):
            run(sectors=[admission.Sector('G', static)])
        with self.assertRaises(ValueError):
            SelectionFact('trend_up', True, EVIDENCE)

    def test_future_rank_stays_unavailable_and_fallback_is_preserved(self):
        r = run([line('A'), line('B')],
                [history('A'), history('B', rank=admission.Rank(99, TODAY, TODAY))])
        self.assertEqual(r.decision.selected, ('A', 'B'))
        self.assertIn('waiting:G', r.decision.ranking_fallbacks)

    def test_ah_issuer_dedup_uses_fixed_identity(self):
        r = run([line('A', issuer_id='company'),
                 line('H', market='H', issuer_id='company', southbound_selected=True)],
                [history('A'), history('H')])
        self.assertEqual(r.decision.selected, ('A',))
        self.assertIn(('H', 'issuer_already_occupied'), r.decision.rejected)

    def test_missing_lines_and_untraceable_evidence_rejected(self):
        with self.assertRaises(ValueError):
            run([line('A'), line('B')], [history('A')])
        with self.assertRaises(ValueError):
            run([line('A')], [history('A'), history('B')])
        with self.assertRaises(ValueError):
            replace(EVIDENCE, snapshot_sha256='')
        with self.assertRaises(ValueError):
            replace(EVIDENCE, observed_at=TODAY.replace(tzinfo=None))


if __name__ == '__main__':
    unittest.main()
