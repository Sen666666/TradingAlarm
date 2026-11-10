"""S-AMT1 research candidate. Pure signals; no data loading or account runner.

The interface accepts prevalidated, complete source segments only. Invalid
amount/price rows fail the whole call rather than silently bridging a gap.
"""
from __future__ import annotations

from dataclasses import replace
import math

import numpy as np
import pandas as pd

from s_amount_arithmetic import compare, log_ratio

VERSION = "S-AMT1"
MULTIPLIER = 1.5
FLOAT_COLUMNS = (
    "pivot", "anchor_price", "scale", "amount_baseline", "threshold",
    "displacement", "delta_frontier", "frontier", "credit", "weight",
    "confirmation", "next_frontier", "next_credit", "strict_floor",
)
BOOL_COLUMNS = ("ready", "strict_target", "strict_exited")
INT_COLUMNS = ("event", "candidate_direction", "next_leg_direction")
DATE_COLUMNS = ("pivot_date", "anchor_date", "next_anchor_date")


def _validate(bars: pd.DataFrame) -> None:
    if not isinstance(bars, pd.DataFrame):
        raise ValueError("DataFrame required")
    if not isinstance(bars.index, pd.DatetimeIndex) or bars.index.tz is not None:
        raise ValueError("Naive DatetimeIndex required")
    if bars.index.hasnans or not bars.index.is_unique or not bars.index.is_monotonic_increasing:
        raise ValueError("Ordered unique dates required")
    if not bars.index.normalize().is_unique:
        raise ValueError("At most one observation per date")
    if not bars.columns.is_unique or not {"close", "amount", "segment_id"} <= set(bars):
        raise ValueError("Unique close/amount/segment_id columns required")
    for column in ("close", "amount"):
        if not pd.api.types.is_numeric_dtype(bars[column]) or pd.api.types.is_bool_dtype(bars[column]):
            raise ValueError(f"Numeric {column} required")
        values = bars[column].to_numpy(dtype=float)
        if not (np.isfinite(values).all() and (values > 0).all()):
            raise ValueError(f"Complete finite positive {column} required; do not drop or fill gaps")
    if bars.segment_id.isna().any() or bars.segment_id.map(lambda x: not str(x).strip()).any():
        raise ValueError("Explicit nonempty source segments required")
    blocks = bars.segment_id.loc[bars.segment_id.ne(bars.segment_id.shift())]
    if blocks.duplicated().any() or blocks.map(str).duplicated().any():
        raise ValueError("Source segments must be contiguous and distinct")


def _state_step(active, floor, close, event, pivot):
    """Preserve old S policy: break yesterday's floor before accepting a pivot."""
    exited = bool(active and compare(close, floor) <= 0)
    if exited:
        active = False
    if event == 1:
        if active:
            floor = max(floor, pivot)
        elif not exited:
            active, floor = True, pivot
    return active, floor, exited


def calculate(bars: pd.DataFrame, original_buy: pd.Series | None = None) -> pd.DataFrame:
    """Build a STRICT-compatible S table without changing any original facts.

    ``original_buy`` is optional and must be an exactly aligned Boolean Series.
    It adds original_buy/strict_buy audit columns, never a new I signal.
    """
    _validate(bars)
    if original_buy is not None:
        if not isinstance(original_buy, pd.Series) or not original_buy.index.equals(bars.index):
            raise ValueError("original_buy must align exactly; no forward fill")
        if not pd.api.types.is_bool_dtype(original_buy) or original_buy.isna().any():
            raise ValueError("Non-null Boolean original_buy required")
    rows = []
    for _, segment in bars.groupby("segment_id", sort=False):
        prices = segment.close.to_numpy(float)
        amounts = segment.amount.to_numpy(float)
        dates = [str(t.date()) for t in segment.index]
        returns = [math.nan] + [log_ratio(prices[i], prices[i - 1]) for i in range(1, len(prices))]
        scale = np.full(len(prices), np.nan)
        baseline = segment.amount.shift().rolling(21).median().to_numpy(float)
        for i in range(64, len(prices)):
            scale[i] = max(math.sqrt(math.fsum(r * r for r in returns[i - 63:i]) / 63), 1e-8)
        direction, extreme = -1, None
        frontier = credit = 0.0
        active, floor = False, math.nan
        for i, close in enumerate(prices):
            row = {name: math.nan for name in FLOAT_COLUMNS}
            row.update({name: False for name in BOOL_COLUMNS})
            row.update({name: 0 for name in INT_COLUMNS})
            row.update({name: None for name in DATE_COLUMNS})
            row["segment_id"] = segment.segment_id.iloc[i]
            event, pivot = 0, math.nan
            if math.isfinite(scale[i] + baseline[i]):
                row["ready"] = True
                is_new_extreme = extreme is None or (
                    direction == -1 and compare(close, prices[extreme]) < 0
                ) or (direction == 1 and compare(close, prices[extreme]) > 0)
                if is_new_extreme:
                    extreme, frontier, credit = i, 0.0, 0.0
                threshold = MULTIPLIER * math.sqrt(5) * scale[extreme]
                displacement = -direction * log_ratio(close, prices[extreme])
                fresh = compare(max(0.0, displacement), frontier) > 0
                delta = displacement - frontier if fresh else 0.0
                # Saturating before division avoids overflow for extreme valid amounts.
                weight = 1.0 if amounts[i] >= baseline[extreme] else math.sqrt(amounts[i] / baseline[extreme])
                if fresh:
                    frontier = displacement
                    credit = math.fsum((credit, delta * weight))
                row.update(
                    candidate_direction=-direction, anchor_date=dates[extreme],
                    anchor_price=prices[extreme], scale=scale[extreme],
                    amount_baseline=baseline[extreme], threshold=threshold,
                    displacement=displacement, delta_frontier=delta,
                    frontier=frontier, credit=credit, weight=weight,
                    confirmation=credit / threshold,
                )
                if fresh and compare(max(0.0, displacement) / threshold, 1.0) >= 0 and compare(credit / threshold, 1.0) >= 0:
                    event, pivot = -direction, float(prices[extreme])
                    row.update(event=event, pivot=pivot, pivot_date=dates[extreme])
                    direction, extreme, frontier, credit = event, i, 0.0, 0.0
                row.update(next_leg_direction=direction, next_anchor_date=dates[extreme],
                           next_frontier=frontier, next_credit=credit)
            active, floor, exited = _state_step(active, floor, close, event, pivot)
            row.update(strict_target=active, strict_exited=exited,
                       strict_floor=floor if active or exited else math.nan)
            rows.append(row)
    columns = ["segment_id", *BOOL_COLUMNS, *INT_COLUMNS, *DATE_COLUMNS, *FLOAT_COLUMNS]
    result = pd.DataFrame(rows, index=bars.index, columns=columns)
    for names, dtype in ((FLOAT_COLUMNS, "float64"), (INT_COLUMNS, "int64"),
                         (BOOL_COLUMNS, "bool"), (DATE_COLUMNS, "string")):
        for name in names:
            result[name] = result[name].astype(dtype)
    if original_buy is not None:
        result["original_buy"] = original_buy.to_numpy(bool)
        result["strict_buy"] = result.original_buy & result.strict_target
    return result


def filter_stocks(stocks, strict_tables, clock, Fact):
    """Same admission adapter as old S: only suppress buy_allowed.

    No ranking, trend_up, held stop, W intent, F support, or account risk is
    calculated here. The caller explicitly selects the S-AMT1 tables.
    """
    day = pd.Timestamp(clock.decision_at.date())
    result = []
    for stock in stocks:
        table = strict_tables.get(stock.security_id)
        if table is not None:
            if not isinstance(table, pd.DataFrame) or not table.columns.is_unique or "strict_target" not in table:
                raise ValueError("STRICT table requires unique columns and strict_target")
            if not isinstance(table.index, pd.DatetimeIndex) or table.index.tz is not None or table.index.hasnans or not table.index.is_unique or not table.index.is_monotonic_increasing or not table.index.normalize().is_unique:
                raise ValueError("STRICT table requires unique ordered daily dates")
            if not pd.api.types.is_bool_dtype(table.strict_target) or table.strict_target.isna().any():
                raise ValueError("STRICT target must be non-null Boolean, never truth-cast missing data")
        allowed = table is not None and day in table.index and bool(table.loc[day, "strict_target"])
        result.append(stock if allowed else replace(
            stock, buy_allowed=Fact(False, clock.decision_at, clock.decision_at,
                                    source_id="s_amt1_entry_only")))
    return tuple(result)
