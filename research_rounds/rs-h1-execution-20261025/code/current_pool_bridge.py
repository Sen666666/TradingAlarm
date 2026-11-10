"""Offline, explicit current-selection data bridge; no network or account runner.

One state production is shared by T0/T1/S0. Unknown inputs stay in the roster.
The upstream event/participation equations and admission RS are imported intact.
See audit-execution/INPUT_MANIFEST.md for the intentionally small input contract.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, time
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import hashlib
import importlib
import json
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
UPSTREAM = {
    'numeric': ROOT / 'research_rounds/pv-participation-response-20261020/code/numeric.py',
    'participation': ROOT / 'research_rounds/pv-participation-response-20261020/code/participation.py',
    'data_utils': ROOT / 'research_rounds/pv-participation-response-20261020/code/data_utils.py',
    'sector_stock_admission': Path(__file__).with_name('sector_stock_admission.py'),
}
for p in [Path(__file__).parent, *(p.parent for p in UPSTREAM.values())]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import sector_stock_admission as admission
from current_fixed_pool import PoolLine, SelectionEvidence, HistoricalInputs
from data_utils import eligible_prices, boolean_column
from numeric import event_frame_numeric
from participation import participation_frame

OHLC = ('open', 'high', 'low', 'close')
TZ = ZoneInfo('Asia/Shanghai')
RESEARCH_BASIS = 'current_pool_historical_development'


def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def checked_ref(ref, base):
    path = Path(ref['path'])
    if not path.is_absolute():
        path = base / path
    if not path.is_file() or sha256(path) != ref['sha256']:
        raise ValueError('Missing or changed input: ' + str(path))
    return path


def decimal(value):
    # str avoids Decimal(float); original decoded/source bytes remain hashed.
    x = Decimal(str(value))
    if not x.is_finite():
        raise ValueError('Nonfinite source decimal')
    return x


def read_raw(path, record):
    if path.suffix == '.parquet':
        frame = pd.read_parquet(path)
    elif path.suffix == '.csv':
        frame = pd.read_csv(path, float_precision='round_trip')
    else:
        obj = json.loads(path.read_text())
        frame = pd.DataFrame(obj['bars'])
    if 'trade_date' in frame:
        frame = frame.rename(columns={'trade_date': 'date'})
    if 'date' in frame:
        frame = frame.set_index('date')
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame.index), name='date')
    if (frame.empty or frame.index.tz is not None or not frame.index.is_unique
            or not frame.index.is_monotonic_increasing):
        raise ValueError('Nonempty unique increasing local session dates required')
    if (frame.index != frame.index.normalize()).any():
        raise ValueError('Expected daily dates, not intraday timestamps')
    if str(frame.index[0].date()) != record['source_start']:
        raise ValueError('Explicit source origin mismatch; no silent truncation/rebase')
    declared_volume_unit = record['volume_unit']
    allowed_volume_units = ({'shares', 'source_index_units'} if record['kind'] == 'sector_index'
                            else {'shares'})
    for name, expected in [('volume_unit', declared_volume_unit), ('price_adjustment', 'raw')]:
        if name in frame and set(frame[name].dropna()) != {expected}:
            raise ValueError('Unexpected raw ' + name)
    if declared_volume_unit not in allowed_volume_units or record['price_adjustment'] != 'raw':
        raise ValueError('Raw prices and normalized share volume (or explicit index source units) required')
    if not set(OHLC + ('volume',)).issubset(frame.columns):
        raise ValueError('Missing raw OHLCV')
    for col in OHLC + ('volume',):
        frame[col] = pd.to_numeric(frame[col], errors='raise')
    if 'is_observed_bar' in frame:
        frame['observed_bar'] = frame.is_observed_bar
    # Malformed price rows are retained for the declared observation mask audit.
    if (frame.volume.dropna() < 0).any():
        raise ValueError('Negative raw volume')
    return frame


def read_actions(record, base):
    """Only explicit normalized terms; no HK text interpretation or cash guessing."""
    adjustment = record['adjustment']
    method = adjustment['method']
    if method == 'unadjusted_index':
        if record['kind'] != 'sector_index':
            raise ValueError('Unadjusted index policy cannot be assigned to a stock')
        return [], {'method': method, 'ledger_ready': False}
    if method not in ('theoretical_ex_price', 'total_return'):
        raise ValueError('Unsupported signal preparation policy')
    path = checked_ref(adjustment['actions'], base)
    obj = json.loads(path.read_text())
    if obj.get('series_id') != record['series_id']:
        raise ValueError('Action identity mismatch')
    if obj.get('status') not in ('reviewed_terms', 'declared_research_proxy'):
        raise ValueError('Action terms not reviewed; raw response is not a certificate')
    if not obj.get('coverage_evidence') or obj.get('unresolved'):
        raise ValueError('Action coverage evidence required and unresolved terms retained')
    if obj.get('currency') != record['currency']:
        raise ValueError('Action/raw currency mismatch')
    events = obj.get('events')
    if not isinstance(events, list):
        raise ValueError('Explicit action events list required')
    seen = set()
    for event in events:
        d = pd.Timestamp(event['effective_date'])
        if d in seen:
            raise ValueError('Same-date actions need explicit upstream aggregation')
        seen.add(d)
        if not event.get('source_id'):
            raise ValueError('Every normalized event needs source evidence')
        if decimal(event['cash_per_old_share']) < 0 or decimal(event['split_ratio']) <= 0:
            raise ValueError('Invalid normalized action terms')
    return events, obj


def prepare_signal(raw, record, events, cutoff=None):
    """Prefix-causal signal coordinates, not shareholder total-return accounting.

    Theoretical ex-price uses prior raw close; total-return uses the event's
    close, matching the existing two declared signal conventions. Factor changes
    only on a supported action. Shares use source-origin units for volume.
    """
    method = record['adjustment']['method']
    source = raw if cutoff is None else raw.loc[:pd.Timestamp(cutoff)]
    if source.empty:
        raise ValueError('Empty source prefix')
    start, end = source.index[0], source.index[-1]
    active = {}
    for event in events:
        date = pd.Timestamp(event['effective_date'])
        if date == start and (decimal(event['cash_per_old_share']) != 0
                              or decimal(event['split_ratio']) != 1):
            raise ValueError('Origin-date action requires an explicit prior price/state')
        if start < date <= end:
            active[date] = event
    full = source.reindex(source.index.union(pd.DatetimeIndex(active))).sort_index()
    full.index.name = 'date'
    observed = set(source.index)
    # Input observation flags survive. Merely appearing in a source is not proof
    # of a real traded bar, and ordinary missing volume is not a price exclusion.
    declared_observed = boolean_column(source, 'observed_bar', True)
    full['observed_bar'] = declared_observed.reindex(full.index).fillna(False).astype(bool)
    full['synthetic_event_bar'] = ~full.index.isin(observed)
    full['raw_volume'] = full.volume
    for col in OHLC:
        full['raw_' + col] = full[col]
    output = {x: [] for x in OHLC + ('volume', 'adjustment_factor', 'volume_factor')}
    with localcontext() as context:
        context.prec, context.rounding = 40, ROUND_HALF_EVEN
        factor, share_units, previous = Decimal(1), Decimal(1), None
        for date, row in full.iterrows():
            event = active.get(date)
            cash = decimal(event.get('signal_cash_per_old_share', event['cash_per_old_share'])) if event else Decimal(0)
            split = decimal(event.get('signal_split_ratio', event['split_ratio'])) if event else Decimal(1)
            volume_split = decimal(event.get('volume_split_ratio',event['split_ratio'])) if event else Decimal(1)
            is_observed = date in observed
            prices = ({k: decimal(row[k]) if pd.notna(row[k]) and np.isfinite(float(row[k])) else None
                       for k in OHLC} if is_observed else None)
            if event:
                if method == 'unadjusted_index':
                    raise ValueError('Index cannot receive stock distribution terms')
                if method == 'theoretical_ex_price':
                    if previous is None or previous <= cash:
                        raise ValueError('Invalid prior raw price for theoretical ex-price')
                    ex_price = (previous - cash) / split
                    factor *= previous / ex_price
                    if not is_observed:
                        prices = {k: ex_price for k in OHLC}
                elif method == 'total_return':
                    if not is_observed:
                        raise ValueError('Total-return event requires observed close or reviewed prepared source')
                    if prices['close'] is None or prices['close'] <= 0:
                        raise ValueError('Total-return event needs a positive finite close')
                    if cash != 0 and split != 1:
                        raise ValueError('Combined cash/split outside frozen total-return preparation convention')
                    factor *= split + cash / prices['close']
                share_units *= volume_split
            if prices is None:
                raise ValueError('Synthetic price requires supported explicit event')
            for k in OHLC:
                output[k].append(float(prices[k] * factor) if prices[k] is not None else np.nan)
            v = (decimal(row.volume) if is_observed and pd.notna(row.volume)
                 and np.isfinite(float(row.volume)) else None)
            output['volume'].append(float(v / share_units) if v is not None else np.nan)
            output['adjustment_factor'].append(float(factor))
            output['volume_factor'].append(float(1 / share_units))
            if prices['close'] is not None and prices['close'] > 0:
                previous = prices['close']
    for key, values in output.items():
        full[key] = values
    # A synthetic action row is never a market observation or executable price.
    return full


def state_frame(signal):
    eligible = eligible_prices(signal)
    if eligible.empty:
        raise ValueError('No eligible price observations')
    if not (eligible.volume.gt(0) & np.isfinite(eligible.volume)).any():
        raise ValueError('No real positive-volume observations for frozen joint model')
    events = event_frame_numeric(eligible.close, eligible.volume, joint=True, event_exit=False)
    state, memories = participation_frame(eligible, events, mode='volume')
    # Call the frozen formula only for the 253-observation rolling window.
    closes = eligible.close.to_numpy()
    state['rs'] = pd.Series(
        [admission.rs_score(closes[max(0, i-252):i+1]) for i in range(len(closes))],
        index=state.index, dtype='float64')
    return eligible, events, state, memories


def source_segments(raw, record):
    """A reviewed source gap is a data boundary, never a one-session return."""
    segments = record.get('segments')
    if segments is None:
        return [{'start': str(raw.index[0].date()), 'end': str(raw.index[-1].date()),
                 'reason': 'declared_continuous_source'}]
    if not isinstance(segments, list) or not segments:
        raise ValueError('Nonempty explicit source segments required')
    assigned = pd.Series(0, index=raw.index)
    previous_end = None
    for part in segments:
        start, end = pd.Timestamp(part['start']), pd.Timestamp(part['end'])
        if (not part.get('reason') or start not in raw.index or end not in raw.index
                or end < start or (previous_end is not None and start <= previous_end)):
            raise ValueError('Ordered real-date nonoverlapping source segments required')
        assigned.loc[start:end] += 1
        previous_end = end
    if not assigned.eq(1).all():
        raise ValueError('Segments must retain every raw row exactly once')
    return segments


@dataclass
class SeriesData:
    record: dict
    raw: pd.DataFrame | None = None
    signal: pd.DataFrame | None = None
    states: pd.DataFrame | None = None
    events: pd.DataFrame | None = None
    memories: pd.DataFrame | None = None
    blocked_reason: str | None = None
    action_policy: dict | None = None


@dataclass(frozen=True)
class DecisionInputs:
    clock: admission.Clock
    evidence: SelectionEvidence
    lines: tuple[PoolLine, ...]
    historical: tuple[HistoricalInputs, ...]
    sectors: tuple[admission.Sector, ...]


@dataclass
class Bundle:
    manifest: dict
    manifest_path: Path
    evidence: SelectionEvidence
    lines: tuple[PoolLine, ...]
    series: dict[str, SeriesData]
    sector_series: dict[str, str]
    technical_sample: bool

    @property
    def signal_ready(self):
        return (not self.technical_sample and all(
            x.blocked_reason is None and x.states is not None for x in self.series.values()))

    def _last(self, series_id, clock):
        item = self.series.get(series_id)
        if item is None or item.blocked_reason or item.states is None:
            return None, None, None
        close_time = time.fromisoformat(item.record['close_available_time'])
        dates = item.states.index
        cutoff = pd.Timestamp(clock.decision_at.astimezone(TZ).date())
        pos = dates.searchsorted(cutoff, side='right') - 1
        if pos < 0:
            return None, None, None
        at = datetime.combine(dates[pos].date(), close_time, TZ)
        if at > clock.decision_at:
            pos -= 1
            if pos < 0:
                return None, None, None
            at = datetime.combine(dates[pos].date(), close_time, TZ)
        segments = item.record.get('segments')
        if segments and 'segment_id' in item.states:
            number = int(item.states.iloc[pos].segment_id)
            if number < len(segments) - 1 and cutoff > pd.Timestamp(segments[number]['end']):
                return None, None, None  # Explicit missing-source interval.
        if item.record.get('unavailable_from') and cutoff >= pd.Timestamp(item.record['unavailable_from']):
            return None, None, None
        return item.states.iloc[pos], at, item.record['raw']['sha256']

    def at_decision(self, clock, *, market_buyable):
        """No implicit trade calendars: caller supplies causal availability Facts.

        State persists across non-observation dates; RS keeps its actual old date
        so admission's same-session freshness check still rejects stale ranks.
        """
        if set(market_buyable) != {x.security_id for x in self.lines}:
            raise ValueError('Explicit historical market availability required for every fixed line')
        if not hasattr(self, '_h1_cache'):
            z=np.load(Path(__file__).resolve().parents[1]/'h1/matrix.npz')
            self._h1_cache=(pd.DatetimeIndex(z['dates']),{sid:j for j,sid in enumerate(z['symbols'])},z['score'])
        dates,columns,scores=self._h1_cache
        d=pd.Timestamp(clock.session_date); ti=dates.get_indexer([d])[0]
        def facts(series_id):
            row, at, source = self._last(series_id, clock)
            if at is None:
                unknown = admission.Fact(None, clock.decision_at, clock.decision_at,
                                          source_id='unavailable:' + str(series_id))
                return unknown, unknown, None
            ready = bool(row.ready)
            kwargs = dict(known_at=at, valid_from=at, observed_at=at, source_id=source)
            trend = admission.Fact(bool(row.target) if ready else None, **kwargs)
            j=columns.get(series_id)
            score=scores[ti,j] if ti>=0 and j is not None else np.nan
            rank = admission.Rank(None if pd.isna(score) else float(score), clock.decision_at, clock.decision_at)
            return admission.Fact(ready, **kwargs), trend, rank
        sectors = []
        sector_ready = {}
        for sector_id, series_id in sorted(self.sector_series.items()):
            ready, trend, rank = facts(series_id)
            sector_ready[sector_id] = ready.read(clock)
            sectors.append(admission.Sector(sector_id, trend, rank))
        histories = []
        for line in self.lines:
            ready, trend, rank = facts(line.security_id)
            a, b = ready.read(clock), sector_ready.get(line.sector_id)
            common = None if a is None or b is None else bool(a and b)
            # This is a derived historical readiness fact, never selection metadata.
            common_fact = admission.Fact(common, clock.decision_at, clock.decision_at,
                                          source_id='derived_common_readiness')
            histories.append(HistoricalInputs(line.security_id, common_fact,
                              market_buyable[line.security_id], trend, rank))
        return DecisionInputs(clock, self.evidence, self.lines, tuple(histories), tuple(sectors))


def build_series(record, base, scope_date):
    """Build exactly one input; failure stays attached to its original identity."""
    item = SeriesData(record)
    try:
        if record.get('status') != 'ready':
            raise ValueError(record.get('blocked_reason', 'Input coverage is not ready'))
        time.fromisoformat(record['close_available_time'])
        item.raw = read_raw(checked_ref(record['raw'], base), record)
        if item.raw.index[-1] > pd.Timestamp(scope_date):
            raise ValueError('Raw input extends beyond frozen round end')
        actions, policy = read_actions(record, base)
        item.action_policy = policy
        signals, events, states, memories = [], [], [], []
        for segment_id, part in enumerate(source_segments(item.raw, record)):
            raw_part = item.raw.loc[part['start']:part['end']]
            signal = prepare_signal(raw_part, record, actions)
            _, event, state, memory = state_frame(signal)
            for frame in (signal, event, state, memory):
                frame['segment_id'] = segment_id
            signals.append(signal); events.append(event); states.append(state); memories.append(memory)
        item.signal = pd.concat(signals)
        item.events = pd.concat(events)
        item.states = pd.concat(states)
        item.memories = pd.concat(memories, ignore_index=True)
    except (ValueError, KeyError, TypeError, FileNotFoundError) as exc:
        item.blocked_reason = type(exc).__name__ + ': ' + str(exc)
    return item


def load_bundle(path, *, technical_sample=False, materialize=False):
    path = Path(path).resolve()
    manifest = json.loads(path.read_text())
    base = path.parent
    if manifest.get('schema_version') != 1 or manifest.get('research_basis') != RESEARCH_BASIS:
        raise ValueError('Explicit schema 1 current-pool development manifest required')
    if manifest.get('scope_date') != '2026-10-22':
        raise ValueError('This frozen round is dated 2026-10-22')
    for name, file in UPSTREAM.items():
        module = importlib.import_module(name)
        if Path(module.__file__).resolve() != file.resolve():
            raise ValueError('Unexpected upstream module loaded: ' + name)
        source_file = (ROOT/'research_rounds/a-share-selection-e0-20261024/code/sector_stock_admission.py') if name=='sector_stock_admission' else file
        if sha256(source_file) != manifest['upstream_sha256'].get(name):
            raise ValueError('Frozen upstream changed: ' + name)
    if not technical_sample:
        receipt = json.loads(checked_ref(manifest['data_pool_closeout'], base).read_text())
        if receipt.get('status') != 'data_pool_closed' or receipt.get('scope_date') != manifest['scope_date']:
            raise ValueError('Production waits for explicit data-pool closeout')
    selection_ref = manifest['selection']
    selection_path = checked_ref(selection_ref, base)
    selection = json.loads(selection_path.read_text())
    evidence = SelectionEvidence(selection['snapshot_id'], selection_ref['sha256'],
                                 datetime.fromisoformat(selection['observed_at']), selection['source_id'])
    lines = tuple(PoolLine(**line) for line in selection['lines'])
    if len({x.security_id for x in lines}) != len(lines):
        raise ValueError('Duplicate fixed selection ID')
    series = {}
    for record in manifest['series']:
        sid = record['series_id']
        if sid in series:
            raise ValueError('Duplicate series ID')
        if record['kind'] not in ('stock', 'sector_index'):
            raise ValueError('Unknown series kind')
        series[sid] = (build_series(record, base, manifest['scope_date']) if materialize
                       else SeriesData(record))
    stock_ids = {sid for sid, item in series.items() if item.record['kind'] == 'stock'}
    if stock_ids != {x.security_id for x in lines}:
        raise ValueError('All raw-pool stocks must have explicit selection and series records; no silent shrinkage')
    sectors = manifest['sector_series']
    if not all(sid in series and series[sid].record['kind'] == 'sector_index' for sid in sectors.values()):
        raise ValueError('Sector mapping must reference explicit same-source index series')
    return Bundle(manifest, path, evidence, lines, series, sectors, technical_sample)


def load_prepared_states(bundle, output):
    """Load only three state/rank columns; do not recompute a model per account."""
    output = Path(output)
    manifest = json.loads((output / 'manifest.json').read_text())
    if (manifest['source_manifest_sha256'] != sha256(bundle.manifest_path)
            or manifest['bridge_sha256'] != sha256(ROOT/'research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py')
            or manifest['technical_sample'] != bundle.technical_sample):
        raise ValueError('Prepared state identity/code/research-mode mismatch')
    rows = {row['series_id']: row for row in manifest['series']}
    if len(rows) != len(manifest['series']) or set(rows) != set(bundle.series):
        raise ValueError('Prepared states must retain every declared series')
    for sid, item in bundle.series.items():
        row = rows[sid]
        item.blocked_reason = row['blocked_reason']
        if item.blocked_reason is None:
            path = checked_ref(row['files']['states'], output)
            item.states = pd.read_parquet(path, columns=['ready', 'target', 'rs', 'segment_id'])
    return bundle


def write_bundle(bundle, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    rows = []
    for n, (sid, declared) in enumerate(sorted(bundle.series.items())):
        # Full raw/signal/event frames live for one security, never the whole pool.
        item = declared if declared.states is not None else build_series(
            declared.record, bundle.manifest_path.parent, bundle.manifest['scope_date'])
        directory = output / f'{n:06d}'
        directory.mkdir()
        files = {}
        for name in ('signal', 'events', 'states', 'memories'):
            frame = getattr(item, name)
            if frame is not None:
                p = directory / (name + '.parquet')
                frame.to_parquet(p)
                files[name] = {'path': str(p.relative_to(output)), 'sha256': sha256(p)}
        rows.append({'series_id': sid, 'blocked_reason': item.blocked_reason,
                     'raw_rows': len(item.raw) if item.raw is not None else 0,
                     'signal_observations': len(item.states) if item.states is not None else 0,
                     'synthetic_action_rows': int(item.signal.synthetic_event_bar.sum()) if item.signal is not None else 0,
                     'files': files})
    summary = {'schema_version': 1, 'source_manifest': str(bundle.manifest_path),
               'source_manifest_sha256': sha256(bundle.manifest_path),
               'bridge_sha256': sha256(__file__), 'research_basis': RESEARCH_BASIS,
               'technical_sample': bundle.technical_sample,
               'signal_ready': not bundle.technical_sample and all(x['blocked_reason'] is None for x in rows),
               'data_pool_closeout_claim': False, 'execution_certified': False, 'accounts_run': 0,
               'algorithm_changes': 0, 'series': rows}
    (output / 'manifest.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--technical-sample', action='store_true')
    args = parser.parse_args()
    summary = write_bundle(load_bundle(args.manifest, technical_sample=args.technical_sample), args.output)
    print(json.dumps({k: v for k, v in summary.items() if k != 'series'}, ensure_ascii=False))
    print(json.dumps({'series': len(summary['series']), 'blocked': sum(bool(x['blocked_reason']) for x in summary['series'])}))


if __name__ == '__main__':
    main()
