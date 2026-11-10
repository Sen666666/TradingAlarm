"""Independent B4 source/receipt audit; no accounts and no bulk synthetic run.

The reference below imports no production numerical/state helpers. Production
strength_frame is used only for physically truncated replay and manual probes.
All destinations are new files/directories and an existing audit is not replaced.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import json
import math
from statistics import median
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
REPO = ROOT.parents[1]
OLD = REPO / 'research_rounds/pv-strength-20261025'
ASSETS = ('AU0', '518880', '512480', '001309.SZ', '688981.SH', '600036.SH', '600519.SH')
EPS = np.finfo(float).eps


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write('\n')


def load_model():
    spec = importlib.util.spec_from_file_location('b4_audited_production', ROOT / 'code/model.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tolerance(a, b):
    return 32 * EPS * max(1., abs(a), abs(b))


def strict(a, b):
    return a - b > tolerance(a, b)


def reached(a, b):
    return a >= b - tolerance(a, b)


def equal(a, b, label):
    if a is None or b is None:
        assert a is None and b is None, (label, a, b)
    elif isinstance(a, (int, float, np.number)) and not isinstance(a, (bool, np.bool_)):
        assert math.isclose(float(a), float(b), abs_tol=1e-12, rel_tol=2e-12), (label, a, b)
    else:
        assert a == b, (label, a, b)


def reference(g, joint=True):
    """Independent scalar ledger of only the frozen structural contract."""
    prices = g.close.to_numpy(float)
    logp = np.log(prices / prices[0])
    returns = np.r_[np.nan, np.diff(logp)]
    volumes = g.volume.to_numpy(float)
    state = {h: 0 for h in (21, 63)}
    candidates = {h: {} for h in (21, 63)}
    extrema = {h: {1: None, -1: None} for h in (21, 63)}
    daily, confirms, resets = {}, [], []

    def reset(t, anchor, h, direction, scale, vref, reason):
        c = dict(direction=direction, anchor=float(logp[anchor]), anchor_price=float(prices[anchor]),
                 anchor_observation=anchor, anchor_date=str(g.index[anchor].date()),
                 created_observation=t, threshold=scale*math.sqrt(h), scale_at_anchor=scale,
                 volume_reference=vref, frontier=0., credit=0., x=direction*float(logp[t]-logp[anchor]),
                 new_frontier=0., frontier_increment=0., credit_increment=0., volume_weight=1.)
        candidates[h][direction] = c
        resets.append((t, h, reason, dict(c)))

    for t in range(64, len(g)):
        scale = max(1.4826 * median(abs(x) for x in returns[t-63:t]), 1e-8)
        vref = median(volumes[t-21:t])
        row = {'s': scale, 'volume_reference': vref, 'r': returns[t], 'r_bp': returns[t]*1e4}
        activity = volumes[t] / vref
        q = returns[t] / scale
        qeff = q * (math.sqrt(min(max(activity, 1.), 4.)) if joint else 1.)
        row.update(activity=activity, q=q, qeff=qeff,
                   acute_down=float(reached(-qeff, 2.)), acute_up=float(reached(qeff, 2.)))
        for h in (21, 63):
            row[f'delta_{h}'] = scale * math.sqrt(h)
            if t == 64:
                extrema[h] = {1: t-1, -1: t-1}
                for direction in (1, -1):
                    reset(t, t-1, h, direction, scale, vref, 'initialization')
            previous = state[h]
            if previous >= 0 and strict(logp[t], logp[extrema[h][1]]):
                extrema[h][1] = t
                reset(t, t, h, -1, scale, vref, 'new_high')
            if previous <= 0 and strict(-logp[t], -logp[extrema[h][-1]]):
                extrema[h][-1] = t
                reset(t, t, h, 1, scale, vref, 'new_low')
            direction_confirmed = 0
            for direction, c in candidates[h].items():
                old_frontier = c['frontier']
                x = direction * float(logp[t] - c['anchor'])
                eligible = strict(x, old_frontier) and direction * returns[t] > 0
                weight = min(max(math.sqrt(volumes[t]/c['volume_reference']), .5), 2.) if joint else 1.
                increment = x-old_frontier if eligible else 0.
                c.update(x=x, new_frontier=float(eligible), frontier_increment=increment,
                         credit_increment=weight*increment, volume_weight=weight,
                         frontier=x if eligible else old_frontier, credit=c['credit']+weight*increment)
                assert c['credit'] >= .5*c['frontier']-1e-12
                assert c['credit'] <= 2.*c['frontier']+1e-12
                if eligible and reached(x, c['threshold']) and reached(c['credit'], c['threshold']):
                    assert not direction_confirmed
                    direction_confirmed = direction
                    confirms.append((t, h, previous, direction, dict(c)))
            if direction_confirmed:
                state[h] = direction_confirmed
                candidates[h] = {}
                reset(t, t, h, -direction_confirmed, scale, vref, 'direction_confirmed')
                extrema[h] = {direction_confirmed: t, -direction_confirmed: None}
            row[f'S{h}'] = state[h]
            row[f'confirmed_{h}'] = float(direction_confirmed != 0)
            row[f'confirmed_direction_{h}'] = direction_confirmed
            for direction, side in ((1, 'up'), (-1, 'down')):
                row[f'{side}_active_{h}'] = float(direction in candidates[h])
                if direction in candidates[h]:
                    for field, value in candidates[h][direction].items():
                        if field != 'direction':
                            row[f'{side}_{field}_{h}'] = value
            if state[h]:
                xt = extrema[h][state[h]]
                row[f'running_extreme_{h}'] = float(logp[xt])
                row[f'running_extreme_price_{h}'] = float(prices[xt])
                row[f'running_extreme_observation_{h}'] = xt
                row[f'running_extreme_date_{h}'] = str(g.index[xt].date())
        daily[g.index[t]] = row
    return daily, confirms, resets, returns


def audit_saved(source, saved, events, model):
    rows = receipts = upward = reset_count = ew_values = 0
    assert source.index.equals(saved.index)
    for segment, group in source.groupby('segment_id', sort=False):
        g = group.loc[group.valid_strength_observation]
        unknown = group.index[~group.valid_strength_observation].union(g.index[:64])
        assert saved.loc[unknown, model.FIELDS].isna().all().all(), 'unknown numeric mask'
        assert saved.loc[unknown, 'phase'].eq('unknown').all(), 'unknown label'
        if not len(g):
            continue
        daily, expected, expected_resets, returns = reference(g)
        actual_events = [e for e in events if e.get('segment') == str(segment)]
        actual = [e for e in actual_events if e['kind'] == 'structure_confirmed']
        actual_resets = [e for e in actual_events if e['kind'] == 'candidate_reset']
        assert len(actual) == len(expected), ('confirmation count', segment)
        assert len(actual_resets) == len(expected_resets), ('reset count', segment)
        for date, expected_row in daily.items():
            for field, value in expected_row.items():
                equal(value, saved.at[date, field], (str(date), field))
            rows += 1
        # This calculation uses pandas' separate EW kernel, not the production recurrence.
        for horizon in (5, 21):
            ew = pd.Series(returns[1:], index=g.index[1:]).ewm(span=horizon, adjust=False).mean()
            for date in g.index[64:]:
                value = float(ew.loc[date])
                for field, expected_value in ((f'mu{horizon}', value), (f'mu{horizon}_bp', 1e4*value),
                       (f'mu{horizon}_direction', np.sign(value)), (f'mu{horizon}_magnitude_bp', 1e4*abs(value))):
                    equal(expected_value, saved.at[date, field], (str(date), field))
                    ew_values += 1
        for (t, h, before, direction, receipt), event in zip(expected, actual):
            assert (t, h, before, direction) == (event['observation'], event['horizon'],
                                                   event['previous_direction'], event['direction'])
            assert direction * returns[t] > 0, 'confirmation on nonpositive directional return'
            assert receipt['frontier_increment'] > 0
            assert reached(receipt['x'], receipt['threshold'])
            assert reached(receipt['credit'], receipt['threshold'])
            for field, value in receipt.items():
                equal(value, event['receipt'][field], ('receipt', t, h, field))
            equal(returns[t], event['r'], ('return', t, h))
            receipts += 1
            upward += direction == 1
        for (t, h, reason, candidate), event in zip(expected_resets, actual_resets):
            assert (t, h, reason) == (event['observation'], event['horizon'], event['reason'])
            for field, value in candidate.items():
                equal(value, event['candidate'][field], ('reset', t, h, field))
            reset_count += 1
    return dict(independent_rows=rows, all_confirmation_receipts=receipts,
                upward_confirmation_receipts=upward, candidate_resets=reset_count,
                independent_ew_values=ew_values)


def formal(destination):
    destination.mkdir(parents=True, exist_ok=False)
    model = load_model()
    assets = []
    for asset in ASSETS:
        source_path = OLD / 'inputs' / (asset+'.parquet')
        saved_path = ROOT / 'results' / (asset+'.parquet')
        event_path = ROOT / 'results' / (asset+'-events.json')
        f = pd.read_parquet(source_path)
        z = pd.read_parquet(saved_path)
        j = json.loads(event_path.read_text())
        counts = audit_saved(f, z, j, model)
        cutoff = pd.Timestamp('2025-08-29')
        prefix = f.loc[:cutoff]
        assert 65 < len(prefix) < len(f), (asset, len(prefix), len(f))
        prefix_path = destination / (asset+'-physical-prefix-input.parquet')
        prefix.to_parquet(prefix_path)
        reloaded = pd.read_parquet(prefix_path)
        replay, replay_events = model.strength_frame(reloaded)
        fields = model.FIELDS + model.DATE_FIELDS + ['phase']
        pd.testing.assert_frame_equal(replay[fields], z.loc[reloaded.index, fields],
                                      check_exact=True, check_dtype=False, check_freq=False)
        wanted_events = [e for e in j if e['date'] <= str(reloaded.index[-1].date())]
        assert replay_events == wanted_events, (asset, 'physical event prefix')
        assets.append(dict(asset=asset, **counts, physical_prefix_rows=len(reloaded),
                           physical_prefix_last=str(reloaded.index[-1].date()),
                           input_sha256=digest(source_path), saved_sha256=digest(saved_path),
                           journal_sha256=digest(event_path), prefix_sha256=digest(prefix_path)))
    report = dict(recorded_at=datetime.now(timezone.utc).isoformat(), passed=True,
                  model_sha256=digest(ROOT/'code/model.py'), audit_sha256=digest(__file__),
                  assets=assets, account_runs=0, formal_synthetic_runs=0,
                  limitations='Technical protocol audit only; no market truth or economic admission.')
    save(destination/'audit.json', report)
    print(json.dumps(report, ensure_ascii=False))


def probes(destination):
    """Two short manual data-contract probes; explicitly not a fixture batch."""
    model = load_model()
    dates = pd.date_range('2000-01-01', periods=142)
    close = np.exp(np.arange(142)*.001)*100
    f = pd.DataFrame(dict(close=close, volume=100., segment_id='source-a',
                         valid_strength_observation=True), index=dates)
    original, events = model.strength_frame(f)
    invalid = f.copy()
    invalid.iloc[66, invalid.columns.get_loc('valid_strength_observation')] = False
    invalid.iloc[66, invalid.columns.get_loc('close')] = np.nan
    invalid.iloc[66, invalid.columns.get_loc('volume')] = np.nan
    skipped, skipped_events = model.strength_frame(invalid)
    bridge, bridge_events = model.strength_frame(invalid.loc[invalid.valid_strength_observation])
    pd.testing.assert_frame_equal(skipped.loc[bridge.index], bridge)
    assert skipped_events == bridge_events
    assert skipped.loc[dates[66], model.FIELDS].isna().all()
    split = f.copy()
    split.loc[dates[71]:, 'segment_id'] = 'source-b'
    split_z, split_j = model.strength_frame(split)
    standalone, standalone_j = model.strength_frame(split.iloc[71:])
    pd.testing.assert_frame_equal(split_z.iloc[71:], standalone)
    assert [e for e in split_j if e['segment']=='source-b' and e['kind']!='source_discontinuity'] == standalone_j
    rejected = []
    for kind in ('blank_segment', 'missing_segment', 'reused_segment', 'invalid_price',
                 'invalid_volume', 'nullable_validity', 'nonboolean_validity', 'duplicate_date', 'timezone'):
        bad = f.copy()
        if kind == 'blank_segment': bad['segment_id'] = '   '
        if kind == 'missing_segment': bad.loc[dates[0], 'segment_id'] = None
        if kind == 'reused_segment': bad.loc[dates[4], 'segment_id'] = 'other'
        if kind == 'invalid_price': bad.loc[dates[0], 'close'] = 0.
        if kind == 'invalid_volume': bad.loc[dates[0], 'volume'] = np.nan
        if kind == 'nullable_validity':
            bad['valid_strength_observation'] = bad.valid_strength_observation.astype('boolean')
            bad.loc[dates[0], 'valid_strength_observation'] = pd.NA
        if kind == 'nonboolean_validity': bad['valid_strength_observation'] = 1
        if kind == 'duplicate_date': bad.index = pd.DatetimeIndex([dates[0], *dates[:-1]])
        if kind == 'timezone': bad.index = bad.index.tz_localize('UTC')
        try: model.strength_frame(bad)
        except (ValueError, TypeError): rejected.append(kind)
        else: raise AssertionError(('not rejected', kind))
    # An independently accumulated strict frontier must not drift on a sequence
    # whose individual steps are below the declared comparison tolerance.
    tiny = f.iloc[:70].copy()
    tiny['close'] = 100.
    for t in range(64, 70): tiny.iloc[t, tiny.columns.get_loc('close')] = 100.*math.exp((t-63)*2e-15)
    tiny_z, tiny_j = model.strength_frame(tiny)
    audit_saved(tiny, tiny_z, tiny_j, model)
    report = dict(recorded_at=datetime.now(timezone.utc).isoformat(), passed=True,
                  model_sha256=digest(ROOT/'code/model.py'), audit_sha256=digest(__file__),
                  manual_probes=['invalid unknown and bridge', 'new source restart', 'strict tiny frontier'],
                  rejected_inputs=rejected, account_runs=0, real_runs=0,
                  formal_synthetic_runs=0, disclosure='Hand-built contract probes, not formal fixture or market evaluation.')
    save(destination, report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('probes', 'formal'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.mode == 'probes': probes(args.output)
    else: formal(args.output)
