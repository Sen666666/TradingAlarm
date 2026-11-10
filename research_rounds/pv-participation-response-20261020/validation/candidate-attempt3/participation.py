"""High-participation declines and their later reclamation. No accounts."""
from __future__ import annotations

import math
import numpy as np
import pandas as pd
from numeric import compare, higher


def participation_frame(bars, events, mode="volume"):
    if mode not in ("volume", "all", "none"):
        raise ValueError(mode)
    if not bars.index.is_unique or not bars.index.is_monotonic_increasing:
        raise ValueError("ordered unique price observations required")
    if "confirmed_pivot_price" not in events:
        raise ValueError("canonical raw-price pivots required")
    e = events.reindex(bars.index)
    v = bars.volume.where(np.isfinite(bars.volume) & bars.volume.gt(0))
    volume_base = v.shift().rolling(21, min_periods=21).median()
    ratios = v / volume_base
    active, floor, pending, previous_close = False, math.nan, None, math.nan
    ready = False
    next_id = 0
    rows, ledger = [], []
    for n, (date, bar) in enumerate(bars.iterrows()):
        ev = e.loc[date]
        price_event = int(ev.event) if pd.notna(ev.event) else 0
        ready = ready or bool(pd.notna(ev.leg_direction))
        c, low = float(bar.close), float(bar.low)
        q = float(ratios.loc[date])
        declined = bool(math.isfinite(previous_close) and compare(c, previous_close) < 0)
        high_effort = bool(math.isfinite(q) and compare(q, 2.0) >= 0)
        entered = exited = created = response = consumed = independent = 0
        ended_id = None
        entry_kind = ""
        if active and compare(c, floor) <= 0:
            active, exited = False, 1
        if pending:
            if compare(c, pending["lower"]) < 0:
                response = -1
            elif compare(c, pending["reclaim"]) > 0:
                response = 1
        # Original confirmation has priority and never waits for new memory.
        if price_event == 1:
            pivot = float(ev.confirmed_pivot_price)
            if not math.isfinite(pivot):
                raise ValueError("up event lacks canonical pivot")
            if active:
                floor = higher(floor, pivot)
            elif not exited:
                active, entered, floor = True, 1, pivot
                entry_kind = "original_event"
        if pending:
            outcome = None
            if response == -1:
                outcome = "rejected"
            elif active:
                outcome, consumed = "base_confirmed", 1
            elif response == 1:
                if exited:
                    raise AssertionError("existing memory cannot coexist with active structure")
                active, entered, independent, floor = True, 1, 1, pending["lower"]
                entry_kind, outcome = "participation_reclaim", "reclaimed"
            if outcome:
                record = dict(pending)
                record.update(resolved_date=str(date.date()), outcome=outcome,
                              response=response, independent_entry=independent,
                              original_entry_same_day=int(entry_kind == "original_event"),
                              resolution_volume_ratio=q if math.isfinite(q) else None,
                              waiting_observations=n-pending["created_observation"])
                ledger.append(record)
                ended_id, pending = pending["id"], None
        if (not active and pending is None and ready and declined
                and (mode == "all" or (mode == "volume" and high_effort))):
            next_id += 1
            pending = {
                "id": next_id, "created_date": str(date.date()),
                "created_observation": n, "reclaim": previous_close, "lower": low,
                "event_open": float(bar.open), "event_high": float(bar.high),
                "event_close": c, "event_volume": float(bar.volume),
                "volume_ratio": q if math.isfinite(q) else None,
                "volume_baseline": float(volume_base.loc[date]) if pd.notna(volume_base.loc[date]) else None,
                "created_on_exit": exited,
            }
            created = 1
        if active and pending is not None:
            raise AssertionError("active structure retained pending memory")
        rows.append({
            "date": date, "target": int(active), "entered": entered, "exited": exited,
            "floor": floor if active or exited else math.nan,
            "pending": int(pending is not None), "pending_id": pending["id"] if pending else None,
            "pending_since": pending["created_date"] if pending else None,
            "pending_reclaim": pending["reclaim"] if pending else math.nan,
            "pending_lower": pending["lower"] if pending else math.nan,
            "created": created, "response": response, "consumed_by_base": consumed,
            "independent_entry": independent, "ended_id": ended_id,
            "entry_kind": entry_kind, "volume_ratio": q, "high_effort": int(high_effort),
            "declined": int(declined), "price_event": price_event, "ready": int(ready),
        })
        previous_close = c
    if pending:
        record = dict(pending)
        record.update(resolved_date=None, outcome="open", response=0,
                      independent_entry=0, original_entry_same_day=0,
                      resolution_volume_ratio=None,
                      waiting_observations=len(bars)-1-pending["created_observation"])
        ledger.append(record)
    result = pd.DataFrame(rows).set_index("date") if rows else pd.DataFrame()
    if not result.empty:
        for col in ("pending_id", "ended_id"):
            result[col] = result[col].astype("Int64")
        for col in ("pending_since", "entry_kind"):
            result[col] = result[col].astype("string")
    ledger_types = {
        "id": "int64", "created_date": "string", "created_observation": "int64",
        "reclaim": "float64", "lower": "float64", "event_open": "float64",
        "event_high": "float64", "event_close": "float64", "event_volume": "float64",
        "volume_ratio": "float64", "volume_baseline": "float64",
        "created_on_exit": "int64", "resolved_date": "string", "outcome": "string",
        "response": "int64", "independent_entry": "int64",
        "original_entry_same_day": "int64", "resolution_volume_ratio": "float64",
        "waiting_observations": "int64",
    }
    records = pd.DataFrame(ledger, columns=ledger_types).astype(ledger_types)
    return result, records
