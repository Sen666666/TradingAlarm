"""Volume-selected failed attempts create causal, two-sided reconstruction events.

No account imports or trading calculations. `events` is the unchanged upstream
event detector on the source clock; `bars` is the audited OHLC price clock.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def attach_exact_pivots(source: pd.DataFrame, events: pd.DataFrame):
    """Recover internal pivot coordinates without log-offset round-trip error.

    Uses already emitted events and the same causal extreme update as the frozen
    detector. Does not change detection or append future-defined pivot dates.
    """
    d = source.loc[np.isfinite(source.close) & source.close.gt(0)
                   & np.isfinite(source.volume) & source.volume.gt(0)]
    result = events.copy()
    result["confirmed_pivot_relative"] = np.nan
    if d.empty:
        return result
    result.attrs["source_first_close"] = float(d.close.iloc[0])
    y = np.log(d.close.to_numpy() / d.close.iloc[0])
    direction, ext = -1, None
    for t, date in enumerate(d.index):
        ev = events.loc[date]
        if not np.isfinite(ev.leg_direction):
            continue
        if ext is None:
            ext = t
        if (direction == -1 and y[t] < y[ext]) or (direction == 1 and y[t] > y[ext]):
            ext = t
        if ev.event:
            result.loc[date, "confirmed_pivot_relative"] = y[ext]
            direction, ext = int(ev.event), t
    return result


def response_frame(bars: pd.DataFrame, events: pd.DataFrame, mode="volume"):
    if mode not in {"volume", "all", "none"}:
        raise ValueError(mode)
    if not bars.index.is_unique or not bars.index.is_monotonic_increasing:
        raise ValueError("ordered unique OHLC observations required")
    if "confirmed_pivot_relative" not in events:
        raise ValueError("use attach_exact_pivots: absolute log pivots lose equality precision")
    if "source_first_close" not in bars.attrs:
        raise ValueError("bars must retain the source detector's price origin")
    if "source_first_close" in events.attrs and events.attrs["source_first_close"] != bars.attrs["source_first_close"]:
        raise ValueError("upstream events and OHLC bars use different price origins")
    e = events.reindex(bars.index)
    v = bars.volume.where(np.isfinite(bars.volume) & bars.volume.gt(0))
    ratio = v / v.shift().rolling(21, min_periods=21).median()
    active, floor = False, np.nan
    peak, trough = np.nan, np.nan
    peak_date = trough_date = None
    pending = None
    next_id = 0
    rows, ledger = [], []
    for date, b in bars.iterrows():
        ev = e.loc[date]
        price_event = int(ev.event) if pd.notna(ev.event) else 0
        # Match original detector's normalized-log comparison coordinates.
        origin = bars.attrs["source_first_close"]
        c, h, l = np.log(np.array([b.close, b.high, b.low]) / origin)
        offset = np.log(origin)
        pivot = float(ev.confirmed_pivot_relative)
        q = float(ratio.loc[date])
        entered = exited = created = blocked = 0
        resolved = 0
        entry_kind = ""
        resolution_id = None
        attempted_up = np.isfinite(peak) and h > peak and c <= peak
        attempted_down = np.isfinite(trough) and l < trough and c >= trough
        eligible = bool(b.high > b.low and (attempted_up or attempted_down))
        high_effort = bool(np.isfinite(q) and q >= 2)
        if active and c <= floor:
            active, exited = False, 1
        if pending is not None:
            if c > pending["high_log"]:
                resolved = 1
            elif c < pending["low_log"]:
                resolved = -1
            if resolved:
                resolution_id = pending["id"]
                record = dict(pending)
                record.update(resolved_date=str(date.date()), outcome=resolved)
                ledger.append(record)
                if resolved == 1 and not exited:
                    active, entered = True, 1
                    floor = pending["low_log"]
                    entry_kind = "volume_resolution" if mode == "volume" else "price_resolution"
                pending = None
        if not active and not exited and not resolved and pending is None:
            if eligible and (mode == "all" or (mode == "volume" and high_effort)):
                next_id += 1
                pending = {
                    "id": next_id, "created_date": str(date.date()),
                    "high_log": float(h), "low_log": float(l),
                    "high": float(b.high), "low": float(b.low),
                    "volume_ratio": q if np.isfinite(q) else None,
                    "attempt": "both" if attempted_up and attempted_down else (
                        "up_not_retained" if attempted_up else "down_not_retained"),
                    "reference_peak": float(np.exp(peak + offset)) if np.isfinite(peak) else None,
                    "reference_trough": float(np.exp(trough + offset)) if np.isfinite(trough) else None,
                    "peak_confirmation_date": peak_date,
                    "trough_confirmation_date": trough_date,
                }
                created = 1
        if price_event == 1:
            if active:
                # A resolution entry uses its event floor first, then the same
                # already-confirmed-low ratchet if both evidence types coincide.
                floor = max(floor, pivot)
            elif pending is not None:
                blocked = 1
            elif not exited and resolved != -1:
                active, entered, floor = True, 1, pivot
                entry_kind = "original_event"
        rows.append({
            "date": date, "target": int(active), "entered": entered,
            "exited": exited, "floor": np.exp(floor + offset) if active or exited else np.nan,
            "pending": int(pending is not None), "created": created,
            "resolved": resolved, "resolution_id": resolution_id,
            "blocked_price_event": blocked, "entry_kind": entry_kind,
            "pending_id": pending["id"] if pending else None,
            "pending_high": pending["high"] if pending else np.nan,
            "pending_low": pending["low"] if pending else np.nan,
            "pending_since": pending["created_date"] if pending else None,
            "reference_peak": np.exp(peak + offset) if np.isfinite(peak) else np.nan,
            "reference_trough": np.exp(trough + offset) if np.isfinite(trough) else np.nan,
            "volume_ratio": q, "high_effort": int(high_effort),
            "price_attempt": int(eligible),
            "price_event": price_event,
        })
        # No same-day pivot retroactively supplies the attempted reference.
        if price_event == -1:
            peak, peak_date = pivot, str(date.date())
        elif price_event == 1:
            trough, trough_date = pivot, str(date.date())
    if pending:
        record = dict(pending)
        record.update(resolved_date=None, outcome=0)
        ledger.append(record)
    result = pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()
    if not result.empty:
        for col in ["resolution_id", "pending_id"]:
            result[col] = result[col].astype("Int64")
        for col in ["pending_since", "entry_kind"]:
            result[col] = result[col].astype("string")
    ledger_frame = pd.DataFrame(ledger)
    if not ledger_frame.empty:
        for col in ["created_date", "resolved_date", "peak_confirmation_date", "trough_confirmation_date"]:
            ledger_frame[col] = ledger_frame[col].astype("string")
    return result, ledger_frame
