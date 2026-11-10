"""Non-economic G1 frozen inputs, physical market prefix, and OPEN isolation tests."""
import hashlib
import json
import unittest
import numpy as np
import pandas as pd
from market_adapter import MarketAdapter, FROZEN, OPEN_COLUMNS, SECTOR_FIELDS, open_projection


class MarketInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.a = MarketAdapter()

    def test_expected_source_plan_guard(self):
        from pathlib import Path
        from unittest.mock import patch
        path = Path(__file__).resolve()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.assertEqual(MarketAdapter()._source(path), path)
        allowed = MarketAdapter(expected_sources={str(path): digest})
        self.assertEqual(allowed._source(path, digest), path)
        allowed.verify_sources()
        with self.assertRaisesRegex(ValueError, 'UNPLANNED_SOURCE'):
            MarketAdapter(expected_sources={})._source(path)
        with self.assertRaisesRegex(ValueError, 'PLANNED_SOURCE_HASH_MISMATCH'):
            MarketAdapter(expected_sources={str(path): '0' * 64})._source(path)
        with self.assertRaisesRegex(ValueError, 'SOURCE_EXPECTATION_CONFLICT'):
            allowed._source(path, '0' * 64)
        with patch.object(Path, 'read_bytes', return_value=b'changed after first read'):
            with self.assertRaisesRegex(ValueError, 'PLANNED_SOURCE_HASH_MISMATCH'):
                allowed._source(path)
        with self.assertRaisesRegex(ValueError, 'UNPLANNED_SOURCE'):
            allowed._merge_sources({str(path.parent / 'not_in_plan'): digest})
        with self.assertRaisesRegex(ValueError, 'PLANNED_SOURCE_HASH_MISMATCH'):
            allowed._merge_sources({str(path): '0' * 64})

    def test_open_isolation(self):
        day = pd.Timestamp('2024-09-23')
        data = dict(raw_open=10., adjustment_factor=1., source_kind='synthetic',
                    source_path='input', segment_id=0, high=12., low=9., close=11.,
                    amount=1., raw_volume=1., price_valid=True, volume_eligible=True,
                    phase='CONFIRMED', failed=False, root_id='old', S_new=9.)
        raw = pd.DataFrame([data], index=[day])
        expected = open_projection(raw, 'SYN', day)
        for changes in [dict(high=-100., low=999., close=-1., amount=np.nan, raw_volume=0.,
                             price_valid=False, volume_eligible=False, phase='FAILED', failed=True,
                             root_id='changed', S_new=123.),
                        dict(phase='CONFIRMED', failed=False, root_id='NEW_ROOT')]:
            changed = raw.copy()
            for k, v in changes.items():
                changed[k] = v
            self.assertEqual(expected, open_projection(changed, 'SYN', day))
        a = MarketAdapter()
        a.open('300666.SZ', '2025-12-16')
        self.assertEqual(a._market, {})
        self.assertEqual(a._native, {})
        self.assertEqual(tuple(a._opens['300666.SZ'].columns), OPEN_COLUMNS)

    def test_continuous_and_frozen_exact(self):
        fields = ['root_day', 'born', 'active', 'failed', 'root_unknown', 'phase', 'S_old', 'S_new',
                  'confirmed_at', 'confirmed_now', 'new_frontier', 'receipt', 'volume_credit_known',
                  'a_day', 'U', 'B', 'R', 'e0_raised']
        for sid in ['300666.SZ', '002583.SZ', '300085.SZ']:
            full = self.a.load_sid(sid)
            for year in [2023, 2025]:
                self.assertGreater(int((full.index.year == year).sum()), 200)
            frozen = pd.read_parquet(FROZEN / 'DAILY_STATES.parquet', filters=[('sid', '==', sid)]).set_index('day')
            pd.testing.assert_frame_equal(full.loc[frozen.index, fields], frozen[fields],
                                          check_exact=True, check_dtype=False, check_freq=False)
            pd.testing.assert_series_equal(full.loc[frozen.index, 'market_credit_Q'], frozen.Q,
                                           check_exact=True, check_dtype=False, check_names=False)
            pd.testing.assert_series_equal(full.loc[frozen.index, 'market_frontier_F'], frozen.F,
                                           check_exact=True, check_dtype=False, check_names=False)
            for cut in ['2023-06-30', '2025-12-17']:
                prefix = self.a.load_sid(sid, cut=cut)
                pd.testing.assert_frame_equal(full.loc[prefix.index], prefix, check_exact=True, check_freq=False)

    def test_native_and_sealed_named_cases(self):
        cases = [('002583.SZ', '2024-09-20', False), ('002583.SZ', '2024-09-23', True),
                 ('300085.SZ', '2024-09-19', True), ('300666.SZ', '2022-06-06', True),
                 ('300666.SZ', '2024-09-27', True), ('300666.SZ', '2025-12-15', True),
                 ('300666.SZ', '2025-12-17', True)]
        for sid, day, expected in cases:
            qualification = self.a.qualification(sid, day)
            direct = self.a.native_industry(sid, day)
            for c in SECTOR_FIELDS:
                self.assertEqual(qualification[c], direct[c])
            self.assertEqual(all(qualification[c] is True for c in SECTOR_FIELDS), expected)
        native = self.a.native_industry('300666.SZ', '2025-12-17', cut='2025-12-17')
        self.assertEqual(native, self.a.native_industry('300666.SZ', '2025-12-17'))

    def test_cut_rejection_and_native_call_order(self):
        for day in ['2024-09-23', '2025-12-17']:
            with self.assertRaisesRegex(ValueError, 'DAY_AFTER_INPUT_CUT'):
                self.a.qualification('002583.SZ', day, cut='2023-01-01')
        expected = self.a.qualification('002583.SZ', '2024-09-23')
        direct_cut = self.a.native_industry('002583.SZ', '2024-09-23', cut='2024-09-23')
        for c in SECTOR_FIELDS:
            self.assertEqual(expected[c], direct_cut[c])
        self.a.native_industry('300666.SZ', '2025-12-17', cut='2025-12-17')
        self.assertEqual(direct_cut, self.a.native_industry('002583.SZ', '2024-09-23', cut='2024-09-23'))
        for env in self.a._native.values():
            dates, symbols, scores = env['b']._h1_cache
            self.assertLessEqual(len(symbols), 2)
            self.assertEqual(scores.shape[1], len(symbols))

    def test_detached_public_results_and_lru_exact(self):
        a = MarketAdapter(native_cache_limit=1)
        sid, day = '300666.SZ', '2025-12-17'
        before = a.close(sid, day)
        returned = a.load_sid(sid)
        returned.loc[pd.Timestamp(day), 'S_new'] = -1000
        returned.loc[pd.Timestamp(day), 'root_id'] = None
        before['S_new'] = -2000
        before['root_id'] = None
        actual = a.close(sid, day)
        expected = self.a.close(sid, day)
        pd.testing.assert_series_equal(pd.Series(actual), pd.Series(expected), check_exact=True)
        first = a.native_industry(sid, day)
        a.native_industry('002583.SZ', '2024-09-23')
        self.assertEqual(len(a._native), 1)
        self.assertNotIn((sid, pd.Timestamp('2026-06-30')), a._native)
        after_eviction = a.native_industry(sid, day)
        self.assertEqual(first, after_eviction)
        self.assertEqual(len(a._native), 1)
        # The close fast path must not call the copying public load method.
        def forbidden(*args, **kwargs):
            raise AssertionError('close copied public full frame')
        a.load_sid = forbidden
        self.assertEqual(a.close(sid, day)['S_new'], expected['S_new'])

    def test_continuous_qualification_exact_and_no_rebuild(self):
        a = MarketAdapter(native_cache_limit=1)
        sid = '300666.SZ'
        for day in ['2023-06-30', '2024-05-08', '2025-12-17']:
            cached = a.qualification(sid, day)
            native = a.native_industry(sid, day)
            for c in ['sector', *SECTOR_FIELDS]:
                self.assertEqual(cached[c], native[c])
        cut = pd.Timestamp('2023-06-30')
        short = a._continuous_qualification(sid, cut)
        full = a._continuous_qualification(sid, pd.Timestamp('2026-06-30'))
        pd.testing.assert_frame_equal(short, full.loc[short.index], check_exact=True)
        a._native.clear()
        def forbidden(*args, **kwargs):
            raise AssertionError('qualified missing-window day rebuilt native context')
        a._native_context = forbidden
        for day in full.index[:100]:
            a.qualification(sid, day)
        self.assertEqual(len(a._native), 0)

    def test_root_alias_and_sealed_receipts(self):
        receipts = self.a.sealed_receipts('2024_924')
        sample = receipts[receipts.sid.eq('002583.SZ')]
        full = self.a.load_sid('002583.SZ')
        for r in sample.itertuples():
            current = full.loc[r.day]
            self.assertEqual(r.root_id, current.root_id)
            self.assertEqual(r.receipt_id, current.receipt_id)
            self.assertEqual(r.legacy_receipt_id, current.legacy_receipt_id)
        self.assertEqual(len(receipts), 12723)

    def test_capacity_not_today_volume_gate(self):
        sid = '300666.SZ'
        self.a._setup()
        raw = pd.read_parquet(self.a._raw_path(sid)).loc[:'2026-06-30']
        positive = raw.raw_volume[raw.raw_volume.gt(0)]
        expected = (positive.rolling(20, min_periods=20).mean() * .01).reindex(raw.index).ffill()
        full = self.a.load_sid(sid)
        pd.testing.assert_series_equal(full.capacity, expected.reindex(full.index), check_names=False)
        # No amount/volume_eligible filter was consulted by capacity or CLOSE price validity.
        src = __import__('inspect').getsource(MarketAdapter.load_sid)
        self.assertNotIn('volume_eligible', src)


if __name__ == '__main__':
    unittest.main(verbosity=2)
