"""Independent four-stock descriptive scalar checks. No model/account imports."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math

import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
PLAN = json.loads((OUT / 'SPOT_CHECK_PLAN.json').read_text())
META = {r['sid']: r for r in json.loads((ROOT / 'METRIC_INPUTS_AND_WARMUP.json').read_text())}
ABS_TOL = 1e-10
REL_TOL = 5e-13


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def clean(v):
    if isinstance(v, dict):
        return {k: clean(x) for k, x in v.items()}
    if isinstance(v, list):
        return [clean(x) for x in v]
    if isinstance(v, float) and not math.isfinite(v):
        return None
    return v


checks = []
details = []
bindings = []
errors = []
max_residual = {}
for sid, dates in PLAN['dates'].items():
    meta = META[sid]
    frames = {}
    for kind in ['facts', 'signal', 'events']:
        record = meta['sources'][kind]
        path = Path(record['path'])
        assert sha(path) == record['sha256'], (sid, kind, 'original input changed')
        frame = pd.read_parquet(path)
        frame.index = pd.DatetimeIndex(frame.index).as_unit('ns')
        assert frame.index.is_unique and frame.index.is_monotonic_increasing
        frames[kind] = frame.loc[:max(dates)]
        bindings.append({'sid': sid, 'kind': kind, **record, 'prefix_end': max(dates)})
    f, signal, events = (frames[k] for k in ['facts', 'signal', 'events'])
    metric_path = ROOT / 'metrics' / (sid + '.csv')
    before_sha = sha(metric_path)
    saved = pd.read_csv(metric_path, index_col='date', parse_dates=True, float_precision='round_trip')
    assert sha(metric_path) == before_sha, 'metric changed during read'
    bindings.append({'sid': sid, 'kind': 'reviewed metric CSV', 'path': str(metric_path), 'sha256': before_sha})
    ema = {}
    ema_history = []
    prior_c, prior_l, prior_h = [], [], []
    prior_valid = False
    prior_segment = None
    seed = None
    count = 0
    for day, row in f.iterrows():
        c = float(row.close)
        valid = math.isfinite(c) and c > 0 and pd.notna(row.segment_id)
        segment = row.segment_id
        if not valid or not prior_valid or segment != prior_segment:
            ema = {}
            ema_history = []
            prior_c, prior_l, prior_h = [], [], []
            seed = None
            count = 0
        if not valid:
            prior_valid = False
            prior_segment = segment
            continue
        if seed is None:
            seed = str(day.date())
        count += 1
        assert day in signal.index, (sid, day, 'original signal date absent')
        assert float(signal.loc[day, 'close']) == c, (sid, day, 'price source mismatch')
        for n in [20, 60]:
            alpha = 2.0 / (n + 1.0)
            ema[n] = c if n not in ema else alpha * c + (1.0 - alpha) * ema[n]
        ema_history.append(ema[20])
        factor = float(row.factor)
        expected = {'close_a': c, 'raw_close': float(row.raw_close), 'factor': factor}
        for n in [20, 60]:
            value = ema[n] if count >= n else math.nan
            expected['ema%d_a' % n] = value
            expected['ema%d_raw_current_units' % n] = value / factor
        delta = 100 * (ema[20] / ema_history[-6] - 1) if count >= 25 else math.nan
        expected['ema20_five_observation_change_pct'] = delta
        expected['ema20_five_observation_slope_pct_per_observation'] = delta / 5
        expected['close_deviation_ema20_pct'] = 100 * (c / ema[20] - 1) if count >= 20 else math.nan
        for label, lows, highs in [('hl', prior_l, prior_h), ('close', prior_c, prior_c)]:
            enough = len(lows) >= 20 and all(math.isfinite(x) for x in lows[-20:] + highs[-20:])
            lo = min(lows[-20:]) if enough else math.nan
            hi = max(highs[-20:]) if enough else math.nan
            expected['prior20_%s_low_a' % label] = lo
            expected['prior20_%s_high_a' % label] = hi
            expected['prior20_%s_position_pct' % label] = 100 * (c - lo) / (hi - lo) if enough and hi > lo else math.nan
        day_string = str(day.date())
        if day_string in dates:
            peaks = events.loc[(events.index <= day) & events.event.eq(-1) & events.segment_id.eq(segment)]
            peaks = peaks.loc[peaks.confirmed_pivot_price.notna()]
            peaks = peaks.loc[peaks.confirmed_pivot_price.map(lambda x: math.isfinite(float(x)) and float(x) > 0)]
            labels = {'seed_date': seed, 'observations_from_seed': count}
            if len(peaks):
                confirm = peaks.index[-1]
                peak = peaks.iloc[-1]
                value = float(peak.confirmed_pivot_price)
                pivot = pd.Timestamp(peak.confirmed_pivot_date)
                expected['last_confirmed_peak_a'] = value
                expected['last_confirmed_peak_raw_current_units'] = value / factor
                expected['last_confirmed_peak_pivot_raw_saved'] = float(f.loc[pivot, 'raw_close']) if pivot in f.index else math.nan
                gap = 100 * (c / value - 1)
                expected['signed_gap_to_confirmed_peak_pct'] = gap
                expected['drawdown_from_confirmed_peak_pct'] = max(0, -gap)
                labels['last_confirmed_peak_confirmation_day'] = str(confirm.date())
                labels['last_confirmed_peak_pivot_day'] = str(pivot.date())
            else:
                for col in ['last_confirmed_peak_a', 'last_confirmed_peak_raw_current_units', 'last_confirmed_peak_pivot_raw_saved', 'signed_gap_to_confirmed_peak_pct', 'drawdown_from_confirmed_peak_pct']:
                    expected[col] = math.nan
            actual = saved.loc[day]
            for col, value in expected.items():
                observed = float(actual[col])
                ok = (not math.isfinite(value) and not math.isfinite(observed)) or math.isclose(value, observed, rel_tol=REL_TOL, abs_tol=ABS_TOL)
                residual = abs(value - observed) if math.isfinite(value) and math.isfinite(observed) else None
                if residual is not None:
                    max_residual[col] = max(max_residual.get(col, 0), residual)
                checks.append({'sid': sid, 'date': day_string, 'field': col, 'passed': ok, 'absolute_residual': residual})
                if not ok:
                    errors.append({'sid': sid, 'date': day_string, 'field': col, 'expected': value, 'saved': observed})
            for col, value in labels.items():
                observed = int(actual[col]) if col == 'observations_from_seed' else str(actual[col])
                ok = observed == value
                checks.append({'sid': sid, 'date': day_string, 'field': col, 'passed': ok})
                if not ok:
                    errors.append({'sid': sid, 'date': day_string, 'field': col, 'expected': value, 'saved': observed})
            for n in [20, 60]:
                ready_col = 'ema%d_ready' % n
                if ready_col in actual:
                    ok = bool(actual[ready_col]) == (count >= n)
                    checks.append({'sid': sid, 'date': day_string, 'field': ready_col, 'passed': ok})
                    if not ok:
                        errors.append({'sid': sid, 'date': day_string, 'field': ready_col})
            details.append({'sid': sid, 'date': day_string, 'manual_expected': expected, 'identity_labels': labels})
        prior_c.append(c)
        prior_l.append(float(signal.loc[day, 'low']))
        prior_h.append(float(signal.loc[day, 'high']))
        prior_valid = valid
        prior_segment = segment
    assert sum(d['sid'] == sid for d in details) == len(dates), (sid, 'planned check date missing')

prefix_checks = json.loads((ROOT / 'PREFIX_CHECKS.json').read_text())
assert len(prefix_checks) == 12 and all(r['exact'] is True for r in prefix_checks)
report = {'status': 'PASS_INDEPENDENT_FOUR_STOCK_SELECTED_SCALAR_CHECKS' if not errors else 'FAIL_SELECTED_SCALAR_CHECKS',
          'reviewer': '/root/upside_logic', 'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
          'scope': 'Independent explicit scalar price EMA recursion and list windows on four manifest-bound source prefixes only. Did not import root metrics or any E0/G1/I/CP/account model. Root12 prefix checks read as saved verification; not rerun by reviewer.',
          'stocks': len(PLAN['dates']), 'selected_dates': len(details), 'checks': len(checks),
          'absolute_tolerance': ABS_TOL, 'relative_tolerance': REL_TOL,
          'maximum_absolute_residual_by_field': max_residual, 'errors': errors,
          'bindings': bindings, 'script_sha256': sha(__file__),
          'frozen_definitions_sha256': sha(ROOT / 'FROZEN_DEFINITIONS.txt'),
          'root_prefix_checks_sha256': sha(ROOT / 'PREFIX_CHECKS.json'),
          'new_accounts': 0, 'new_backtests': 0, 'old_models_recomputed': False,
          'not_validated': ['Descriptive metric predictive value', 'Economic or strategy improvement', 'Real exchange execution', 'Historical provider receipt timing', 'Case opportunity/order/funding joins']}
for name, value in [('SELECTED_SCALAR_DETAILS.json', details), ('SELECTED_SCALAR_CHECKS.json', checks), ('INDEPENDENT_SCALAR_REVIEW.json', report)]:
    (OUT / name).write_text(json.dumps(clean(value), ensure_ascii=False, indent=2, allow_nan=False) + '\n')
print(json.dumps({'status': report['status'], 'stocks': report['stocks'], 'selected_dates': len(details), 'checks': len(checks), 'errors': len(errors), 'max_abs_residual': max(max_residual.values()), 'review_sha256': sha(OUT / 'INDEPENDENT_SCALAR_REVIEW.json')}, ensure_ascii=False))
assert not errors, errors
