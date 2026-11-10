"""Frozen E0 participation policy consuming only explicit B5 market facts.

This module neither imports old E0 code nor reads source files.  It owns its
active/floor/pending state; all strength columns are intentionally irrelevant
when enhancements=False.  No account, order execution, or PnL is implemented.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from arithmetic import compare, higher


STATE_TYPES = {
    "target": "int64", "entered": "int64", "exited": "int64", "floor": "float64",
    "pending": "int64", "pending_id": "Int64", "pending_since": "string",
    "pending_reclaim": "float64", "pending_lower": "float64", "created": "int64",
    "response": "int64", "consumed_by_base": "int64", "independent_entry": "int64",
    "ended_id": "Int64", "entry_kind": "string", "volume_ratio": "float64",
    "high_effort": "int64", "declined": "int64", "price_event": "int64", "ready": "int64",
}
LEDGER_TYPES = {
    "id": "int64", "created_date": "string", "created_observation": "int64",
    "reclaim": "float64", "lower": "float64", "event_open": "float64",
    "event_high": "float64", "event_close": "float64", "event_volume": "float64",
    "volume_ratio": "float64", "volume_baseline": "float64",
    "created_on_exit": "int64", "resolved_date": "string", "outcome": "string",
    "response": "int64", "independent_entry": "int64",
    "original_entry_same_day": "int64", "resolution_volume_ratio": "float64",
    "waiting_observations": "int64",
}
REQUIRED_FACTS = [
    "segment_id", "valid_price_observation", "price_observation", "open", "high",
    "low", "close", "volume", "event", "confirmed_pivot_price", "ready",
    "previous_close", "volume_baseline", "volume_ratio", "declined", "high_effort",
    "decline_candidate", "candidate_lower", "candidate_reclaim",
]


def e0_policy(frame, enhancements=False):
    """Return (state, ledger), reproducing the frozen mode='volume' policy.

    Every segment starts inactive with no memory and candidate IDs starting at
    one.  A still-open memory is recorded as open at that segment's end, not
    rejected at the next segment.  Invalid price rows expose unknown state and
    never advance the clock.  State integer columns always use nullable Int64,
    including complete valid prefixes, so future invalid rows cannot change
    the schema.  Ledger dtypes are unchanged.  segment_id is appended after
    all original columns in both outputs.
    """
    if not isinstance(enhancements, (bool, np.bool_)):
        raise ValueError("Scalar Boolean enhancements required")
    if enhancements:
        raise NotImplementedError("B5 strength-enhanced participation is not specified or implemented")
    if not frame.columns.is_unique or any(column not in frame for column in REQUIRED_FACTS):
        raise ValueError("Complete B5 market facts required")
    if not isinstance(frame.index, pd.DatetimeIndex) or frame.index.tz is not None:
        raise ValueError("Naive DatetimeIndex required")
    if not frame.index.is_unique or not frame.index.is_monotonic_increasing or frame.index.hasnans:
        raise ValueError("Ordered unique dated observations required")
    if not frame.index.normalize().is_unique:
        raise ValueError("At most one daily observation per calendar date required")
    if (not pd.api.types.is_bool_dtype(frame.valid_price_observation)
            or frame.valid_price_observation.isna().any()):
        raise ValueError("Non-null Boolean price validity required")
    if frame.segment_id.isna().any():
        raise ValueError("Explicit source segment required")
    if any(isinstance(segment, str) and not segment.strip() for segment in frame.segment_id):
        raise ValueError("Nonempty source segment identity required")
    blocks = frame.segment_id.loc[frame.segment_id.ne(frame.segment_id.shift())]
    if blocks.duplicated().any():
        raise ValueError("Noncontiguous segment identity")
    if blocks.map(str).duplicated().any():
        raise ValueError("Distinct source segment identities collide after string conversion")
    rows, ledger = [], []
    for segment, group in frame.groupby("segment_id", sort=False):
        bars = group.loc[group.valid_price_observation]
        boolean_facts = ["ready", "declined", "high_effort", "decline_candidate"]
        if not bars[boolean_facts].isin([0, 1]).all().all():
            raise ValueError("Valid price rows require complete binary ready/decline/effort facts")
        if not bars.event.isin([-1, 0, 1]).all():
            raise ValueError("Valid price rows require complete event values in {-1, 0, 1}")
        active, floor, pending = False, math.nan, None
        next_id = 0
        for n, (date, fact) in enumerate(bars.iterrows()):
            if fact.price_observation != n:
                raise ValueError("Price observation clock must restart at zero and advance on valid rows")
            price_event = int(fact.event) if pd.notna(fact.event) else 0
            ready = bool(fact.ready)
            c = float(fact.close)
            q = float(fact.volume_ratio)
            declined, high_effort = bool(fact.declined), bool(fact.high_effort)
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
            if price_event == 1:
                pivot = float(fact.confirmed_pivot_price)
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
                                  waiting_observations=n-pending["created_observation"],
                                  segment_id=str(segment))
                    ledger.append(record)
                    ended_id, pending = pending["id"], None
            if not active and pending is None and bool(fact.decline_candidate):
                next_id += 1
                pending = {
                    "id": next_id, "created_date": str(date.date()),
                    "created_observation": n, "reclaim": float(fact.candidate_reclaim),
                    "lower": float(fact.candidate_lower),
                    "event_open": float(fact.open), "event_high": float(fact.high),
                    "event_close": c, "event_volume": float(fact.volume),
                    "volume_ratio": q if math.isfinite(q) else None,
                    "volume_baseline": float(fact.volume_baseline) if pd.notna(fact.volume_baseline) else None,
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
                "segment_id": str(segment),
            })
        if pending:
            record = dict(pending)
            record.update(resolved_date=None, outcome="open", response=0,
                          independent_entry=0, original_entry_same_day=0,
                          resolution_volume_ratio=None,
                          waiting_observations=len(bars)-1-pending["created_observation"],
                          segment_id=str(segment))
            ledger.append(record)
    columns = list(STATE_TYPES) + ["segment_id"]
    if rows:
        state = pd.DataFrame(rows).set_index("date").reindex(frame.index)[columns]
    else:
        state = pd.DataFrame(index=frame.index, columns=columns)
    # The original participation DataFrame builds its index from row dates,
    # which drops an input DatetimeIndex.freq.  Preserve that exact contract.
    state.index = pd.DatetimeIndex(state.index.to_numpy(), name="date")
    state_types = {column: ("Int64" if dtype == "int64" else dtype)
                   for column, dtype in STATE_TYPES.items()}
    state = state.astype(state_types)
    state["segment_id"] = frame.segment_id.astype("string")
    ledger_types = dict(LEDGER_TYPES, segment_id="string")
    records = pd.DataFrame(ledger, columns=ledger_types).astype(ledger_types)
    return state, records
