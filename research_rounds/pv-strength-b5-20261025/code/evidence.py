"""B5 market evidence: pure E0 events and the unchanged frozen B4 strength.

No participation state is calculated here.  Price, event, and strength clocks
are explicit and different: price-valid rows drive previous close and the
21-price-observation volume window; positive finite C/V rows drive the E0
event kernel; the supplied strength mask drives the independent B4 channel.
"""
from __future__ import annotations

import hashlib
import importlib.util
import math
from pathlib import Path

import numpy as np
import pandas as pd

from arithmetic import compare, log_ratio


ROOT = Path(__file__).resolve().parents[3]
B4_SOURCE = ROOT / "research_rounds/pv-strength-b4-20261025/code/model.py"
B4_SHA256 = "0beb0b16f2f2cac4f1aff23258b7c45722dc12f16e495be27bf5635c03888cf1"
INPUT_COLUMNS = [
    "open", "high", "low", "close", "volume", "segment_id",
    "valid_price_observation", "valid_strength_observation",
]
EVENT_COLUMNS = [
    "confirmation", "leg_direction", "developing_extreme", "confirmed_pivot",
    "event", "pivot_age", "developing_extreme_price", "confirmed_pivot_price",
    "confirmed_pivot_date", "developing_extreme_date",
]
EVENT_DATE_COLUMNS = ["confirmed_pivot_date", "developing_extreme_date"]
FACT_COLUMNS = [
    "price_observation", "event_observation", "strength_observation", "ready",
    "previous_close", "volume_baseline", "volume_ratio", "declined",
    "high_effort", "decline_candidate", "candidate_lower", "candidate_reclaim",
]


def _load_frozen_b4():
    """Verify the bytes before loading under an isolated, source-specific name."""
    if hashlib.sha256(B4_SOURCE.read_bytes()).hexdigest() != B4_SHA256:
        raise RuntimeError("Frozen B4 source SHA-256 mismatch")
    spec = importlib.util.spec_from_file_location(
        "_pvs_b5_frozen_b4_0beb0b16f2f2cac4", B4_SOURCE)
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load frozen B4 source")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validate(f):
    if not isinstance(f, pd.DataFrame):
        raise ValueError("DataFrame required")
    if not isinstance(f.index, pd.DatetimeIndex) or f.index.tz is not None:
        raise ValueError("Naive DatetimeIndex required")
    if not f.index.is_unique or not f.index.is_monotonic_increasing or f.index.hasnans:
        raise ValueError("Ordered unique dated observations required")
    if not f.index.normalize().is_unique:
        raise ValueError("At most one daily observation per calendar date required")
    if not f.columns.is_unique or any(column not in f for column in INPUT_COLUMNS):
        raise ValueError("Unique OHLCV, segment_id and both validity columns required")
    if f.segment_id.isna().any():
        raise ValueError("Explicit source segment required")
    if any(isinstance(segment, str) and not segment.strip() for segment in f.segment_id):
        raise ValueError("Nonempty source segment identity required")
    blocks = f.segment_id.loc[f.segment_id.ne(f.segment_id.shift())]
    if blocks.duplicated().any():
        raise ValueError("Noncontiguous segment identity")
    if blocks.map(str).duplicated().any():
        raise ValueError("Distinct source segment identities collide after string conversion")
    for name in ("valid_price_observation", "valid_strength_observation"):
        if not pd.api.types.is_bool_dtype(f[name]) or f[name].isna().any():
            raise ValueError("Non-null Boolean validity required")
    if (f.valid_strength_observation & ~f.valid_price_observation).any():
        raise ValueError("Strength validity must be a subset of price validity")
    good = f.loc[f.valid_price_observation]
    if len(good):
        a = good[["open", "high", "low", "close"]].to_numpy(float)
        if not np.isfinite(a).all() or not (a > 0).all():
            raise ValueError("Finite positive valid OHLC prices required")
        o, h, low, c = a.T
        if ((h < np.maximum(o, c)) | (low > np.minimum(o, c)) | (h < low)).any():
            raise ValueError("Valid OHLC bars must satisfy low <= open/close <= high")
        # NaN, zero, negative and infinite numeric volume remain explicit gaps;
        # they do not create a volume event, but price processing continues.
        good.volume.to_numpy(float)


def _event_facts(bars):
    """Pure event portion extracted from numeric.event_frame_numeric.

    Every retained scalar operation, local fsum, median window, branch and
    extreme update matches the source.  The source's active/floor/target and
    entered/exited calculations have never been executed in this function.
    An empty C/V-valid segment is a B5 extension: events remain unprepared.
    """
    raw = bars[["close", "volume"]]
    d = raw.loc[raw.gt(0).all(axis=1) & np.isfinite(raw).all(axis=1)]
    numeric_columns = [column for column in EVENT_COLUMNS if column not in EVENT_DATE_COLUMNS]
    blank = pd.DataFrame(np.nan, index=bars.index, columns=numeric_columns)
    blank["event"] = 0.0
    for column in EVENT_DATE_COLUMNS:
        blank[column] = pd.Series(pd.NA, index=bars.index, dtype="string")
    if d.empty:
        return blank[EVENT_COLUMNS], pd.Series(np.nan, index=bars.index)
    prices, volumes = d.close.to_numpy(), d.volume.to_numpy()
    returns = [math.nan] + [log_ratio(prices[t], prices[t - 1])
                           for t in range(1, len(d))]
    sigma = np.full(len(d), np.nan)
    baseline = d.volume.shift().rolling(21).median().to_numpy()
    for t in range(64, len(d)):
        sigma[t] = max(math.sqrt(math.fsum(x * x for x in returns[t - 63:t]) / 63), 1e-8)
    direction, ext = -1, None
    rows = []
    for t, date in enumerate(d.index):
        row = dict(confirmation=math.nan, leg_direction=math.nan,
                   developing_extreme=math.nan, confirmed_pivot=math.nan,
                   event=0.0, pivot_age=math.nan,
                   developing_extreme_price=math.nan, confirmed_pivot_price=math.nan,
                   confirmed_pivot_date=None, developing_extreme_date=None)
        if not math.isfinite(sigma[t] + baseline[t]):
            rows.append(row)
            continue
        if ext is None:
            ext = t
        extreme_order = compare(prices[t], prices[ext])
        if (direction == -1 and extreme_order < 0) or (direction == 1 and extreme_order > 0):
            ext = t
        if t > ext:
            activity = math.sqrt(
                (math.fsum(float(x) for x in volumes[ext + 1:t + 1]) / (t - ext))
                / baseline[ext]
            )
            activity = min(max(activity, 0.5), 2.0)
            confirmation = (-direction) * log_ratio(prices[t], prices[ext]) * activity / (math.sqrt(5) * sigma[ext])
            row["confirmation"] = confirmation
            if compare(max(confirmation, 0.0), 1.0) >= 0:
                event = -direction
                pivot = float(prices[ext])
                row.update(event=float(event), confirmed_pivot=math.log(pivot),
                           confirmed_pivot_price=pivot, pivot_age=float(t - ext),
                           confirmed_pivot_date=str(d.index[ext].date()))
                direction, ext = event, t
        row.update(leg_direction=float(direction),
                   developing_extreme=math.log(float(prices[ext])),
                   developing_extreme_price=float(prices[ext]),
                   developing_extreme_date=str(d.index[ext].date()))
        rows.append(row)
    result = pd.DataFrame(rows, index=d.index).reindex(bars.index)
    result["event"] = result.event.fillna(0.0)
    for column in EVENT_DATE_COLUMNS:
        result[column] = result[column].astype("string")
    observations = pd.Series(np.arange(len(d), dtype=float), index=d.index).reindex(bars.index)
    return result[EVENT_COLUMNS], observations


def build_evidence(f):
    """Return (market_frame, {'events': list, 'strength': original_B4_list}).

    All rows are retained.  Price-invalid rows have unknown E0 facts; missing
    volume on a price-valid row still permits price facts and ready to persist.
    Extra input columns are intentionally not forwarded.  B4's 101 output
    columns receive only a `strength_` prefix; its journal stays unchanged.
    """
    _validate(f)
    out = f[INPUT_COLUMNS].copy()
    facts = pd.DataFrame(np.nan, index=f.index, columns=FACT_COLUMNS + [
        column for column in EVENT_COLUMNS if column not in EVENT_DATE_COLUMNS])
    for column in EVENT_DATE_COLUMNS:
        facts[column] = pd.Series(pd.NA, index=f.index, dtype="string")
    event_journal = []
    previous_segment = None
    for segment, group in f.groupby("segment_id", sort=False):
        if previous_segment is not None:
            event_journal.append(dict(
                segment=str(segment), date=str(group.index[0].date()),
                kind="source_discontinuity", previous_segment=previous_segment,
                observation=None,
            ))
        previous_segment = str(segment)
        bars = group.loc[group.valid_price_observation, ["open", "high", "low", "close", "volume"]].astype(float)
        if bars.empty:
            continue
        events, event_clock = _event_facts(bars)
        facts.loc[bars.index, EVENT_COLUMNS] = events
        facts.loc[bars.index, "event_observation"] = event_clock
        facts.loc[bars.index, "price_observation"] = np.arange(len(bars), dtype=float)
        strength_dates = group.index[group.valid_strength_observation]
        facts.loc[strength_dates, "strength_observation"] = np.arange(len(strength_dates), dtype=float)
        v = bars.volume.where(np.isfinite(bars.volume) & bars.volume.gt(0))
        volume_base = v.shift().rolling(21, min_periods=21).median()
        ratios = v / volume_base
        ready, previous_close = False, math.nan
        for n, (date, bar) in enumerate(bars.iterrows()):
            ev = events.loc[date]
            ready = ready or bool(pd.notna(ev.leg_direction))
            c, low = float(bar.close), float(bar.low)
            q = float(ratios.loc[date])
            declined = bool(math.isfinite(previous_close) and compare(c, previous_close) < 0)
            high_effort = bool(math.isfinite(q) and compare(q, 2.0) >= 0)
            candidate = bool(ready and declined and high_effort)
            facts.loc[date, ["ready", "previous_close", "volume_baseline", "volume_ratio",
                             "declined", "high_effort", "decline_candidate",
                             "candidate_lower", "candidate_reclaim"]] = [
                int(ready), previous_close, float(volume_base.loc[date]), q,
                int(declined), int(high_effort), int(candidate),
                low if candidate else math.nan, previous_close if candidate else math.nan,
            ]
            if ev.event:
                event_journal.append(dict(
                    segment=str(segment), date=str(date.date()), observation=int(n),
                    event_observation=int(event_clock.loc[date]), kind="event_confirmed",
                    direction=int(ev.event), confirmation=float(ev.confirmation),
                    pivot_price=float(ev.confirmed_pivot_price), pivot_date=ev.confirmed_pivot_date,
                    pivot_age=int(ev.pivot_age),
                ))
            if candidate:
                event_journal.append(dict(
                    segment=str(segment), date=str(date.date()), observation=int(n),
                    kind="high_participation_decline", lower=low, reclaim=previous_close,
                    volume_ratio=q, volume_baseline=float(volume_base.loc[date]),
                ))
            previous_close = c
    b4 = _load_frozen_b4()
    strength, strength_journal = b4.strength_frame(f, joint=True)
    out = pd.concat([out, facts[FACT_COLUMNS + EVENT_COLUMNS], strength.add_prefix("strength_")], axis=1)
    out.attrs.update(
        model="PVS-B5", strength_source=str(B4_SOURCE.relative_to(ROOT)),
        strength_sha256=B4_SHA256, strength_attrs=strength.attrs.copy(),
        clocks="price: explicit mask; event: price plus positive finite C/V; strength: explicit subset mask",
        journal_contract="events: pure event/candidate receipts; strength: unchanged frozen B4 journal",
    )
    return out, {"events": event_journal, "strength": strength_journal}
