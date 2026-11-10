"""Version 1: refresh descriptive evidence with the developing price-volume leg.

Only the age of the descriptive evidence changes. The imported version-0 price
skeleton, structural regimes/boundaries, events, RS, and Bollinger descriptors are
preserved exactly. This wrapper is not a trading rule or a probability model.
It has no I/O and never imports an account or order implementation.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from context_model import context_frame as _completed_frame


def _date(value):
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def context_frame(close: pd.Series, volume: pd.Series) -> pd.DataFrame:
    """Compare the last completed leg with the current developing leg.

    The developing leg starts at the latest already-confirmed pivot's actual
    date and ends at the current valid observation. Its interval is (start,end].
    It is only available after leg2 exists and has positive speed, and when
    end > start. No unavailable live pair falls back to the completed-pair label.

    ``live_displacement`` is absolute log displacement. ``live_direction`` stores
    its sign. Pivot dates are only used after their confirmation; old output rows
    are never rewritten. Invalid rows carry descriptors without emitting events.
    """
    output = _completed_frame(close, volume).copy()
    replaced = ("e", "s", "retrace", "phase", "price_phase")
    for column in replaced:
        output[f"completed_{column}"] = output[column]

    numeric_live = (
        "live_start_idx", "live_end_idx", "live_n", "live_direction",
        "live_displacement", "live_effort", "live_speed",
    )
    live_columns = (*replaced, "phase_source", *numeric_live,
                    "live_start_date", "live_end_date")
    valid = output["valid"].to_numpy(dtype=bool)
    valid_output = output.loc[output["valid"]]
    log_price = valid_output["log_price"].to_numpy(dtype=float)
    activity = valid_output["volume_ratio"].to_numpy(dtype=float)
    labels = valid_output.index
    descriptions = []
    previous = None
    t = -1

    for i, (_, base) in enumerate(output.iterrows()):
        if not valid[i]:
            if previous is None:
                description = {
                    "e": np.nan, "s": np.nan, "retrace": np.nan,
                    "phase": "unresolved", "price_phase": "unresolved",
                    "phase_source": "unavailable",
                    **{column: np.nan for column in numeric_live},
                    "live_start_date": "", "live_end_date": "",
                }
            else:
                description = previous.copy()
            descriptions.append(description)
            continue

        t += 1
        regime = int(base["regime"])
        description = {
            "e": np.nan, "s": np.nan, "retrace": np.nan,
            "phase": "unresolved" if regime == 0 else "unknown",
            "price_phase": "unresolved" if regime == 0 else "unknown",
            "phase_source": "unavailable",
            **{column: np.nan for column in numeric_live},
            "live_start_date": "", "live_end_date": "",
        }
        pivot_indices = [
            base[column] for column in ("last_high_idx", "last_low_idx")
            if np.isfinite(base[column])
        ]
        start = int(max(pivot_indices)) if pivot_indices else None
        last_speed, last_effort = base["leg2_speed"], base["leg2_effort"]
        last_displacement = base["leg2_displacement"]
        available = (
            start is not None and t > start
            and np.isfinite(last_speed) and last_speed > 0
            and np.isfinite(last_effort) and last_effort > 0
            and np.isfinite(last_displacement) and last_displacement > 0
        )
        if available:
            n = t - start
            signed_displacement = log_price[t] - log_price[start]
            displacement = abs(signed_displacement)
            direction = int(np.sign(signed_displacement))
            effort = float(np.mean(activity[start + 1:t + 1]))
            speed = displacement / n
            e, s = effort / last_effort, speed / last_speed
            retrace = displacement / last_displacement
            phase = "contested"
            price_phase = "slower" if s < 1 else ("faster" if s > 1 else "same_speed")
            if regime == 0:
                phase = price_phase = "unresolved"
            elif direction == 0:
                phase = "contested"
            elif direction == regime:
                phase = "supported" if e > 1 and s > 1 else (
                    "quiet" if e < 1 and s < 1 else "contested"
                )
            else:
                phase = "orderly" if e < 1 and s < 1 else (
                    "opposing_pressure" if e > 1 and s > 1 else "contested"
                )
            description = {
                "e": e, "s": s, "retrace": retrace,
                "phase": phase, "price_phase": price_phase,
                "phase_source": "developing_pair",
                "live_start_idx": start, "live_end_idx": t,
                "live_start_date": _date(labels[start]),
                "live_end_date": _date(labels[t]),
                "live_n": n, "live_direction": direction,
                "live_displacement": displacement, "live_effort": effort,
                "live_speed": speed,
            }
        descriptions.append(description)
        previous = description.copy()

    descriptive = pd.DataFrame(descriptions, index=output.index)
    for column in live_columns:
        output[column] = descriptive[column]
    for column in (*numeric_live, "e", "s", "retrace"):
        output[column] = output[column].astype(float)
    return output
