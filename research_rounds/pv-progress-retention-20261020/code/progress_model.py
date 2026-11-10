"""Two-scale causal hysteresis with retained-progress and volume descriptions.

The sqrt(21) primary scale and unchanged sqrt(5) local scale are an explicit
comparison within the known hysteresis family, not a claimed new theory.
Price boundaries, progress retained, reaction/recovery, and volume activity are
reported separately. No description is a probability, health guarantee, position,
or order. This module performs no filesystem, network, or account I/O.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from context_model import context_frame as _local_frame

EPSILON = 1e-12
PRIMARY_SCALE = np.sqrt(21.0)


def _date(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def progress_frame(close: pd.Series, volume: pd.Series) -> pd.DataFrame:
    """Return exactly the input index using the shared positive-price/volume clock.

    Prices named origin/extreme are natural logs. ``*_idx`` values use the common
    valid observation clock. A developing primary extreme is known at its actual
    observation but unconfirmed; its confirmation is recorded only at the later
    reversal event. Confirmation events never rewrite the prior output rows.

    Initialization follows running min/max after the first ready sigma. Movement
    from either extreme must reach sqrt(21) times the lagged-63-return RMS frozen
    at that extreme. If both qualify, the larger normalized excursion wins (an
    exact tie chooses upward). Later reversals use the same anchored threshold.
    Comparisons of same prices and strict parent-boundary breaches use 1e-12.

    Parent age starts at its creation/confirmation date, not its old origin.
    Parent endpoints survive local primary flips while price remains between
    them. Crossing beyond the parent's extreme or origin resolves it. Existing
    parent resolution precedes a same-day primary flip; a proposed new parent
    already beyond its endpoints is resolved immediately rather than stored.

    Volume intervals are descriptive backgrounds: advance is (O,E], current
    post-extreme/erosion activity is (E,t], peak-to-trough is (E,T], and recovery
    is (T,t]. The latter two partition the post-extreme interval and overlap its
    summary. They are not independent buying/selling volumes or current-day
    volume. Erosion-relative uses (E,t] / (O,E]; recovery-relative uses
    (T,t] / (E,T], keeping both the fresh background and the frozen trough basis.
    """
    base = _local_frame(close, volume)
    good = base.loc[base.valid]
    labels = good.index
    y = good.log_price.to_numpy(dtype=float)
    sigma = good.sigma.to_numpy(dtype=float)
    q = good.volume_ratio.to_numpy(dtype=float)
    local_direction = good.developing_direction.to_numpy(dtype=int)
    ready = good.ready.to_numpy(dtype=bool)

    direction = 0
    origin = extreme = reaction = None
    origin_confirmed = None
    initial_min = initial_max = None
    parent = None
    rows = []

    def mean_q(start, end):
        if start is None or end is None or end <= start:
            return np.nan
        values = q[start + 1:end + 1]
        return float(np.mean(values)) if np.isfinite(values).all() else np.nan

    def ratio(numerator, denominator):
        return (
            float(numerator / denominator)
            if np.isfinite(numerator) and np.isfinite(denominator)
            and denominator > EPSILON else np.nan
        )

    def resolution(candidate, t):
        d, o, e = candidate["direction"], candidate["origin_idx"], candidate["extreme_idx"]
        if d * (y[t] - y[e]) > EPSILON:
            return "reclaimed"
        if d * (y[t] - y[o]) < -EPSILON:
            return "fully_eroded"
        return ""

    for t in range(len(good)):
        event = 0
        initialized = flipped = parent_created = False
        confirmed_extreme = None
        resolutions = []
        if parent is not None:
            resolved = resolution(parent, t)
            if resolved:
                resolutions.append((resolved, parent.copy()))
                parent = None

        if ready[t]:
            if direction == 0:
                if initial_min is None:
                    initial_min = initial_max = t
                if y[t] < y[initial_min] - EPSILON:
                    initial_min = t
                if y[t] > y[initial_max] + EPSILON:
                    initial_max = t
                upward = (y[t] - y[initial_min]) / (PRIMARY_SCALE * sigma[initial_min])
                downward = (y[initial_max] - y[t]) / (PRIMARY_SCALE * sigma[initial_max])
                if max(upward, downward) >= 1.0:
                    direction = 1 if upward >= downward else -1
                    origin = initial_min if direction == 1 else initial_max
                    origin_confirmed = t
                    extreme = reaction = t
                    event, initialized = direction, True
            else:
                if direction * (y[t] - y[extreme]) > EPSILON:
                    extreme = reaction = t
                else:
                    if direction * (y[reaction] - y[t]) > EPSILON:
                        reaction = t
                    reverse = (
                        direction * (y[extreme] - y[t])
                        / (PRIMARY_SCALE * sigma[extreme])
                    )
                    if reverse >= 1.0:
                        old = {
                            "direction": direction, "origin_idx": origin,
                            "extreme_idx": extreme,
                            "origin_confirmed_idx": origin_confirmed,
                            "extreme_confirmed_idx": t, "created_idx": t,
                        }
                        confirmed_extreme = extreme
                        if parent is None:
                            resolved = resolution(old, t)
                            if resolved:
                                resolutions.append((resolved, old))
                            else:
                                parent = old
                                parent_created = True
                        direction = -direction
                        origin, origin_confirmed = extreme, t
                        extreme = reaction = t
                        event, flipped = direction, True

        retention = erosion = recovery = drawdown_z = np.nan
        advance_activity = erosion_activity = recovery_activity = np.nan
        peak_to_trough_activity = np.nan
        erosion_relative = recovery_relative = np.nan
        stage = "unestablished"
        if direction:
            progress = direction * (y[extreme] - y[origin])
            retreat = direction * (y[extreme] - y[t])
            reaction_depth = direction * (y[extreme] - y[reaction])
            retention = ratio(direction * (y[t] - y[origin]), progress)
            erosion = ratio(retreat, progress)
            recovery = ratio(direction * (y[t] - y[reaction]), reaction_depth)
            drawdown_z = retreat / sigma[extreme]
            stage = (
                "expanding" if extreme == t else
                ("repairing" if local_direction[t] == direction else "eroding")
            )
            advance_activity = mean_q(origin, extreme)
            erosion_activity = mean_q(extreme, t)
            peak_to_trough_activity = mean_q(extreme, reaction)
            recovery_activity = mean_q(reaction, t)
            erosion_relative = ratio(erosion_activity, advance_activity)
            recovery_relative = ratio(recovery_activity, peak_to_trough_activity)

        activity_by_stage = {
            "expanding": ("advance_activity", advance_activity),
            "eroding": ("erosion_relative", erosion_relative),
            "repairing": ("recovery_relative", recovery_relative),
        }
        activity_reference, activity_ratio = activity_by_stage.get(stage, ("none", np.nan))
        if not np.isfinite(activity_ratio):
            volume_context = "unknown"
        elif activity_ratio > 1 + EPSILON:
            volume_context = "above_reference"
        elif activity_ratio < 1 - EPSILON:
            volume_context = "below_reference"
        else:
            volume_context = "equal_reference"

        row = {
            "valid": True, "ready": bool(ready[t]), "valid_idx": t,
            "log_price": y[t], "close": float(np.exp(y[t])), "sigma": sigma[t], "q": q[t],
            "local_direction": int(local_direction[t]),
            "local_event": int(good.iloc[t].event),
            "comparison_regime": int(good.iloc[t].regime),
            "comparison_phase": good.iloc[t].phase,
            "comparison_structure_floor": good.iloc[t].structure_floor,
            "comparison_structure_ceiling": good.iloc[t].structure_ceiling,
            "primary_direction": direction, "primary_event": event,
            "primary_initialized": initialized, "primary_flip": flipped,
            "primary_origin": y[origin] if origin is not None else np.nan,
            "primary_origin_idx": origin if origin is not None else np.nan,
            "primary_origin_date": _date(labels[origin]) if origin is not None else "",
            "primary_origin_confirmed_idx": origin_confirmed if origin is not None else np.nan,
            "primary_origin_confirmed_date": _date(labels[origin_confirmed]) if origin is not None else "",
            "primary_extreme": y[extreme] if extreme is not None else np.nan,
            "primary_extreme_idx": extreme if extreme is not None else np.nan,
            "primary_extreme_date": _date(labels[extreme]) if extreme is not None else "",
            "primary_extreme_known_idx": extreme if extreme is not None else np.nan,
            "primary_extreme_confirmed_idx": np.nan,
            "primary_extreme_confirmed_date": "",
            "reaction_extreme": y[reaction] if reaction is not None else np.nan,
            "reaction_extreme_idx": reaction if reaction is not None else np.nan,
            "reaction_extreme_date": _date(labels[reaction]) if reaction is not None else "",
            "confirmed_extreme": y[confirmed_extreme] if confirmed_extreme is not None else np.nan,
            "confirmed_extreme_idx": confirmed_extreme if confirmed_extreme is not None else np.nan,
            "confirmed_extreme_date": _date(labels[confirmed_extreme]) if confirmed_extreme is not None else "",
            "confirmed_extreme_confirmed_idx": t if confirmed_extreme is not None else np.nan,
            "confirmed_extreme_confirmed_date": _date(labels[t]) if confirmed_extreme is not None else "",
            "stage": stage, "retention": retention, "erosion": erosion,
            "recovery": recovery, "drawdown_z": drawdown_z,
            "advance_activity": advance_activity, "erosion_activity": erosion_activity,
            "peak_to_trough_activity": peak_to_trough_activity,
            "recovery_activity": recovery_activity,
            "erosion_relative": erosion_relative, "recovery_relative": recovery_relative,
            "volume_context": volume_context, "volume_context_ratio": activity_ratio,
            "volume_context_reference": activity_reference,
            "pv_state": f"{stage}/{volume_context}",
            "parent_created": parent_created,
            "parent_resolution": "|".join(reason for reason, _ in resolutions),
            "parent_resolution_count": len(resolutions),
            "parent_direction": parent["direction"] if parent else 0,
            "parent_age": t - parent["created_idx"] if parent else np.nan,
            "parent_context": (
                "counter_parent" if parent and direction != parent["direction"]
                else "aligned_parent" if parent else "none"
            ),
        }
        for field in ("origin", "extreme"):
            index = parent[f"{field}_idx"] if parent else None
            confirmed = parent[f"{field}_confirmed_idx"] if parent else None
            row[f"parent_{field}"] = y[index] if parent else np.nan
            row[f"parent_{field}_idx"] = index if parent else np.nan
            row[f"parent_{field}_date"] = _date(labels[index]) if parent else ""
            row[f"parent_{field}_confirmed_idx"] = confirmed if parent else np.nan
            row[f"parent_{field}_confirmed_date"] = _date(labels[confirmed]) if parent else ""
        row["parent_created_idx"] = parent["created_idx"] if parent else np.nan
        row["parent_created_date"] = _date(labels[parent["created_idx"]]) if parent else ""
        row["parent_retention"] = (
            ratio(
                parent["direction"] * (y[t] - y[parent["origin_idx"]]),
                parent["direction"] * (y[parent["extreme_idx"]] - y[parent["origin_idx"]]),
            ) if parent else np.nan
        )
        for j in range(2):
            reason, resolved_parent = resolutions[j] if len(resolutions) > j else ("", None)
            row[f"parent_resolution_{j + 1}"] = reason
            row[f"parent_resolution_{j + 1}_direction"] = resolved_parent["direction"] if resolved_parent else 0
            for field in ("origin_idx", "extreme_idx", "created_idx"):
                row[f"parent_resolution_{j + 1}_{field}"] = (
                    resolved_parent[field] if resolved_parent else np.nan
                )
        if len(resolutions) > 2:
            raise AssertionError("at most an existing and a proposed parent can resolve")
        rows.append(row)

    valid_output = pd.DataFrame(rows, index=good.index)
    output = valid_output.reindex(close.index)
    locations = pd.Series(np.arange(len(good)), index=good.index).reindex(close.index).ffill()
    invalid = ~base.valid
    has_previous = locations.notna()
    carried_rows = invalid & has_previous
    if carried_rows.any():
        output.loc[carried_rows, :] = valid_output.iloc[
            locations.loc[carried_rows].astype(int).to_numpy()
        ].to_numpy()
    leading = invalid & ~has_previous
    bool_columns = ["valid", "ready", "primary_initialized", "primary_flip", "parent_created"]
    int_columns = [
        "local_direction", "local_event", "comparison_regime", "primary_direction",
        "primary_event", "parent_direction", "parent_resolution_count",
        "parent_resolution_1_direction", "parent_resolution_2_direction",
    ]
    for column in output.columns:
        if column in bool_columns:
            output.loc[leading, column] = False
        elif column in int_columns:
            output.loc[leading, column] = 0
        elif valid_output[column].dtype == object:
            output.loc[leading, column] = ""
    output.loc[leading, ["stage"]] = "unestablished"
    output.loc[leading, "parent_context"] = "none"
    output.loc[leading, "volume_context"] = "unknown"
    output.loc[leading, "volume_context_reference"] = "none"
    output.loc[leading, "pv_state"] = "unestablished/unknown"
    output.loc[invalid, "valid"] = False
    output.loc[invalid, ["local_event", "primary_event", "parent_resolution_count"]] = 0
    output.loc[invalid, ["primary_initialized", "primary_flip", "parent_created"]] = False
    output.loc[invalid, ["log_price", "close", "sigma", "q"]] = np.nan
    for column in output.columns:
        if column.startswith("confirmed_extreme"):
            output.loc[invalid, column] = "" if "date" in column else np.nan
        if column.startswith("parent_resolution"):
            if column.endswith("direction") or column.endswith("count"):
                output.loc[invalid, column] = 0
            elif column.endswith("_idx"):
                output.loc[invalid, column] = np.nan
            else:
                output.loc[invalid, column] = ""
    for column in bool_columns:
        output[column] = output[column].astype(bool)
    for column in int_columns:
        output[column] = output[column].astype(int)
    for column in output.select_dtypes(include=[np.number]).columns:
        if column not in int_columns:
            output[column] = output[column].astype(float)
    return output


# Convenient consistent API for trajectory runners, without a second code path.
context_frame = progress_frame
