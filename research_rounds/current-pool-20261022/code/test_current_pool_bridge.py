"""Meaningful bridge-boundary tests; synthetic data, zero economic accounts."""
import copy
from datetime import datetime, date
import json
from pathlib import Path
import tempfile
import unittest
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import current_pool_bridge as bridge

TZ = ZoneInfo('Asia/Shanghai')


def raw_frame(n=300):
    dates = pd.bdate_range('2013-01-02', periods=n)
    close = 10 + np.arange(n) * .025 + np.sin(np.arange(n) / 7) * .4
    return pd.DataFrame({'open': close, 'high': close * 1.01, 'low': close * .99,
                         'close': close, 'volume': 1000 + np.arange(n) % 23 * 200,
                         'amount': close * 1000}, index=pd.DatetimeIndex(dates, name='date'))


def record(sid='A', kind='stock', method='theoretical_ex_price'):
    return dict(series_id=sid, kind=kind, status='ready', currency='CNY',
                source_start='2013-01-02', volume_unit='shares', price_adjustment='raw',
                close_available_time='15:05:00', adjustment={'method': method})


def fixture(directory, blocked=True):
    raw = raw_frame()
    raw.to_parquet(directory / 'raw.parquet')
    actions = {'series_id': 'A', 'currency': 'CNY', 'status': 'reviewed_terms',
               'coverage_evidence': 'synthetic fixture, deliberately no distribution',
               'unresolved': [], 'events': []}
    (directory / 'actions.json').write_text(json.dumps(actions))
    ref = lambda p: {'path': p, 'sha256': bridge.sha256(directory / p)}
    a = record()
    a['raw'] = ref('raw.parquet')
    a['adjustment']['actions'] = ref('actions.json')
    i = record('I', 'sector_index', 'unadjusted_index')
    i['raw'] = ref('raw.parquet')
    series = [a, i]
    lines = [dict(security_id='A', market='A', issuer_id='ISSUER-A', sector_id='G',
                  company_cap_cny=20e9, current_stock=True)]
    if blocked:
        series.append(dict(series_id='H', kind='stock', status='pending',
                           blocked_reason='HK normalized distribution terms unresolved'))
        lines.append(dict(security_id='H', market='H', issuer_id='ISSUER-H', sector_id='G',
                          company_cap_cny=20e9, current_stock=True, southbound_selected=True))
    selection = dict(snapshot_id='TEST-ONLY', observed_at='2026-10-22T23:00:00+08:00',
                     source_id='synthetic_fixture', lines=lines)
    (directory / 'selection.json').write_text(json.dumps(selection))
    manifest = dict(schema_version=1, scope_date='2026-10-22',
                    research_basis=bridge.RESEARCH_BASIS, upstream_sha256={
                        name: bridge.sha256(path) for name, path in bridge.UPSTREAM.items()},
                    selection=ref('selection.json'), series=series, sector_series={'G': 'I'})
    path = directory / 'manifest.json'
    path.write_text(json.dumps(manifest))
    return path, manifest


class BridgeTests(unittest.TestCase):
    def test_split_coordinates_and_volume_units(self):
        raw = raw_frame()
        when = raw.index[100]
        raw.loc[when:, list(bridge.OHLC)] /= 2
        raw.loc[when:, 'volume'] *= 2
        signal = bridge.prepare_signal(raw, record(), [dict(effective_date=str(when.date()),
            cash_per_old_share='0', split_ratio='2', source_id='fixture-split')])
        pd.testing.assert_series_equal(signal.close, raw_frame().close, check_names=False)
        np.testing.assert_array_equal(signal.volume, raw_frame().volume)
        self.assertEqual(signal.adjustment_factor.iloc[99], 1)
        self.assertEqual(signal.adjustment_factor.iloc[100], 2)

    def test_action_only_factors_and_exact_prefix(self):
        raw = raw_frame()
        event = dict(effective_date=str(raw.index[100].date()), cash_per_old_share='0.2',
                     split_ratio='1', source_id='fixture-cash')
        full = bridge.prepare_signal(raw, record(), [event])
        self.assertEqual(full.adjustment_factor.iloc[100:].nunique(), 1)
        for n in (70, 100, 120, 280):
            prefix = bridge.prepare_signal(raw.iloc[:n], record(), [event])
            pd.testing.assert_frame_equal(prefix, full.iloc[:n], check_exact=True, check_freq=False)

    def test_nonobserved_action_never_becomes_market_observation(self):
        raw = raw_frame()
        when = raw.index[100]
        raw = raw.drop(when)
        event = dict(effective_date=str(when.date()), cash_per_old_share='0.2',
                     split_ratio='1', source_id='fixture')
        signal = bridge.prepare_signal(raw, record(), [event])
        self.assertTrue(signal.loc[when, 'synthetic_event_bar'])
        eligible, _, _, _ = bridge.state_frame(signal)
        self.assertNotIn(when, eligible.index)
        self.assertTrue(pd.isna(signal.loc[when, 'raw_close']))

    def test_origin_action_rejected(self):
        event = dict(effective_date='2013-01-02', cash_per_old_share='1', split_ratio='1')
        with self.assertRaisesRegex(ValueError, 'Origin-date'):
            bridge.prepare_signal(raw_frame(), record(), [event])

    def test_missing_volume_keeps_price_clock_invalid_geometry_does_not(self):
        raw = raw_frame()
        missing_volume, bad_geometry = raw.index[100], raw.index[150]
        raw.loc[missing_volume, 'volume'] = np.nan
        raw.loc[bad_geometry, 'high'] = raw.loc[bad_geometry, 'low'] * .5
        signal = bridge.prepare_signal(raw, record(), [])
        eligible, _, states, _ = bridge.state_frame(signal)
        self.assertIn(missing_volume, eligible.index)
        self.assertIn(missing_volume, states.index)
        self.assertTrue(pd.isna(eligible.loc[missing_volume, 'volume']))
        self.assertNotIn(bad_geometry, eligible.index)

    def test_false_string_observation_flag_not_truthy(self):
        raw = raw_frame()
        raw['observed_bar'] = 'True'
        raw.loc[raw.index[100], 'observed_bar'] = 'False'
        signal = bridge.prepare_signal(raw, record(), [])
        eligible, _, _, _ = bridge.state_frame(signal)
        self.assertNotIn(raw.index[100], eligible.index)

    def test_stock_cannot_inherit_index_raw_policy(self):
        with self.assertRaisesRegex(ValueError, 'cannot be assigned'):
            bridge.read_actions(record(method='unadjusted_index'), Path('.'))

    def test_index_source_units_never_relax_stock_share_units(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'raw.parquet'
            raw_frame().to_parquet(path)
            index = record('I', 'sector_index', 'unadjusted_index')
            index['volume_unit'] = 'source_index_units'
            self.assertEqual(len(bridge.read_raw(path, index)), 300)
            index['kind'] = 'stock'
            with self.assertRaisesRegex(ValueError, 'share volume'):
                bridge.read_raw(path, index)

    def test_raw_unit_and_origin_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'raw.parquet'
            raw_frame().to_parquet(path)
            bad = record()
            bad['volume_unit'] = 'hands'
            with self.assertRaisesRegex(ValueError, 'share volume'):
                bridge.read_raw(path, bad)
            bad = record()
            bad['source_start'] = '2013-01-03'
            with self.assertRaisesRegex(ValueError, 'origin mismatch'):
                bridge.read_raw(path, bad)

    def test_empty_rights_needs_coverage_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            path, manifest = fixture(Path(temp))
            action = Path(temp) / 'actions.json'
            obj = json.loads(action.read_text())
            obj['coverage_evidence'] = ''
            action.write_text(json.dumps(obj))
            manifest['series'][0]['adjustment']['actions']['sha256'] = bridge.sha256(action)
            path.write_text(json.dumps(manifest))
            bundle = bridge.load_bundle(path, technical_sample=True, materialize=True)
            self.assertIn('coverage evidence', bundle.series['A'].blocked_reason)
            self.assertEqual(len(bundle.lines), 2)

    def test_missing_and_changed_sources_preserve_lines(self):
        with tempfile.TemporaryDirectory() as temp:
            path, manifest = fixture(Path(temp))
            manifest['series'][0]['raw']['sha256'] = '0' * 64
            path.write_text(json.dumps(manifest))
            bundle = bridge.load_bundle(path, technical_sample=True, materialize=True)
            self.assertEqual(set(bundle.series), {'A', 'H', 'I'})
            self.assertIn('changed input', bundle.series['A'].blocked_reason)
            self.assertIn('unresolved', bundle.series['H'].blocked_reason)
            self.assertFalse(bundle.signal_ready)

    def test_production_closeout_and_upstream_hash_required(self):
        with tempfile.TemporaryDirectory() as temp:
            path, manifest = fixture(Path(temp), blocked=False)
            with self.assertRaises(KeyError):
                bridge.load_bundle(path)
            manifest['upstream_sha256']['numeric'] = '0' * 64
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, 'upstream changed'):
                bridge.load_bundle(path, technical_sample=True)

    def test_states_match_frozen_algorithm_and_prefix(self):
        raw = raw_frame()
        full = bridge.prepare_signal(raw, record(), [])
        _, events, states, _ = bridge.state_frame(full)
        expected_events = bridge.event_frame_numeric(full.close, full.volume, joint=True, event_exit=False)
        pd.testing.assert_frame_equal(events, expected_events)
        for n in (70, 160, 299):
            _, _, prefix, _ = bridge.state_frame(full.iloc[:n])
            pd.testing.assert_frame_equal(prefix, states.iloc[:n], check_exact=True, check_freq=False)
        self.assertEqual(states.rs.iloc[-1], bridge.admission.rs_score(full.close.iloc[-253:].tolist()))

    def test_actual_observation_clock_and_unknown_retention(self):
        with tempfile.TemporaryDirectory() as temp:
            path, _ = fixture(Path(temp))
            bundle = bridge.load_bundle(path, technical_sample=True, materialize=True)
            d = raw_frame().index[-1].date()
            clock = bridge.admission.Clock(datetime.combine(d, datetime.min.time(), TZ).replace(hour=16),
                datetime.combine(d, datetime.min.time(), TZ).replace(hour=17), d)
            market = {sid: bridge.admission.Fact(True, clock.decision_at, clock.decision_at)
                      for sid in ('A', 'H')}
            observed = bundle.at_decision(clock, market_buyable=market)
            a, h = observed.historical
            self.assertIsNotNone(a.rank.read(clock))
            self.assertIsNone(h.trend_up.read(clock))
            self.assertEqual(observed.evidence.observed_at.year, 2026)
            preclose = bridge.admission.Clock(clock.decision_at.replace(hour=14),
                                               clock.earliest_execution_at, d)
            early = bundle.at_decision(preclose, market_buyable=market)
            self.assertLess(early.historical[0].rank.observation_at.date(), d)
            self.assertIsNone(early.historical[0].rank.read(preclose))
            with self.assertRaisesRegex(ValueError, 'every fixed line'):
                bundle.at_decision(clock, market_buyable={'A': market['A']})

    def test_declared_source_gap_resets_warmup_and_has_unknown_interval(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path, manifest = fixture(directory, blocked=False)
            raw = raw_frame()
            raw.index = raw.index[:150].append(raw.index[150:] + pd.Timedelta(days=1000))
            raw.to_parquet(directory / 'raw.parquet')
            for item in manifest['series']:
                item['raw']['sha256'] = bridge.sha256(directory / 'raw.parquet')
                item['segments'] = [
                    {'start': str(raw.index[0].date()), 'end': str(raw.index[149].date()), 'reason': 'before source gap'},
                    {'start': str(raw.index[150].date()), 'end': str(raw.index[-1].date()), 'reason': 'source resumes; warmup reset'}]
            path.write_text(json.dumps(manifest))
            bundle = bridge.load_bundle(path, technical_sample=True, materialize=True)
            self.assertIsNone(bundle.series['A'].blocked_reason)
            self.assertEqual(bundle.series['A'].states.loc[raw.index[150], 'ready'], 0)
            self.assertTrue(pd.isna(bundle.series['A'].states.loc[raw.index[-1], 'rs']))
            d = (raw.index[149] + pd.Timedelta(days=10)).date()
            at = datetime.combine(d, datetime.min.time(), TZ).replace(hour=16)
            clock = bridge.admission.Clock(at, at.replace(hour=17), d)
            inputs = bundle.at_decision(clock, market_buyable={'A': bridge.admission.Fact(True, at, at)})
            self.assertIsNone(inputs.historical[0].trend_up.read(clock))

    def test_streamed_output_reload_and_tamper_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            path, _ = fixture(directory)
            bundle = bridge.load_bundle(path, technical_sample=True)
            self.assertTrue(all(x.states is None for x in bundle.series.values()))
            summary = bridge.write_bundle(bundle, directory / 'output')
            self.assertEqual(summary['accounts_run'], 0)
            self.assertFalse(summary['signal_ready'])
            bridge.load_prepared_states(bundle, directory / 'output')
            self.assertEqual(list(bundle.series['A'].states.columns), ['ready', 'target', 'rs', 'segment_id'])
            self.assertIn('unresolved', bundle.series['H'].blocked_reason)
            state_path = directory / 'output' / summary['series'][0]['files']['states']['path']
            with state_path.open('ab') as f:
                f.write(b'tamper')
            with self.assertRaisesRegex(ValueError, 'changed input'):
                bridge.load_prepared_states(bundle, directory / 'output')


if __name__ == '__main__':
    unittest.main(verbosity=2)
