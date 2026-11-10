"""Explicit binary64 boundary policy; no account or new trend mechanism.

The original event_frame is retained elsewhere as an immutable control.
Numerically indistinguishable prices retain the earlier extreme/old floor.
This is an error-budget convention, not a financial price tolerance.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd


UNIT_ROUNDOFF = np.finfo(np.float64).eps / 2
# Two input encodings plus one unit multiplication on each side of a comparison.
# A machine-precision comparison policy motivated by that four-rounding model.
# The prior adjustment/serialization pipelines are not certified to obey it.
ROUNDING_STEPS = 4
GAMMA4 = ROUNDING_STEPS * UNIT_ROUNDOFF / (1 - ROUNDING_STEPS * UNIT_ROUNDOFF)


def compare(a: float, b: float) -> int:
    """Order finite nonnegative magnitudes, treating the gamma4 band as a tie.

    Homogeneous in exact arithmetic. Independent rounded rescaling can move an
    input on the band's boundary across it; universal scale invariance is NOT
    promised. Comparisons outside this band remain strict.
    """
    a, b = float(a), float(b)
    if not (math.isfinite(a) and math.isfinite(b) and a >= 0 and b >= 0):
        raise ValueError("finite nonnegative magnitudes required")
    if abs(a - b) <= GAMMA4 * max(a, b):
        return 0
    return 1 if a > b else -1


def log_ratio(a: float, b: float) -> float:
    """Local log change without subtracting two origin-normalized logarithms."""
    a, b = float(a), float(b)
    if not (math.isfinite(a) and math.isfinite(b) and a > 0 and b > 0):
        raise ValueError("finite positive prices required")
    if compare(a, b) == 0:
        return 0.0
    # log1p preserves a small displacement. The far-down case avoids rounding
    # (a-b)/b to -1. At the branch boundary, rounded rescaling can select the
    # other algebraically equivalent expression; universal bit equality is not promised.
    if 0.5 <= a / b <= 2:
        return math.log1p((a - b) / b)
    return math.log(a) - math.log(b)


def higher(old: float, new: float) -> float:
    """The existing ratchet retains its actual old point on a numerical tie."""
    return float(new) if compare(new, old) > 0 else float(old)


def event_frame_numeric(close, volume, joint=True, event_exit=False):
    """Numerical repair of frozen event+structure equations, separately named.

    Same observation clock, warmup, 21/63/5 constants, activity clipping,
    confirmation >=1, floor <=, and same-day exit priority. Numerical changes:
    raw-price extrema/floors with an explicit tie policy; local log returns;
    local fsum instead of long cumulative-volume subtraction.
    Original output log fields are display only; raw pivot fields are canonical.
    """
    if not close.index.is_unique or not close.index.is_monotonic_increasing:
        raise ValueError("ordered unique index required")
    raw = pd.concat([close.rename("close"), volume.rename("volume")], axis=1)
    d = raw.loc[raw.gt(0).all(axis=1) & np.isfinite(raw).all(axis=1)]
    if d.empty:
        raise ValueError("no valid observations")
    prices, volumes = d.close.to_numpy(), d.volume.to_numpy()
    returns = [math.nan] + [log_ratio(prices[t], prices[t - 1])
                              for t in range(1, len(d))]
    sigma = np.full(len(d), np.nan)
    baseline = d.volume.shift().rolling(21).median().to_numpy()
    for t in range(64, len(d)):
        sigma[t] = max(math.sqrt(math.fsum(x * x for x in returns[t - 63:t]) / 63), 1e-8)
    direction, ext, active, floor = -1, None, False, math.nan
    rows = []
    for t, date in enumerate(d.index):
        row = dict(confirmation=math.nan, leg_direction=math.nan,
                   developing_extreme=math.nan, confirmed_pivot=math.nan,
                   structure_floor=math.nan, event=0.0, target=0.0,
                   entered=0.0, exited=0.0, pivot_age=math.nan,
                   developing_extreme_price=math.nan, confirmed_pivot_price=math.nan,
                   structure_floor_price=math.nan, confirmed_pivot_date=None,
                   developing_extreme_date=None)
        if not math.isfinite(sigma[t] + baseline[t]):
            rows.append(row)
            continue
        if ext is None:
            ext = t
        if active and not event_exit and compare(prices[t], floor) <= 0:
            active, row["exited"] = False, 1.0
        extreme_order = compare(prices[t], prices[ext])
        if (direction == -1 and extreme_order < 0) or (direction == 1 and extreme_order > 0):
            ext = t
        if t > ext:
            activity = math.sqrt(
                (math.fsum(float(x) for x in volumes[ext + 1:t + 1]) / (t - ext))
                / baseline[ext]
            ) if joint else 1.0
            activity = min(max(activity, 0.5), 2.0)
            confirmation = (-direction) * log_ratio(prices[t], prices[ext]) * activity / (math.sqrt(5) * sigma[ext])
            row["confirmation"] = confirmation
            # A numerically indistinguishable exact threshold is inclusive.
            if compare(max(confirmation, 0.0), 1.0) >= 0:
                event = -direction
                pivot = float(prices[ext])
                row.update(event=float(event), confirmed_pivot=math.log(pivot),
                           confirmed_pivot_price=pivot, pivot_age=float(t - ext),
                           confirmed_pivot_date=str(d.index[ext].date()))
                if event == 1:
                    if active:
                        floor = higher(floor, pivot)
                    elif not row["exited"]:
                        active, floor, row["entered"] = True, pivot, 1.0
                elif event_exit and active:
                    active, row["exited"] = False, 1.0
                direction, ext = event, t
        row.update(leg_direction=float(direction),
                   developing_extreme=math.log(float(prices[ext])),
                   developing_extreme_price=float(prices[ext]),
                   developing_extreme_date=str(d.index[ext].date()), target=float(active))
        if active or row["exited"]:
            row.update(structure_floor=math.log(floor), structure_floor_price=floor)
        rows.append(row)
    result = pd.DataFrame(rows, index=d.index).reindex(close.index)
    for col in ("event", "entered", "exited"):
        result[col] = result[col].fillna(0.0)
    result["target"] = result.target.ffill().fillna(0.0)
    for col in ("confirmed_pivot_date", "developing_extreme_date"):
        result[col] = result[col].astype("string")
    return result


def failed_attempts(bars, events):
    """The previous v0 position facts under the new arithmetic, not a model run."""
    peak, trough = math.nan, math.nan
    output = []
    for date, bar in bars.iterrows():
        up = math.isfinite(peak) and compare(bar.high, peak) > 0 and compare(bar.close, peak) <= 0
        down = math.isfinite(trough) and compare(bar.low, trough) < 0 and compare(bar.close, trough) >= 0
        output.append(int(compare(bar.high, bar.low) > 0 and (up or down)))
        row = events.loc[date]
        if row.event == -1:
            peak = float(row.confirmed_pivot_price)
        elif row.event == 1:
            trough = float(row.confirmed_pivot_price)
    return pd.Series(output, index=bars.index, name="price_attempt")
