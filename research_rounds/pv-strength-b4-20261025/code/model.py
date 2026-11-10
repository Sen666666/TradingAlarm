"""PVS-B4: returns, EW net pace, event-anchored structures, and acute events.

There is deliberately no global temperature, grade, or trading policy. All times
are positions on the segment's valid-observation clock. Indicators are public
from its 65th valid close; EW pace is nevertheless warmed up from return r_1.
"""

import copy
import math

import numpy as np
import pandas as pd


SCALES = (21, 63)
PACE_SPANS = (5, 21)
INPUT_COLUMNS = ['close', 'volume', 'segment_id', 'valid_strength_observation']
CANDIDATE_FIELDS = [
    'active', 'anchor', 'anchor_price', 'anchor_observation',
    'created_observation', 'threshold', 'scale_at_anchor', 'volume_reference',
    'frontier', 'credit', 'x', 'new_frontier', 'frontier_increment',
    'credit_increment', 'volume_weight',
]
FIELDS = [
    'r', 'r_bp', 'mu5', 'mu21', 'mu5_bp', 'mu21_bp',
    'mu5_direction', 'mu21_direction', 'mu5_magnitude_bp', 'mu21_magnitude_bp',
    's', 'volume_reference', 'activity', 'q', 'qeff', 'acute_down', 'acute_up',
    'S21', 'S63', 'local', 'background', 'building_direction',
]
for _h in SCALES:
    FIELDS.extend([
        f'delta_{_h}', f'confirmed_{_h}', f'confirmed_direction_{_h}',
        f'running_extreme_{_h}', f'running_extreme_price_{_h}',
        f'running_extreme_observation_{_h}',
    ])
    for _side in ('up', 'down'):
        FIELDS.extend(f'{_side}_{field}_{_h}' for field in CANDIDATE_FIELDS)
DATE_FIELDS = [f'{side}_anchor_date_{h}' for h in SCALES for side in ('up', 'down')]
DATE_FIELDS.extend(f'running_extreme_date_{h}' for h in SCALES)


def tol(a, b):
    """The frozen 32-epsilon comparison tolerance, in normalized log units."""
    return 32 * np.finfo(float).eps * max(1., abs(a), abs(b))


def ge(a, b):
    return bool(a >= b - tol(a, b))


def le(a, b):
    return bool(a <= b + tol(a, b))


def gt(a, b):
    """Strict new extrema/frontiers must exceed floating-point noise."""
    return bool(a > b + tol(a, b))


def lt(a, b):
    return bool(a < b - tol(a, b))


def phase_for(local, background):
    """Unknown structure is not a flat or neutral market assessment."""
    if local == 0 or background == 0:
        if local == 0 and background == 0:
            return 'unconfirmed', 0
        return 'building', local or background
    return {
        (1, 1): 'aligned_up',
        (1, -1): 'rebound',
        (-1, 1): 'pullback',
        (-1, -1): 'aligned_down',
    }[(local, background)], 0


def _blank_row():
    row = {field: math.nan for field in FIELDS}
    row.update({field: None for field in DATE_FIELDS})
    row['phase'] = 'unknown'
    return row


def _log_prices(close):
    # Ratios remove the arbitrary price unit before log. Use differences of
    # logs only where extreme but finite positive inputs overflow/underflow.
    with np.errstate(over='ignore', under='ignore', invalid='ignore', divide='ignore'):
        p = np.log(close / close[0])
    exceptional = ~np.isfinite(p)
    if exceptional.any():
        p[exceptional] = np.log(close[exceptional]) - math.log(float(close[0]))
    return p


def run_valid(f, joint=True):
    """Compute one already validated, contiguous source segment.

    joint=False is the explicit price ablation: both structure-credit and
    acute-event volume multipliers are one. Valid positive volume is still
    required by strength_frame. Candidate columns are end-of-day states;
    structure_confirmed journal entries retain the consumed candidate receipt.
    """
    if not isinstance(joint, (bool, np.bool_)):
        raise ValueError('Scalar Boolean joint mode required')
    if len(f) == 0:
        out = pd.DataFrame(index=f.index, columns=FIELDS + DATE_FIELDS + ['phase'])
        out.attrs['terminal'] = None
        return out, []
    close = f.close.to_numpy(float)
    p = _log_prices(close)
    r = np.r_[np.nan, np.diff(p)]
    v = f.volume.to_numpy(float)
    dates = [str(date.date()) for date in f.index]
    rows, journal = [], []
    states = {}
    mu = {h: None for h in PACE_SPANS}

    def emit(t, kind, **fields):
        journal.append(dict(observation=int(t), date=dates[t], kind=kind, **fields))

    def fresh_candidate(t, anchor_t, h, direction, scale, vref, reason, prior=None):
        candidate = dict(
            direction=int(direction), anchor=float(p[anchor_t]),
            anchor_price=float(close[anchor_t]), anchor_observation=int(anchor_t),
            anchor_date=dates[anchor_t], created_observation=int(t),
            threshold=float(math.sqrt(h) * scale), scale_at_anchor=float(scale),
            volume_reference=float(vref), frontier=0., credit=0.,
            x=float(direction * (p[t] - p[anchor_t])), new_frontier=0.,
            frontier_increment=0., credit_increment=0., volume_weight=1.,
        )
        emit(t, 'candidate_reset', horizon=h, reason=reason,
             previous_candidate=copy.deepcopy(prior), candidate=copy.deepcopy(candidate))
        return candidate

    def advance_candidate(t, h, candidate):
        direction = candidate['direction']
        x = float(direction * (p[t] - candidate['anchor']))
        old_frontier, old_credit = candidate['frontier'], candidate['credit']
        extension = gt(x, old_frontier)
        weight = (float(np.clip(math.sqrt(float(v[t] / candidate['volume_reference'])), .5, 2.))
                  if joint else 1.)
        eligible = extension and direction * r[t] > 0.
        # F and Q describe the same accepted frontier. Updating F for tiny
        # sub-tolerance moves while leaving Q fixed would break .5F <= Q.
        frontier = x if eligible else old_frontier
        frontier_increment = float(frontier - old_frontier)
        credit_increment = float((x - old_frontier) * weight) if eligible else 0.
        candidate.update(
            x=x, frontier=float(frontier), credit=float(old_credit + credit_increment),
            new_frontier=float(eligible), frontier_increment=frontier_increment,
            credit_increment=credit_increment, volume_weight=weight,
        )
        if extension:
            emit(t, 'frontier_extended', horizon=h, direction=direction,
                 prior_frontier=float(old_frontier), prior_credit=float(old_credit),
                 direction_return=float(direction * r[t]), eligible_for_credit=bool(eligible),
                 r=float(r[t]), volume=float(v[t]), candidate=copy.deepcopy(candidate))
        confirmed = (eligible and ge(x, candidate['threshold'])
                     and ge(candidate['credit'], candidate['threshold']))
        return bool(confirmed)

    for t in range(len(f)):
        if t >= 1:
            for h in PACE_SPANS:
                alpha = 2. / (h + 1.)
                mu[h] = float(r[t]) if mu[h] is None else float(alpha * r[t] + (1. - alpha) * mu[h])
        row = _blank_row()
        if t < 64:
            rows.append(row)
            continue

        # Exactly the preceding 63 returns and 21 volumes; never today's data.
        scale = max(1.4826 * float(np.median(np.abs(r[t - 63:t]))), 1e-8)
        vref = float(np.median(v[t - 21:t]))
        activity = float(v[t] / vref)
        q = float(r[t] / scale)
        qeff = float(q * math.sqrt(float(np.clip(activity, 1., 4.)) if joint else 1.))
        row.update(
            r=float(r[t]), r_bp=float(1e4 * r[t]), s=scale,
            volume_reference=vref, activity=activity, q=q, qeff=qeff,
            acute_down=float(le(qeff, -2.)), acute_up=float(ge(qeff, 2.)),
        )
        for h in PACE_SPANS:
            row.update({
                f'mu{h}': mu[h], f'mu{h}_bp': 1e4 * mu[h],
                f'mu{h}_direction': float(np.sign(mu[h])),
                f'mu{h}_magnitude_bp': float(1e4 * abs(mu[h])),
            })
        if row['acute_down'] or row['acute_up']:
            emit(t, 'acute_down' if row['acute_down'] else 'acute_up',
                 r=float(r[t]), s=scale, q=q, qeff=qeff, volume=float(v[t]),
                 volume_reference=vref, activity=activity, joint=bool(joint))

        for h in SCALES:
            row[f'delta_{h}'] = float(math.sqrt(h) * scale)
            row[f'confirmed_{h}'] = 0.
            row[f'confirmed_direction_{h}'] = 0.
            if h not in states:
                states[h] = dict(
                    direction=0, high=float(p[t - 1]), low=float(p[t - 1]),
                    high_observation=t - 1, low_observation=t - 1,
                    candidates={
                        1: fresh_candidate(t, t - 1, h, 1, scale, vref, 'initialization'),
                        -1: fresh_candidate(t, t - 1, h, -1, scale, vref, 'initialization'),
                    },
                )
            state = states[h]
            before = state['direction']
            candidates = state['candidates']

            # Only extrema belonging to the active structure are maintained.
            # Before first confirmation both initial candidates are available.
            if before >= 0 and gt(float(p[t]), state['high']):
                state['high'], state['high_observation'] = float(p[t]), t
                candidates[-1] = fresh_candidate(
                    t, t, h, -1, scale, vref, 'new_high', candidates.get(-1))
            if before <= 0 and lt(float(p[t]), state['low']):
                state['low'], state['low_observation'] = float(p[t]), t
                candidates[1] = fresh_candidate(
                    t, t, h, 1, scale, vref, 'new_low', candidates.get(1))

            # A single return cannot provide same-day directional extension in
            # both directions. The assertion also prevents an accidental double
            # confirmation if the implementation changes later.
            confirmations = []
            for direction, candidate in candidates.items():
                if advance_candidate(t, h, candidate):
                    confirmations.append(direction)
            if len(confirmations) > 1:
                raise AssertionError('At most one structure confirmation per scale and observation')
            if confirmations:
                direction = confirmations[0]
                receipt = copy.deepcopy(candidates[direction])
                emit(t, 'structure_confirmed', horizon=h, previous_direction=before,
                     direction=direction, r=float(r[t]), volume=float(v[t]),
                     s=scale, lag_volume_reference=vref,
                     close=float(close[t]), log_close=float(p[t]), joint=bool(joint),
                     receipt=receipt)
                state['direction'] = direction
                row[f'confirmed_{h}'] = 1.
                row[f'confirmed_direction_{h}'] = float(direction)
                state['candidates'] = {
                    -direction: fresh_candidate(
                        t, t, h, -direction, scale, vref, 'direction_confirmed',
                        candidates.get(-direction))
                }
                # On confirmation discard the old structure's extreme. The
                # new direction starts its running high/low at today's close.
                if direction == 1:
                    state.update(high=float(p[t]), high_observation=t,
                                 low=None, low_observation=None)
                else:
                    state.update(low=float(p[t]), low_observation=t,
                                 high=None, high_observation=None)
            row[f'S{h}'] = float(state['direction'])
            for direction, side in ((1, 'up'), (-1, 'down')):
                candidate = state['candidates'].get(direction)
                row[f'{side}_active_{h}'] = float(candidate is not None)
                if candidate is not None:
                    for field in CANDIDATE_FIELDS:
                        if field != 'active':
                            row[f'{side}_{field}_{h}'] = candidate[field]
                    row[f'{side}_anchor_date_{h}'] = candidate['anchor_date']
            if state['direction'] != 0:
                extreme = 'high' if state['direction'] == 1 else 'low'
                extreme_t = state[f'{extreme}_observation']
                row[f'running_extreme_{h}'] = state[extreme]
                row[f'running_extreme_price_{h}'] = float(close[extreme_t])
                row[f'running_extreme_observation_{h}'] = float(extreme_t)
                row[f'running_extreme_date_{h}'] = dates[extreme_t]

        local, background = int(row['S21']), int(row['S63'])
        phase, building_direction = phase_for(local, background)
        row.update(local=float(local), background=float(background), phase=phase,
                   building_direction=float(building_direction))
        rows.append(row)

    out = pd.DataFrame(rows, index=f.index, columns=FIELDS + DATE_FIELDS + ['phase'])
    out.attrs['terminal'] = copy.deepcopy(states) if states else None
    return out, journal


def strength_frame(f, joint=True):
    """Return a causal indicator frame and journal, restarting per source segment.

    Invalid observations remain entirely unknown, and do not advance the valid
    clock. A later valid close bridges their price gap. Missing/invalid source
    identities are rejected; a new explicit segment restarts all warm-up and
    structure state and archives the old state as a source discontinuity.
    """
    if not isinstance(joint, (bool, np.bool_)):
        raise ValueError('Scalar Boolean joint mode required')
    if not isinstance(f.index, pd.DatetimeIndex) or f.index.tz is not None:
        raise ValueError('Naive DatetimeIndex required')
    if not f.index.is_unique or not f.index.is_monotonic_increasing or f.index.hasnans:
        raise ValueError('Ordered unique dated observations required')
    if any(column not in f for column in INPUT_COLUMNS):
        raise ValueError('close, volume, segment_id and valid_strength_observation required')
    if f.segment_id.isna().any():
        raise ValueError('Explicit source segment required')
    if any(isinstance(segment, str) and not segment.strip() for segment in f.segment_id):
        raise ValueError('Nonempty source segment identity required')
    blocks = f.segment_id.loc[f.segment_id.ne(f.segment_id.shift())]
    if blocks.duplicated().any():
        raise ValueError('Noncontiguous segment identity')
    if (not pd.api.types.is_bool_dtype(f.valid_strength_observation)
            or f.valid_strength_observation.isna().any()):
        raise ValueError('Non-null Boolean validity required')
    out = pd.DataFrame(np.nan, index=f.index, columns=FIELDS)
    for column in DATE_FIELDS:
        out[column] = pd.Series(None, index=f.index, dtype=object)
    out['phase'] = 'unknown'
    journal, terminal, previous = [], None, None
    for segment, group in f.groupby('segment_id', sort=False):
        if terminal:
            journal.append(dict(
                segment=str(segment), date=str(group.index[0].date()), observation=None,
                kind='source_discontinuity', previous_segment=previous,
                unresolved=terminal,
            ))
        good = group.loc[group.valid_strength_observation]
        if len(good):
            a = good[['close', 'volume']].to_numpy(float)
            if not np.isfinite(a).all() or not (a > 0).all():
                raise ValueError('Finite positive valid price/volume required')
            frame, events = run_valid(good, joint)
            out.loc[good.index, frame.columns] = frame
            journal.extend(dict(segment=str(segment), **event) for event in events)
            terminal = frame.attrs['terminal']
        else:
            terminal = None
        previous = str(segment)
    out.attrs['terminal'] = terminal
    out.attrs['model'] = 'PVS-B4'
    out.attrs['pace_units'] = 'mu5/mu21: log return per valid observation; *_bp: log bp per valid observation'
    return out, journal
