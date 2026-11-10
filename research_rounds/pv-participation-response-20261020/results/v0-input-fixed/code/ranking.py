"""Independent same-date price ranking; never feeds back into trend state.

The four 63-observation segments reproduce the price RS formula in
pv-progress-retention-20261020/code/context_model.py. At least 253 eligible
price observations are required. Inputs should already use the audited price
clock; an invalid close is not an eligible observation and is not filled.

Policy fixed before calculation: retain the unrounded rs_score, but round the
comparison key to 12 decimal places using pandas/NumPy ties-to-even semantics.
Equal keys receive ascending average ranks. This is ranking precision, not a
trading threshold. No claim is made of exact invariance under every floating
point scaling, overflow, or value at a rounding boundary.

Only close and the observation dates are read. Volume, trend state and account
eligibility are neither inputs nor outputs. Missing same-date peers are not
forward-filled. The two indices retain a diagnostic rs_score but are excluded
from peer ranking.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


RANK_DECIMALS = 12
POOL_MEMBERS = {
    "CN_stock": ("600059.SH", "600917.SH", "600919.SH"),
    "HK_stock": ("HK00002", "HK00101", "HK00700", "HK03690", "HK09618"),
    "CN_ETF": ("USHJ510300", "USHJ512480", "USHJ518880"),
    "HK_ETF": ("HK03033",),
}
EXCLUDED = frozenset(("URFI881129", "UZZI000994"))
SYMBOL_POOL = {symbol: pool for pool, symbols in POOL_MEMBERS.items() for symbol in symbols}


def rank_frames(frames: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Return each supplied symbol's independent RS and same-date peer ranking.

    Output rows retain that symbol's input dates. `peer_count` is the number of
    same-pool symbols with a calculable score on that date, including the symbol
    itself when eligible. A symbol with unknown own score has unknown rank even
    when other peers have valid scores. Indices have pool='excluded', count=0.
    """
    unknown = set(frames).difference(SYMBOL_POOL).difference(EXCLUDED)
    if unknown:
        raise ValueError(f"Unknown symbols outside fixed ranking universe: {sorted(unknown)}")
    results = {}
    for symbol, frame in frames.items():
        if "close" not in frame:
            raise ValueError(f"Missing close: {symbol}")
        index = pd.DatetimeIndex(frame.index)
        if index.hasnans or not index.is_unique or not index.is_monotonic_increasing:
            raise ValueError(f"Unique increasing observed dates required: {symbol}")
        close = pd.Series(
            pd.to_numeric(frame["close"], errors="coerce").to_numpy(dtype=float),
            index=index, name="close",
        )
        eligible = close.loc[np.isfinite(close) & close.gt(0)]
        score = (
            .4 * (eligible / eligible.shift(63) - 1)
            + .2 * (eligible.shift(63) / eligible.shift(126) - 1)
            + .2 * (eligible.shift(126) / eligible.shift(189) - 1)
            + .2 * (eligible.shift(189) / eligible.shift(252) - 1)
        )
        # Non-finite arithmetic is unavailable, never promoted to a top rank.
        score = score.where(np.isfinite(score)).reindex(index)
        result = pd.DataFrame({
            "rs_score": score,
            "rank_score": pd.Series(np.nan, index=index, dtype=float),
            "peer_count": pd.Series(0, index=index, dtype="int64"),
            "pool": pd.Series(SYMBOL_POOL.get(symbol, "excluded"), index=index, dtype="string"),
        })
        result.index.name = frame.index.name
        results[symbol] = result

    for pool, fixed_members in POOL_MEMBERS.items():
        members = [symbol for symbol in fixed_members if symbol in results]
        if not members:
            continue
        # Outer date alignment is solely for same-date comparisons; no filling.
        scores = pd.concat({symbol: results[symbol]["rs_score"] for symbol in members}, axis=1)
        count = scores.notna().sum(axis=1).astype("int64")
        ordinal = scores.round(RANK_DECIMALS).rank(axis=1, method="average", ascending=True)
        normalized = ordinal.sub(1).div(count.sub(1).where(count.ge(2)), axis=0)
        for symbol in members:
            result = results[symbol]
            result["rank_score"] = normalized[symbol].reindex(result.index)
            result["peer_count"] = count.reindex(result.index).astype("int64")
    return results
