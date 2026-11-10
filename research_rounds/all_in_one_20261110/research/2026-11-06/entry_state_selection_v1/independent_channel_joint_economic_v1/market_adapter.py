"""G1 read-only continuous market facts. Import performs no IO or economics.

OPEN is a physically separate raw-column projection; never calls replay/close.
The native fallback keeps four sector facts only, never old stock admission Q.
No orders, holdings, fees, cash, accounts or strategy returns are evaluated.
"""
from pathlib import Path
import ast
from collections import OrderedDict
import hashlib
import importlib.util
import json
import sys
import textwrap
import threading
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
R = O.parent
FROZEN = R / 'independent_channel_full1709_preflight_v1'
END = pd.Timestamp('2026-06-30')
PROTOCOL_SHA256 = '94965590a1d5ba5fd28e88a6cf6c09188f747663590d2ffa0e3f7858e2265687'
SECTOR_FIELDS = ('sector_known', 'sector_observed_today', 'sector_rs_ready_fresh', 'sector_up')
OPEN_COLUMNS = ('raw_open', 'adjustment_factor', 'source_kind', 'source_path', 'segment_id')
_LOCK = threading.RLock()


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _tri(value):
    return None if pd.isna(value) else bool(value)


def _reasons(value):
    if pd.isna(value):
        return dict.fromkeys(SECTOR_FIELDS)
    reasons = set(str(value).split('|'))
    return {c: None if c + ':unknown' in reasons else False if c + ':false' in reasons else True
            for c in SECTOR_FIELDS}


def canonical_root(sid, source_identity, birthday):
    if pd.isna(birthday) or pd.isna(source_identity):
        return None
    return (sid, str(source_identity), str(pd.Timestamp(birthday).date()))


def open_projection(raw, sid, day):
    """Only whitelist reads are allowed here, including in missing-row handling."""
    day = pd.Timestamp(day)
    z = raw.loc[day, list(OPEN_COLUMNS)].to_dict() if day in raw.index else dict.fromkeys(OPEN_COLUMNS)
    return dict(sid=sid, day=day, known_at=(day, 'OPEN'), raw_open=z['raw_open'],
                factor=z['adjustment_factor'], adjustment_factor=z['adjustment_factor'], source_kind=z['source_kind'],
                source_path=z['source_path'], segment_id=z['segment_id'])


class MarketAdapter:
    def __init__(self, native_cache_limit=8, expected_sources=None):
        if not isinstance(native_cache_limit, int) or native_cache_limit < 1:
            raise ValueError("native_cache_limit must be a positive integer")
        self.native_cache_limit = native_cache_limit
        self.expected_sources = None
        if expected_sources is not None:
            self.expected_sources = {}
            for path, digest in expected_sources.items():
                if not isinstance(digest, str) or len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
                    raise ValueError(('INVALID_PLANNED_SHA256', str(path)))
                key = str(Path(path).resolve())
                if key in self.expected_sources and self.expected_sources[key] != digest:
                    raise ValueError(('CONFLICTING_PLANNED_SOURCE', key))
                self.expected_sources[key] = digest
        self.sources = {}
        self._market = {}
        self._opens = {}
        self._native = OrderedDict()
        self._qual = {}
        self._pvr = {}
        self._continuous_qual = {}
        self._engine = None
        self._core = None

    def _planned_digest(self, path):
        if self.expected_sources is None:
            return None
        key = str(Path(path).resolve())
        if key not in self.expected_sources:
            raise ValueError(('UNPLANNED_SOURCE', key))
        return self.expected_sources[key]

    def _source(self, path, expected=None):
        path = Path(path).resolve()
        planned = self._planned_digest(path)
        if planned is not None and expected is not None and planned != expected:
            raise ValueError(('SOURCE_EXPECTATION_CONFLICT', str(path)))
        # G2 always rehashes, including previously seen paths. G1 retains lazy caching.
        digest = self.sources.get(str(path)) if self.expected_sources is None else None
        if digest is None:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if planned is not None and digest != planned:
            raise ValueError(('PLANNED_SOURCE_HASH_MISMATCH', str(path)))
        if expected is not None and digest != expected:
            raise ValueError(('SOURCE_HASH_MISMATCH', str(path)))
        if str(path) in self.sources and self.sources[str(path)] != digest:
            raise ValueError(('SOURCE_CHANGED', str(path)))
        self.sources[str(path)] = digest
        return path

    def _merge_sources(self, sources):
        """Validate hashes actually collected by frozen loaders before publishing facts."""
        checked = {}
        for path, digest in sources.items():
            key = str(Path(path).resolve())
            planned = self._planned_digest(key)
            if planned is not None and digest != planned:
                raise ValueError(('PLANNED_SOURCE_HASH_MISMATCH', key))
            if key in self.sources and self.sources[key] != digest:
                raise ValueError(('SOURCE_CHANGED', key))
            checked[key] = digest
        self.sources.update(checked)

    def _setup(self):
        if self._engine is not None:
            return
        self._source(O / 'PROTOCOL_DRAFT.md', PROTOCOL_SHA256)
        audit = json.loads(self._source(O / 'INDEPENDENT_CONTRACT_AUDIT.json').read_text())
        if not audit['contract_specification_passed'] or audit['protocol_sha256'] != PROTOCOL_SHA256:
            raise ValueError('SPEC_ONLY_AUDIT_REQUIRED')
        self._core = _load('_joint_frozen_fast_core', self._source(FROZEN / 'fast_core.py'))
        engine = _load('_joint_frozen_market_engine', self._source(FROZEN / 'engine.py'))
        self._merge_sources(engine.S)
        self._engine = engine

    def _raw_path(self, sid):
        self._setup()
        entry = self._engine.manifest[sid]
        path = next(p for p in entry['source_sha256'] if p.endswith('/signal.parquet'))
        return self._source(path, entry['source_sha256'][path])

    def open(self, sid, day):
        """Never loads market replay or native close facts, even on first invocation."""
        if sid not in self._opens:
            self._opens[sid] = pd.read_parquet(self._raw_path(sid), columns=list(OPEN_COLUMNS)).loc[:END]
        return open_projection(self._opens[sid], sid, day)

    def load_sid(self, sid, cut=None):
        """Public detached copy; callers may mutate without changing market facts."""
        return self._cached_market(sid, cut=cut).copy(deep=True)

    def _cached_market(self, sid, cut=None):
        """Private read-only-by-contract view; never return this object externally."""
        self._setup()
        cut = END if cut is None else min(pd.Timestamp(cut), END)
        key = (sid, cut)
        if key in self._market:
            return self._market[key]
        # Original replay resolves `from fast_core import simulate` at call time.
        # Bind it only for this call and restore the previous module afterwards.
        with _LOCK:
            old = sys.modules.get('fast_core')
            sys.modules['fast_core'] = self._core
            try:
                q, x = self._engine.replay(sid, cut=cut)
            finally:
                if old is None:
                    sys.modules.pop('fast_core', None)
                else:
                    sys.modules['fast_core'] = old
        self._merge_sources(self._engine.S)
        cols = ['root_day', 'born', 'active', 'failed', 'root_unknown', 'phase', 'S_old', 'S_new',
                'confirmed_at', 'confirmed_now', 'new_frontier', 'receipt', 'receipt_id',
                'volume_credit_known', 'Q', 'F', 'a_day', 'U', 'B', 'R', 'e0_raised']
        z = x[cols].copy().rename(columns={'receipt_id': 'legacy_receipt_id', 'Q': 'market_credit_Q',
                                         'F': 'market_frontier_F'})
        z['legacy_receipt_id'] = z.legacy_receipt_id.map(lambda v: sid + '|' + v if pd.notna(v) else None)
        for c in ('price_valid', 'raw_close', 'close', 'adjustment_factor', 'source_kind', 'source_path', 'segment_id', 'identity'):
            z[c] = q[c]
        z['factor'] = z.adjustment_factor
        # Capacity follows original raw stream before common-calendar projection.
        # Off-calendar positive-volume observations are not silently discarded.
        raw = pd.read_parquet(self._raw_path(sid), columns=['raw_volume']).loc[:cut]
        vol = raw.raw_volume[raw.raw_volume.gt(0)]
        cap = (vol.rolling(20, min_periods=20).mean() * .01).reindex(raw.index).ffill()
        z['capacity'] = cap.reindex(z.index)
        z['capacity_shares'] = z.capacity
        z['capacity_known'] = np.isfinite(z.capacity)
        z['fresh'] = z.receipt
        z['confirmed'] = z.phase.eq('CONFIRMED')
        roots = {}
        for d in x.index[x.born]:
            row = q.loc[d]
            roots[d] = canonical_root(sid, row.identity, d)
        # On UNKNOWN transition use the old root's birth identity, not today's new source.
        z['root_id'] = [roots.get(d) for d in z.root_day]
        z['legacy_root_id'] = z.root_day.map(lambda d: sid + '|' + str(d.date()) if pd.notna(d) else None)
        z['receipt_id'] = [(rid, str(d.date()))
                           if fresh and isinstance(rid, tuple) else None
                           for d, rid, fresh in zip(z.index, z.root_id, z.fresh)]
        self._market[key] = z
        return z

    def _load_qual(self, sid):
        if sid in self._qual:
            return
        frames = []
        columns = ['sid', 'day', 'sector', 'event_Q_reasons', 'PVR_known', 'PVR_score']
        for path in [R / 'fast_entry_equity_2022_v1/ALL_MARKET_INPUTS_2022.parquet',
                     FROZEN / 'overlap/OLD_NATIVE_Q_EXTENDED.parquet']:
            frame = pd.read_parquet(self._source(path), columns=columns, filters=[('sid', '==', sid)])
            frames.append(frame)
        cache = pd.concat(frames).set_index('day').sort_index()
        if cache.index.has_duplicates:
            raise ValueError('DUPLICATE_NATIVE_INPUT')
        self._qual[sid] = cache

    def _native_context(self, sid, cut):
        key = (sid, cut)
        if key in self._native:
            self._native.move_to_end(key)
            return self._native[key]
        path = self._source(R / 'fast_entry_equity_2022_v1/prepare_inputs.py')
        source = path.read_text()
        env = {'__file__': str(path)}
        exec(compile(source[:source.index('\ndef main():')], str(path) + ':helpers', 'exec'), env)
        node = next(n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name == 'main')
        body = textwrap.dedent('\n'.join(ast.get_source_segment(source, node).splitlines()[1:]))
        setup = body[:body.index('tpath=W/')]
        assert setup.count('keep=set(ids)') == 1
        setup = setup.replace('keep=set(ids)', 'keep={' + repr(sid) + '}')
        exec(compile(setup, str(path) + ':one_stock_native_facts_only', 'exec'), env)
        facts = pd.read_parquet(self._source(env['manifest'][sid]['refs']['facts'])).loc[:cut]
        env['f'].f[sid] = facts
        env['b'].series[sid].states = facts[['e0_ready', 'e0_target', 'segment_id']].rename(
            columns={'e0_ready': 'ready', 'e0_target': 'target'})
        # Physically truncate facts, sector states and H1, not only the output table.
        for sector in env['b'].sector_series:
            ff = env['f'].f[sector].loc[:cut]
            env['f'].f[sector] = ff
            env['b'].series[sector].states = ff[['e0_ready', 'e0_target', 'segment_id']].rename(
                columns={'e0_ready': 'ready', 'e0_target': 'target'})
        dates, symbols, scores = env['b']._h1_cache
        mask = dates <= cut
        kept_symbols = [s for s in env['b'].series if s in symbols]
        columns = [symbols[s] for s in kept_symbols]
        env['b']._h1_cache = (dates[mask], {s: i for i, s in enumerate(kept_symbols)},
                               scores[np.ix_(mask, columns)].copy())
        self._merge_sources(env['SOURCES'])
        # Freeze definition-only import dependencies as the original exporter does.
        # This is a conservative superset when other research modules are imported.
        prefixes = (str(env['RR']), str(env['W']),
                    '/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/')
        for module in list(sys.modules.values()):
            path = getattr(module, '__file__', None)
            if path and str(path).endswith('.py') and str(path).startswith(prefixes):
                self._source(path)
        # Keep only runtime dependencies, not setup manifests/rosters/scratch data.
        # No sector sharing or semantic shortcut: evicted contexts rebuild originally.
        context = {k: env[k] for k in ('b', 'f', 'datetime', 'time', 'TZ', 'native_elig')}
        self._native[key] = context
        while len(self._native) > self.native_cache_limit:
            self._native.popitem(last=False)
        return context

    def native_industry(self, sid, day, cut=None):
        """Native S0 original admission reasons, projected to four fields only."""
        day = pd.Timestamp(day)
        cut = END if cut is None else pd.Timestamp(cut)
        if day > cut:
            raise ValueError('DAY_AFTER_INPUT_CUT')
        env = self._native_context(sid, cut)
        clock, stocks, sectors = env['f'].packet(env['datetime'].combine(
            day.date(), env['time'](15, 10), env['TZ']), 'I')
        stock = next(s for s in stocks if s.security_id == sid)
        eligibility = env['native_elig'](stock, {s.sector_id: s for s in sectors}, clock, 'S0')
        return dict(sector=eligibility.sector_id, **_reasons('|'.join(eligibility.reasons)))

    def _continuous_qualification(self, sid, cut):
        """One original native context per sid/cut, then only exact-day fact lookups.

        All missing fixed common dates are computed without holdings/selection input.
        Future rows are never read by qualification; physical cuts get separate caches.
        """
        key = (sid, cut)
        if key in self._continuous_qual:
            return self._continuous_qual[key]
        self._setup()
        self._load_qual(sid)
        days = self._engine.cal
        days = days[(days >= pd.Timestamp('2022-01-01')) & (days <= cut)]
        days = days[~days.isin(self._qual[sid].index)]
        rows = []
        try:
            for day in days:
                rows.append(dict(day=day, **self.native_industry(sid, day, cut=cut)))
        finally:
            # No daily joint traversal can retain or churn this context.
            self._native.pop(key, None)
        frame = pd.DataFrame(rows, columns=['day', 'sector', *SECTOR_FIELDS]).set_index('day')
        for column in SECTOR_FIELDS:
            frame[column] = frame[column].astype('boolean')
        if frame.index.has_duplicates:
            raise ValueError('DUPLICATE_CONTINUOUS_NATIVE_DAY')
        self._continuous_qual[key] = frame
        return frame

    def qualification(self, sid, day, cut=None):
        day = pd.Timestamp(day)
        if cut is not None and day > pd.Timestamp(cut):
            raise ValueError('DAY_AFTER_INPUT_CUT')
        self._load_qual(sid)
        cache = self._qual[sid]
        if day in cache.index:
            row = cache.loc[day]
            return dict(sector=row.sector, **_reasons(row.event_Q_reasons),
                        PVR_known=_tri(row.PVR_known), PVR_score=row.PVR_score,
                        qualification_source='FROZEN_NATIVE_EXPORT')
        effective_cut = END if cut is None else min(pd.Timestamp(cut), END)
        if day > effective_cut:
            raise ValueError('DAY_AFTER_INPUT_CUT')
        if day < pd.Timestamp('2022-01-01'):
            facts = self.native_industry(sid, day, cut=effective_cut)
        else:
            continuous = self._continuous_qualification(sid, effective_cut)
            if day not in continuous.index:
                raise KeyError(('NOT_COMMON_QUALIFICATION_DAY', sid, str(day)))
            row = continuous.loc[day]
            facts = dict(sector=row.sector, **{c: _tri(row[c]) for c in SECTOR_FIELDS})
        if sid not in self._pvr:
            path = self._source(R / 'pvr_persistence_breadth_v1/STOCK_DAILY.parquet')
            self._pvr[sid] = pd.read_parquet(path, columns=['sid', 'day', 'score', 'state', 'valid_observation'],
                                            filters=[('sid', '==', sid)])
        pv = self._pvr[sid]
        pv = pv[pv.day.eq(day)]
        known = len(pv) == 1 and np.isfinite(pv.iloc[0].score) and pv.iloc[0].state >= 0 and bool(pv.iloc[0].valid_observation)
        return dict(facts, PVR_known=bool(known), PVR_score=float(pv.iloc[0].score) if len(pv) == 1 else np.nan,
                    qualification_source='ORIGINAL_NATIVE_PACKET_FOUR_FIELDS')

    def close(self, sid, day, cut=None):
        day = pd.Timestamp(day)
        table = self._cached_market(sid, cut=cut)
        if day not in table.index:
            raise KeyError(('NOT_COMMON_CLOSE', sid, str(day)))
        return dict(sid=sid, day=day, known_at=(day, 'CLOSE'), **table.loc[day].to_dict(),
                    **self.qualification(sid, day, cut=cut))

    def verify_sources(self):
        for path, digest in list(self.sources.items()):
            planned = self._planned_digest(path)
            if planned is not None and digest != planned:
                raise ValueError(('PLANNED_SOURCE_HASH_MISMATCH', path))
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != digest:
                raise ValueError(('SOURCE_CHANGED', path))
        return dict(self.sources)

    def sealed_receipts(self, window=None):
        """Frozen window candidates without replaying any sid or computing economics.

        Subsequent held-day management MUST use continuous close(), not these rows.
        The source is the narrow sealed market receipt table, never old outcomes.
        """
        self._setup()
        path = self._source(FROZEN / 'RECEIPTS.parquet')
        filters = [('window', '==', window)] if window is not None else None
        frame = pd.read_parquet(path, filters=filters)
        frame = frame.rename(columns={'receipt_id': 'legacy_receipt_id'})
        frame['legacy_root_id'] = [sid + '|' + str(pd.Timestamp(d).date())
                                   for sid, d in zip(frame.sid, frame.root_day)]
        frame['root_id'] = [canonical_root(sid, identity, birthday)
                            for sid, identity, birthday in zip(frame.sid, frame.identity, frame.root_day)]
        frame['receipt_id'] = [(root, str(pd.Timestamp(day).date()))
                               for root, day in zip(frame.root_id, frame.day)]
        return frame
