"""Localize attempt1 failures without changing the frozen numeric policy."""
from __future__ import annotations
import json
import math
from pathlib import Path

import pandas as pd

from numeric import GAMMA4, compare, event_frame_numeric, failed_attempts
from validate_numeric import OLD, REPO, ROUND, module


def references(bars, events):
    peak = trough = math.nan
    records = {}
    for date, row in bars.iterrows():
        records[date] = (peak, trough)
        event = events.loc[date]
        if event.event == -1:
            peak = float(event.confirmed_pivot_price)
        if event.event == 1:
            trough = float(event.confirmed_pivot_price)
    return records


def compare_detail(a, b):
    if not math.isfinite(b):
        return None
    return {"a": a, "b": b, "comparison": compare(a, b),
            "signed_gap_over_budget": (a - b) / (GAMMA4 * max(a, b))}


def main():
    path = ROUND / "validation/numeric-attempt1/diagnostics.json"
    if path.exists():
        raise FileExistsError(path)
    data = module("numeric_diagnostic_inputs", OLD / "code/data_utils.py")
    frames, _, _ = data.load_inputs(OLD)
    facts, floor_changes = [], []
    for symbol in ["USHJ518880", "USHJ512480", "USHJ510300", "HK00101"]:
        source = pd.read_csv(OLD / "inputs" / f"{symbol}.csv", index_col="date", parse_dates=True)
        events = event_frame_numeric(source.close, source.volume)
        scaled_events = event_frame_numeric(source.close * 7, source.volume * 11)
        bars = frames[symbol]
        scaled_bars = bars.copy()
        scaled_bars.loc[:, ["open", "high", "low", "close"]] *= 7
        before, after = failed_attempts(bars, events), failed_attempts(scaled_bars, scaled_events)
        refs, scaled_refs = references(bars, events), references(scaled_bars, scaled_events)
        for date in before.index[before.ne(after)]:
            pairs = []
            for side, b, ref in [("base", bars.loc[date], refs[date]),
                                 ("scaled", scaled_bars.loc[date], scaled_refs[date])]:
                pairs.append({
                    "side": side, "high_peak": compare_detail(float(b.high), ref[0]),
                    "close_peak": compare_detail(float(b.close), ref[0]),
                    "low_trough": compare_detail(float(b.low), ref[1]),
                    "close_trough": compare_detail(float(b.close), ref[1]),
                })
            facts.append({"symbol": symbol, "date": str(date.date()),
                          "base": int(before.loc[date]), "scaled": int(after.loc[date]),
                          "comparison_details": pairs})
    for symbol, dates in [("HK00700", ["2021-08-03", "2024-07-18"]),
                           ("HK03033", ["2023-09-20"])]:
        source = pd.read_csv(OLD / "inputs" / f"{symbol}.csv", index_col="date", parse_dates=True)
        events = event_frame_numeric(source.close, source.volume)
        for date in dates:
            row = events.loc[date]
            floor_changes.append({"symbol": symbol, "date": date,
                                  "price_floor_comparison": compare_detail(
                                      float(source.loc[date, "close"]), float(row.structure_floor_price))})
    symbol = "HK09618"
    source = pd.read_csv(OLD / "inputs" / f"{symbol}.csv", index_col="date", parse_dates=True)
    legacy = pd.read_csv(REPO / "TradingAlarm/research/results/pv-event-structure-20261020/HK09618-signals.csv",
                         index_col="date", parse_dates=True)
    replay = {}
    for side, frame in [("ohlcv", source), ("legacy", legacy)]:
        a, b = float(frame.loc["2026-10-15", "close"]), float(frame.loc["2026-10-13", "close"])
        replay[side] = compare_detail(a, b)
    record = {"policy_unchanged": True, "gamma4": GAMMA4,
              "failed_unit_attempt_dates": facts, "three_changed_exit_dates": floor_changes,
              "legacy_input_jd_extreme_dates": ["2026-10-13", "2026-10-15"],
              "legacy_input_jd_comparison": replay,
              "meaning": "Only failure localization; no policy/parameter adjustment; no accounts"}
    path.write_text(json.dumps(record, indent=2) + "\n")
    print(json.dumps({"unit_attempt_dates": [(x["symbol"], x["date"]) for x in facts],
                      "floor_changes": floor_changes, "jd_inputs": replay}, indent=2))


if __name__ == "__main__":
    main()
