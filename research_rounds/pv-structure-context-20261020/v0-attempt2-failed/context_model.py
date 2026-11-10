"""Causal price structure and volume-conditioned description, version 0.

The price skeleton uses confirmed alternating pivots. Volume describes the
quality of the last two *completed* legs; it does not accelerate pivot detection.
Regime, completed-leg quality, developing direction, and relative-strength
ingredients have separate meanings. None is a probability or a position.

All calculations use the common finite, positive close/volume observation clock.
Scales use information preceding the extreme/observation; pivots are emitted at
their confirmation time, never backdated to their actual extreme. The confirmed
pair can be stale because this version deliberately ignores the developing leg.
No account, order, external model, filesystem, or network is accessed here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def _date(value):
    """Stable readable source-index label; dates are not required for the math."""
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def context_frame(close: pd.Series, volume: pd.Series) -> pd.DataFrame:
    """Return causal observations on exactly the input index.

    ``log_price``, pivots, developing extrema, floor, and ceiling are natural-log
    prices. ``pivot_idx`` and other ``*_idx`` values index the common valid clock;
    their ``*_date`` companions identify the original observation labels.
    Event +1 confirms a LOW and starts an upward developing leg; event -1 confirms
    a HIGH and starts a downward leg. Regime +1/-1/0 means up/down/unestablished.

    Old boundaries are checked first (close <= floor / close >= ceiling).
    Previously frozen candidates can earn a boundary only on a later observation
    than their confirmation. New pivots are processed last. A boundary break
    cannot establish a new regime on the same observation; later establishment
    requires a new pivot and strict HH+HL or LH+LL.

    ``phase`` and ``price_phase`` describe the last confirmed pair under today's
    regime. ``e`` is later/prior mean normalized volume; ``s`` is later/prior
    absolute log displacement per valid observation. Equalities are contested
    (or same_speed for price_phase), never silently assigned a direction.
    Invalid rows carry previously known descriptors, but no event, new pivot,
    boundary-change flag, or current log price is emitted.
    """
    if not isinstance(close, pd.Series) or not isinstance(volume, pd.Series):
        raise TypeError("close and volume must be pandas Series")
    if not close.index.equals(volume.index):
        raise ValueError("close and volume must have identical indexes")
    if not close.index.is_unique or not close.index.is_monotonic_increasing:
        raise ValueError("ordered unique index required")
    if close.index.hasnans:
        raise ValueError("null index labels are not supported")

    raw = pd.DataFrame({
        "close": pd.to_numeric(close, errors="coerce"),
        "volume": pd.to_numeric(volume, errors="coerce"),
    })
    valid = (
        np.isfinite(raw["close"]) & raw["close"].gt(0)
        & np.isfinite(raw["volume"]) & raw["volume"].gt(0)
    )
    d = raw.loc[valid]
    if d.empty:
        raise ValueError("no valid observations")

    y = np.log(d["close"].to_numpy(dtype=float))
    returns = pd.Series(y).diff()
    sigma = (
        returns.shift(1).pow(2).rolling(63, min_periods=63).mean()
        .pow(0.5).clip(lower=1e-8).to_numpy()
    )
    volume_base = d["volume"].shift(1).rolling(21, min_periods=21).median()
    volume_ratio = (d["volume"] / volume_base).to_numpy()
    c = d["close"]
    rs_score = (
        .4 * (c / c.shift(63) - 1)
        + .2 * (c.shift(63) / c.shift(126) - 1)
        + .2 * (c.shift(126) / c.shift(189) - 1)
        + .2 * (c.shift(189) / c.shift(252) - 1)
    ).to_numpy()
    bb_mid = c.rolling(20, min_periods=20).mean()
    bb_std = c.rolling(20, min_periods=20).std(ddof=0)
    bb_upper, bb_lower = bb_mid + 2 * bb_std, bb_mid - 2 * bb_std
    bb_width = bb_upper - bb_lower
    percent_b = ((c - bb_lower) / bb_width.where(bb_width > 0)).to_numpy()
    bandwidth = (bb_width / bb_mid).to_numpy()
    bb_mid, bb_std = bb_mid.to_numpy(), bb_std.to_numpy()
    bb_upper, bb_lower = bb_upper.to_numpy(), bb_lower.to_numpy()

    direction = -1
    extreme = None
    regime = 0
    floor = ceiling = np.nan
    highs, lows, pivots, legs = [], [], [], []
    up_candidate = down_candidate = None
    rows = []

    for t in range(len(d)):
        event = 0
        pivot = None
        confirmation = np.nan
        broken = False
        boundary_earned = False
        broken_boundary = np.nan
        state_reason = "unchanged"
        ready = bool(np.isfinite(sigma[t]))

        if ready:
            if extreme is None:
                extreme = t
            # Invalidation uses the boundary already known before this bar.
            if (regime == 1 and y[t] <= floor) or (
                regime == -1 and y[t] >= ceiling
            ):
                broken_boundary = floor if regime == 1 else ceiling
                regime = 0
                floor = ceiling = np.nan
                up_candidate = down_candidate = None
                broken = True
                state_reason = "broken"

            # A candidate must survive until it earns promotion.
            if up_candidate is not None and y[t] <= up_candidate["low"]:
                up_candidate = None
            if down_candidate is not None and y[t] >= down_candidate["high"]:
                down_candidate = None

            # A local pivot alone cannot tighten a structural boundary.
            if (
                regime == 1 and up_candidate is not None
                and t > up_candidate["confirmed_idx"]
                and y[t] > up_candidate["high"]
                and up_candidate["low"] > floor
            ):
                floor = up_candidate["low"]
                up_candidate = None
                boundary_earned = True
                state_reason = "floor_earned"
            if (
                regime == -1 and down_candidate is not None
                and t > down_candidate["confirmed_idx"]
                and y[t] < down_candidate["low"]
                and down_candidate["high"] < ceiling
            ):
                ceiling = down_candidate["high"]
                down_candidate = None
                boundary_earned = True
                state_reason = "ceiling_earned"

            if (direction == -1 and y[t] < y[extreme]) or (
                direction == 1 and y[t] > y[extreme]
            ):
                extreme = t
            if t > extreme:
                confirmation = (
                    -direction * (y[t] - y[extreme])
                    / (np.sqrt(5.0) * sigma[extreme])
                )
                if confirmation >= 1:
                    event = -direction
                    pivot = {
                        "value": float(y[extreme]), "idx": int(extreme),
                        "date": _date(d.index[extreme]),
                        "confirmed_idx": t, "confirmed_date": _date(d.index[t]),
                        "kind": "low" if event == 1 else "high",
                    }
                    if pivots:
                        previous = pivots[-1]
                        n = pivot["idx"] - previous["idx"]
                        if n <= 0:
                            raise AssertionError("confirmed pivot dates must advance")
                        displacement = pivot["value"] - previous["value"]
                        activity = volume_ratio[previous["idx"] + 1:pivot["idx"] + 1]
                        legs.append({
                            "start_idx": previous["idx"], "end_idx": pivot["idx"],
                            "start_date": previous["date"], "end_date": pivot["date"],
                            "confirmed_idx": t, "confirmed_date": _date(d.index[t]),
                            "direction": int(np.sign(displacement)),
                            "n": n, "displacement": abs(displacement),
                            "effort": float(np.mean(activity)),
                            "speed": abs(displacement) / n,
                        })
                        legs = legs[-2:]
                    pivots.append(pivot)
                    pivots = pivots[-1:]
                    if event == 1:
                        lows.append(pivot)
                        lows = lows[-2:]
                        if regime == 1 and highs:
                            up_candidate = {
                                "low": pivot["value"], "high": highs[-1]["value"],
                                "confirmed_idx": t,
                                "low_idx": pivot["idx"], "high_idx": highs[-1]["idx"],
                                "confirmed_date": _date(d.index[t]),
                            }
                    else:
                        highs.append(pivot)
                        highs = highs[-2:]
                        if regime == -1 and lows:
                            down_candidate = {
                                "high": pivot["value"], "low": lows[-1]["value"],
                                "confirmed_idx": t,
                                "high_idx": pivot["idx"], "low_idx": lows[-1]["idx"],
                                "confirmed_date": _date(d.index[t]),
                            }
                    direction = event
                    extreme = t
                    if regime == 0 and not broken and len(highs) == len(lows) == 2:
                        if (
                            highs[-1]["value"] > highs[-2]["value"]
                            and lows[-1]["value"] > lows[-2]["value"]
                            and y[t] > lows[-1]["value"]
                        ):
                            regime = 1
                            floor, ceiling = lows[-1]["value"], np.nan
                            state_reason = "established_up"
                        elif (
                            highs[-1]["value"] < highs[-2]["value"]
                            and lows[-1]["value"] < lows[-2]["value"]
                            and y[t] < highs[-1]["value"]
                        ):
                            regime = -1
                            ceiling, floor = highs[-1]["value"], np.nan
                            state_reason = "established_down"

        e = s = retrace = np.nan
        phase = price_phase = "unknown"
        if len(legs) == 2:
            before, after = legs
            e = after["effort"] / before["effort"] if before["effort"] > 0 else np.nan
            s = after["speed"] / before["speed"] if before["speed"] > 0 else np.nan
            retrace = (
                after["displacement"] / before["displacement"]
                if before["displacement"] > 0 else np.nan
            )
            if np.isfinite(s):
                price_phase = "slower" if s < 1 else ("faster" if s > 1 else "same_speed")
            if np.isfinite(e) and np.isfinite(s) and regime:
                if after["direction"] == regime:
                    phase = "supported" if e > 1 and s > 1 else (
                        "quiet" if e < 1 and s < 1 else "contested"
                    )
                else:
                    phase = "orderly" if e < 1 and s < 1 else (
                        "opposing_pressure" if e > 1 and s > 1 else "contested"
                    )
        if regime == 0:
            phase = price_phase = "unresolved"

        row = {
            "valid": True, "ready": ready, "valid_idx": t, "log_price": y[t],
            "sigma": sigma[t], "volume_ratio": volume_ratio[t],
            "confirmation": confirmation, "developing_direction": direction,
            "developing_extreme": y[extreme] if extreme is not None else np.nan,
            "developing_extreme_idx": extreme if extreme is not None else np.nan,
            "developing_extreme_date": _date(d.index[extreme]) if extreme is not None else "",
            "regime": regime, "state_reason": state_reason,
            "structure_floor": floor, "structure_ceiling": ceiling,
            "event": event, "broken": broken, "boundary_earned": boundary_earned,
            "broken_boundary": broken_boundary,
            "pivot": pivot["value"] if pivot else np.nan,
            "pivot_idx": pivot["idx"] if pivot else np.nan,
            "pivot_date": pivot["date"] if pivot else "",
            "pivot_confirmed_idx": t if pivot else np.nan,
            "pivot_confirmed_date": _date(d.index[t]) if pivot else "",
            "pivot_kind": pivot["kind"] if pivot else "",
            "phase_source": "confirmed_pair", "phase": phase,
            "price_phase": price_phase, "e": e, "s": s, "retrace": retrace,
            "oneil_inspired_score": rs_score[t],
            "bb_mid": bb_mid[t], "bb_std": bb_std[t],
            "bb_upper": bb_upper[t], "bb_lower": bb_lower[t],
            "percent_b": percent_b[t], "bandwidth": bandwidth[t],
        }
        for stem, values in (("high", highs), ("low", lows)):
            for suffix, j in (("last", -1), ("previous", -2)):
                item = values[j] if len(values) >= -j else None
                for field in ("value", "idx", "date", "confirmed_idx", "confirmed_date"):
                    name = f"{suffix}_{stem}" if field == "value" else f"{suffix}_{stem}_{field}"
                    row[name] = item[field] if item else ("" if "date" in field else np.nan)
        for stem, candidate in (("up_candidate", up_candidate), ("down_candidate", down_candidate)):
            for field in ("low", "high", "low_idx", "high_idx", "confirmed_idx", "confirmed_date"):
                row[f"{stem}_{field}"] = (
                    candidate[field] if candidate else ("" if "date" in field else np.nan)
                )
        for j in range(2):
            leg = legs[j] if len(legs) == 2 else None
            for field in (
                "start_idx", "end_idx", "start_date", "end_date",
                "confirmed_idx", "confirmed_date", "direction", "n",
                "displacement", "effort", "speed",
            ):
                row[f"leg{j + 1}_{field}"] = (
                    leg[field] if leg else ("" if "date" in field else np.nan)
                )
        rows.append(row)

    output = pd.DataFrame(rows, index=d.index).reindex(close.index)
    # Reindex via last valid row rather than column-wise ffill: a real NaN/empty
    # after invalidation must not resurrect an earlier boundary or candidate.
    valid_locations = pd.Series(np.arange(len(d)), index=d.index).reindex(close.index).ffill()
    has_previous = valid_locations.notna()
    invalid_with_previous = (~valid) & has_previous
    if invalid_with_previous.any():
        carried = pd.DataFrame(rows, index=d.index).iloc[
            valid_locations.loc[invalid_with_previous].astype(int).to_numpy()
        ]
        output.loc[invalid_with_previous, :] = carried.to_numpy()
    invalid = ~valid
    output.loc[invalid, "valid"] = False
    output.loc[invalid, "event"] = 0
    for field in ("broken", "boundary_earned"):
        output.loc[invalid, field] = False
    for field in (
        "log_price", "pivot", "pivot_idx", "pivot_confirmed_idx", "broken_boundary",
        "confirmation", "sigma", "volume_ratio",
    ):
        output.loc[invalid, field] = np.nan
    for field in ("pivot_date", "pivot_confirmed_date", "pivot_kind"):
        output.loc[invalid, field] = ""
    output.loc[invalid, "state_reason"] = "invalid_observation"
    before_first = invalid & ~has_previous
    output.loc[before_first, "regime"] = 0
    output.loc[before_first, "ready"] = False
    output.loc[before_first, "developing_direction"] = -1
    output.loc[before_first, ["phase", "price_phase"]] = "unresolved"
    output.loc[before_first, "phase_source"] = "confirmed_pair"
    for field in ("valid", "ready", "broken", "boundary_earned"):
        output[field] = output[field].astype(bool)
    for field in ("regime", "developing_direction", "event"):
        output[field] = output[field].astype(int)
    return output
