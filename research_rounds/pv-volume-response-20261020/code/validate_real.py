"""Independent real-history signal validation; no accounts, plots or model edits."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import platform
import sys
import traceback

import numpy as np
import pandas as pd

from baseline_event_structure import event_frame
from data_utils import eligible_prices, load_inputs, sha256
from volume_response import attach_exact_pivots, response_frame


BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]
OLD = REPO / "TradingAlarm/research/results/pv-event-structure-20261020"
MODES = ("none", "volume", "all")
PRICE_COLUMNS = ("floor", "pending_high", "pending_low", "reference_peak", "reference_trough")
LOG_COLUMNS = ("developing_extreme", "confirmed_pivot", "structure_floor")


def set_origin(bars, source):
    valid = (
        np.isfinite(source.close) & source.close.gt(0)
        & np.isfinite(source.volume) & source.volume.gt(0)
    )
    bars.attrs["source_first_close"] = float(source.loc[valid].close.iloc[0])
    return bars


def compare_frames(actual, expected):
    pd.testing.assert_frame_equal(
        actual, expected, check_dtype=True, check_freq=True,
        check_exact=False, atol=1e-10, rtol=1e-10,
    )


def compact_failure(exc):
    return {
        "error": type(exc).__name__, "message": str(exc)[:12000],
        "traceback": traceback.format_exc(limit=3),
    }


def run_check(checks, name, symbol, action, **metadata):
    row = {"test": name, "symbol": symbol, **metadata}
    try:
        detail = action()
        row.update(passed=True)
        if detail:
            row.update(detail)
    except Exception as exc:
        row.update(passed=False, **compact_failure(exc))
    checks.append(row)


def main():
    validation = BASE / "validation"
    validation.mkdir(exist_ok=True)
    output = validation / "real.json"
    if output.exists():
        raise FileExistsError("Refuse overwrite of completed real validation")
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    frames, cases, inputs_manifest = load_inputs(BASE)
    masks = {
        item["symbol"]: item
        for item in json.loads((BASE / "inputs/observation-mask-addendum.json").read_text())["series"]
    }
    checks, excluded, coverage = [], [], []
    code_files = (
        "validate_real.py", "volume_response.py", "baseline_event_structure.py", "data_utils.py",
    )
    code_hashes = {name: sha256(BASE / "code" / name) for name in code_files}
    for symbol, clean in frames.items():
        source = pd.read_csv(BASE / "inputs" / f"{symbol}.csv", index_col="date", parse_dates=True)
        bars = set_origin(clean.copy(), source)
        upstream = event_frame(source.close, source.volume)
        events = attach_exact_pivots(source, upstream)
        full = {mode: response_frame(bars, events, mode)[0] for mode in MODES}
        removed = upstream.loc[~upstream.index.isin(bars.index)]
        excluded.append({
            "symbol": symbol,
            "rows": [
                {"date": str(date.date()), "event": float(row.event),
                 "entered": float(row.entered), "exited": float(row.exited),
                 "leg_direction_known": bool(np.isfinite(row.leg_direction))}
                for date, row in removed.iterrows()
            ],
            "nonzero_event_count": int(removed.event.ne(0).sum()),
            "entry_exit_count": int(removed.entered.sum() + removed.exited.sum()),
        })
        coverage.append({
            "symbol": symbol, "source_rows": len(source), "eligible_rows": len(bars),
            "source_sha256": sha256(BASE / "inputs" / f"{symbol}.csv"),
            "saved_original_exists": (OLD / f"{symbol}-signals.csv").exists(),
        })

        def identity():
            actual = full["none"][["target", "entered", "exited"]]
            expected = upstream.loc[bars.index, actual.columns].astype(actual.dtypes.to_dict())
            compare_frames(actual, expected)
            return {
                "fields": list(actual.columns),
                "note": "Original fields are float encodings of 0/1; cast explicitly to response integer dtypes before equality.",
            }
        run_check(checks, "none_restores_original_state", symbol, identity)

        def saved_candidate_identity():
            path = BASE / "results/v0-verified" / f"{symbol}-states.csv"
            saved = pd.read_csv(path, index_col="date", parse_dates=True)
            columns = ["target", "pending", "floor", "entered", "exited", "created", "resolved"]
            expected = saved[columns].astype(full["volume"][columns].dtypes.to_dict())
            compare_frames(full["volume"][columns], expected)
            return {
                "fields": columns, "saved_sha256": sha256(path),
                "note": "API-origin guards and ledger date dtype changes do not change saved causal trajectory values.",
            }
        run_check(checks, "current_model_matches_saved_verified_candidate", symbol, saved_candidate_identity)

        def excluded_are_inert():
            assert removed.event.eq(0).all(), "OHLC mask removed a nonzero upstream event"
            assert removed.entered.eq(0).all() and removed.exited.eq(0).all(), (
                "OHLC mask removed a state transition"
            )
        run_check(checks, "excluded_source_dates_have_no_events_or_transitions", symbol, excluded_are_inert)

        saved_path = OLD / f"{symbol}-signals.csv"
        if saved_path.exists():
            def saved_identity():
                saved = pd.read_csv(saved_path, index_col="date", parse_dates=True)
                compare_frames(upstream, saved[upstream.columns])
                return {"fields": list(upstream.columns), "saved_sha256": sha256(saved_path)}
            run_check(checks, "upstream_matches_saved_original_all_fields", symbol, saved_identity)

        for cut in sorted({len(bars) // 3, 2 * len(bars) // 3, len(bars) - 1}):
            cutoff = bars.index[cut - 1]
            prefix_source = source.loc[:cutoff].copy()
            prefix_bars = set_origin(
                eligible_prices(prefix_source, symbol, masks[symbol]["exclude_price_dates"]),
                prefix_source,
            )
            prefix_events = attach_exact_pivots(
                prefix_source, event_frame(prefix_source.close, prefix_source.volume),
            )
            for mode in MODES:
                def prefix_check(mode=mode):
                    observed, _ = response_frame(prefix_bars, prefix_events, mode)
                    compare_frames(observed, full[mode].iloc[:cut])
                    return {"columns": list(observed.columns), "dtype_checked": True}
                run_check(
                    checks, "complete_state_prefix", symbol, prefix_check,
                    mode=mode, eligible_prefix_rows=cut, cutoff=str(cutoff.date()),
                )

        scaled_source = source.copy()
        scaled_source.loc[:, ["open", "high", "low", "close"]] *= 7.0
        scaled_source.loc[:, "volume"] *= 11.0
        scaled_bars = set_origin(
            eligible_prices(scaled_source, symbol, masks[symbol]["exclude_price_dates"]),
            scaled_source,
        )
        scaled_upstream = event_frame(scaled_source.close, scaled_source.volume)
        scaled_events = attach_exact_pivots(scaled_source, scaled_upstream)

        def scaled_upstream_identity():
            normalized = scaled_upstream.copy()
            normalized.loc[:, list(LOG_COLUMNS)] -= np.log(7.0)
            compare_frames(normalized, upstream)
        run_check(
            checks, "upstream_unit_invariance", symbol, scaled_upstream_identity,
            price_factor=7, volume_factor=11,
        )
        for mode in MODES:
            def scale_check(mode=mode):
                scaled, _ = response_frame(scaled_bars, scaled_events, mode)
                normalized = scaled.copy()
                normalized.loc[:, list(PRICE_COLUMNS)] /= 7.0
                compare_frames(normalized, full[mode])
                return {"dtype_checked": True, "normalized_price_fields": list(PRICE_COLUMNS)}
            run_check(
                checks, "complete_state_unit_invariance", symbol, scale_check,
                mode=mode, price_factor=7, volume_factor=11,
            )

        def constant_new_volume():
            constant = bars.copy()
            constant.loc[:, "volume"] = 100.0
            constant.attrs["source_first_close"] = bars.attrs["source_first_close"]
            result, ledger = response_frame(constant, events, "volume")
            assert result.created.eq(0).all(), "Constant new volume created a conflict"
            assert result.pending.eq(0).all(), "Constant new volume retained a conflict"
            assert ledger.empty, "Constant new volume created an event ledger"
            compare_frames(
                result[["target", "entered", "exited", "floor"]],
                full["none"][["target", "entered", "exited", "floor"]],
            )
            return {
                "upstream_events_fixed": True, "new_conflicts": int(result.created.sum()),
                "compared_fields": ["target", "entered", "exited", "floor"],
            }
        run_check(checks, "constant_volume_only_in_new_mechanism", symbol, constant_new_volume)
        print(json.dumps({
            "symbol": symbol, "checks": sum(x["symbol"] == symbol for x in checks),
            "failed": sum(x["symbol"] == symbol and not x["passed"] for x in checks),
        }), flush=True)

    for name, digest in code_hashes.items():
        if sha256(BASE / "code" / name) != digest:
            checks.append({"test": "code_unchanged_during_validation", "symbol": None,
                           "passed": False, "file": name})
    forbidden = ("run_event_structure", "run_competing_state", "campaign_engine", "run_study")
    assert not any(name in sys.modules for name in forbidden), "Forbidden runner imported"
    record = {
        "started_utc": started, "completed_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "meaning": "Independent pure-signal checks on existing development histories; no economic evaluation",
        "code_sha256": code_hashes,
        "input_manifest_sha256": sha256(BASE / "inputs/manifest.json"),
        "versions": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "series_count": len(frames), "fixed_cases": len(cases),
        "coverage": coverage, "excluded_source_dates": excluded,
        "passed_checks": sum(x["passed"] for x in checks),
        "failed_checks": sum(not x["passed"] for x in checks),
        "checks": checks,
        "scope": {
            "prefix": "Every output column and dtype in each of three modes at three fixed eligible-row cutoffs.",
            "units": "Full source OHLC * 7 and volume * 11, recomputing upstream and candidate; absolute output prices divided by 7.",
            "constant_volume": "Only volume passed to response_frame is replaced; upstream original events remain fixed.",
            "ledger": "Prefix compares causal state rows, not an unresolved ledger record against its future resolution.",
            "tolerances": {"atol": 1e-10, "rtol": 1e-10, "dtype_checked": True},
        },
        "account_runs": 0, "network_requests": 0, "plots": 0,
    }
    if record["failed_checks"]:
        attempt = 1
        while (validation / f"real-attempt-{attempt}.json").exists():
            attempt += 1
        destination = validation / f"real-attempt-{attempt}.json"
    else:
        destination = output
    destination.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({
        "output": str(destination), "passed": record["passed_checks"],
        "failed": record["failed_checks"], "sha256": sha256(destination),
    }), flush=True)
    return int(bool(record["failed_checks"]))


if __name__ == "__main__":
    raise SystemExit(main())
