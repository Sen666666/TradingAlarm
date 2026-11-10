"""Finite, preregistered numerical checks of 14 existing signal histories."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from numeric import GAMMA4, event_frame_numeric, failed_attempts
from tests_numeric import run as synthetic

ROUND = Path(__file__).resolve().parents[1]
OLD = ROUND.parent / "pv-volume-response-20261020"
REPO = ROUND.parents[1]
LOGS = ["developing_extreme", "confirmed_pivot", "structure_floor"]
RAW = ["developing_extreme_price", "confirmed_pivot_price", "structure_floor_price"]
DISCRETE = ["event", "target", "entered", "exited", "leg_direction", "pivot_age",
            "confirmed_pivot_date", "developing_extreme_date"]


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def changes(a, b, fields, symbol, comparison):
    rows = []
    for col in fields:
        both_nan = a[col].isna() & b[col].isna()
        if pd.api.types.is_numeric_dtype(a[col]):
            same = np.isclose(a[col].to_numpy(dtype=float), b[col].to_numpy(dtype=float),
                              rtol=1e-10, atol=1e-10, equal_nan=True)
        else:
            same = (a[col].fillna("<missing>") == b[col].fillna("<missing>")) | both_nan
        for date in a.index[~np.asarray(same)]:
            rows.append({"symbol": symbol, "comparison": comparison, "date": str(date.date()),
                         "field": col, "new": str(a.loc[date, col]), "reference": str(b.loc[date, col])})
    return rows


def main():
    destination = ROUND / "validation/numeric-attempt1"
    destination.mkdir(exist_ok=False)
    old = module("frozen_numeric_control", OLD / "code/baseline_event_structure.py")
    data = module("frozen_numeric_inputs", OLD / "code/data_utils.py")
    frames, _, manifest = data.load_inputs(OLD)
    checks, old_diffs, input_diffs, attempt_diffs, counts = [], [], [], [], []
    original_hash = digest(OLD / "code/baseline_event_structure.py")
    assert original_hash == "b61e889e684305cbb45223e0e2dd8da324e8e8d0a2d201794e2749eb9441540e"

    def check(name, symbol, fn, **metadata):
        try:
            fn()
            checks.append(dict(test=name, symbol=symbol, passed=True, **metadata))
        except Exception as exc:
            checks.append(dict(test=name, symbol=symbol, passed=False,
                               error=type(exc).__name__, message=str(exc)[:2500], **metadata))

    for symbol, bars in frames.items():
        source = pd.read_csv(OLD / "inputs" / f"{symbol}.csv", index_col="date", parse_dates=True)
        old_frame = old.event_frame(source.close, source.volume)
        full = event_frame_numeric(source.close, source.volume)
        old_diffs += changes(full, old_frame, list(old_frame.columns), symbol, "numeric_vs_frozen")
        scaled = event_frame_numeric(source.close * 7, source.volume * 11)
        normalized = scaled.copy()
        normalized[LOGS] -= math.log(7)
        normalized[RAW] /= 7
        check("unit_all_columns", symbol, lambda: pd.testing.assert_frame_equal(
            full, normalized, check_exact=False, atol=1e-10, rtol=1e-10))
        check("unit_discrete_exact", symbol, lambda: pd.testing.assert_frame_equal(
            full[DISCRETE], scaled[DISCRETE], check_exact=True))
        attempt = failed_attempts(bars, full)
        scaled_bars = bars.copy()
        scaled_bars.loc[:, ["open", "high", "low", "close"]] *= 7
        scaled_bars.loc[:, "volume"] *= 11
        scaled_attempt = failed_attempts(scaled_bars, scaled)
        check("old_v0_attempt_fact_unit_exact", symbol, lambda: pd.testing.assert_series_equal(
            attempt, scaled_attempt, check_exact=True))
        saved = pd.read_csv(OLD / "results/v0-verified" / f"{symbol}-states.csv",
                            index_col="date", parse_dates=True)
        for date in attempt.index[attempt.ne(saved.price_attempt)]:
            attempt_diffs.append(dict(symbol=symbol, date=str(date.date()),
                                      numeric=int(attempt.loc[date]), frozen=int(saved.loc[date, "price_attempt"])))
        for cut in sorted({len(source) // 3, 2 * len(source) // 3, len(source) - 1}):
            prefix = event_frame_numeric(source.close.iloc[:cut], source.volume.iloc[:cut])
            check("prefix_all_columns_exact", symbol, lambda: pd.testing.assert_frame_equal(
                prefix, full.iloc[:cut], check_exact=True), rows=cut)
        legacy_path = REPO / "TradingAlarm/research/results/pv-event-structure-20261020" / f"{symbol}-signals.csv"
        if legacy_path.exists():
            legacy = pd.read_csv(legacy_path, index_col="date", parse_dates=True)
            replay = event_frame_numeric(legacy.close, legacy.volume)
            input_diffs += changes(full, replay, list(full.columns), symbol, "numeric_ohlcv_vs_legacy_input")
            check("legacy_input_replay_all_columns", symbol, lambda: pd.testing.assert_frame_equal(
                full, replay, check_exact=False, atol=1e-10, rtol=1e-10))
        state_fields = ["event", "target", "entered", "exited"]
        count = {col: int(full[col].ne(old_frame[col]).sum()) for col in state_fields}
        counts.append(dict(symbol=symbol, source_rows=len(source), eligible_rows=len(bars),
                           changed_vs_old=count, events=int(full.event.ne(0).sum())))
        full.to_csv(destination / f"{symbol}-numeric-signals.csv", index_label="date")
        print(json.dumps(dict(symbol=symbol, state_differences=count,
                              failed=sum(not x["passed"] for x in checks if x["symbol"] == symbol))), flush=True)
    pd.DataFrame(old_diffs).to_csv(destination / "numeric-vs-frozen.csv", index=False)
    pd.DataFrame(input_diffs).to_csv(destination / "numeric-input-replay-differences.csv", index=False)
    pd.DataFrame(attempt_diffs).to_csv(destination / "old-v0-attempt-fact-changes.csv", index=False)
    record = {
        "meaning": "Numerical repair only; frozen original remains control; no new mechanism or account",
        "gamma4": GAMMA4,
        "policy_limit": "Machine-precision convention, not certified source error bound or universal binary64 scale proof",
        "synthetic": synthetic(), "checks": checks,
        "passed": sum(x["passed"] for x in checks), "failed": sum(not x["passed"] for x in checks),
        "series": counts, "old_field_changes": len(old_diffs), "input_replay_changes": len(input_diffs),
        "old_v0_attempt_fact_changes": len(attempt_diffs),
        "original_baseline_sha256": original_hash,
        "code_sha256": {x: digest(ROUND / "code" / x)
                        for x in ["numeric.py", "tests_numeric.py", "validate_numeric.py"]},
        "input_manifest_sha256": digest(OLD / "inputs/manifest.json"),
        "comparison": "Continuous diagnostics atol=rtol=1e-10; discrete states, dates, prefix comparisons exact",
        "scale_test": "One frozen transformation: all prices x7 and volume x11",
        "account_runs": 0,
    }
    (destination / "summary.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: record[k] for k in ["passed", "failed", "old_field_changes",
                                           "input_replay_changes", "old_v0_attempt_fact_changes"]}))
    return int(bool(record["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
