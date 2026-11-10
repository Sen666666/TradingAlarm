"""Independent complete upstream checks after source-precision repair.

The original failed numeric evidence remains unchanged. This validator tests
the current upstream contract on frozen prepared inputs; it never calls a
participation model, account, ranking, or the old price-attempt label.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

from data_utils import load_inputs, load_source, source_directory, sha256
from numeric import event_frame_numeric

BASE = Path(__file__).resolve().parents[1]
SCALES = ((7.0, 11.0), (0.1, 0.01))
ATOL = RTOL = 1e-10
LOGS = ("developing_extreme", "confirmed_pivot", "structure_floor")
PRICES = ("developing_extreme_price", "confirmed_pivot_price", "structure_floor_price")
DISCRETE = ("event", "target", "entered", "exited", "leg_direction", "pivot_age",
            "confirmed_pivot_date", "developing_extreme_date")
CONTINUOUS = LOGS + PRICES + ("confirmation",)


def json_value(value):
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (float, np.floating)) and not math.isfinite(value):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    return value


def differences(actual, expected, exact):
    result = {
        "actual_shape": list(actual.shape), "expected_shape": list(expected.shape),
        "actual_columns": list(actual.columns), "expected_columns": list(expected.columns),
        "actual_only_indices": [str(x) for x in actual.index.difference(expected.index)],
        "expected_only_indices": [str(x) for x in expected.index.difference(actual.index)],
        "dtype_differences": {}, "values": [],
    }
    indices = actual.index.intersection(expected.index)
    for column in actual.columns.intersection(expected.columns):
        left, right = actual.loc[indices, column], expected.loc[indices, column]
        if left.dtype != right.dtype:
            result["dtype_differences"][column] = [str(left.dtype), str(right.dtype)]
        if pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right):
            a = left.to_numpy(dtype=float, na_value=np.nan)
            b = right.to_numpy(dtype=float, na_value=np.nan)
            same = ((a == b) | (np.isnan(a) & np.isnan(b))) if exact else np.isclose(
                a, b, atol=ATOL, rtol=RTOL, equal_nan=True)
        else:
            same = left.fillna("<missing>").eq(right.fillna("<missing>")).to_numpy()
        for index in indices[~same]:
            result["values"].append({
                "date": str(index.date()), "column": column,
                "actual": json_value(actual.loc[index, column]),
                "expected": json_value(expected.loc[index, column]),
            })
    return result


def main():
    destination = BASE / "validation/upstream-input-fixed"
    report_path = BASE / "validation/upstream-input-fixed.json"
    if report_path.exists():
        raise FileExistsError("Refuse to overwrite upstream validation evidence")
    destination.mkdir(exist_ok=False)
    names = ("numeric.py", "prepare_input.py", "data_utils.py", "validate_upstream_prepared.py")
    hashes = {name: sha256(BASE / "code" / name) for name in names}
    for name in names:
        shutil.copy2(BASE / "code" / name, destination / name)
    manifest_path = source_directory(BASE) / "manifest.json"
    manifest_hash = sha256(manifest_path)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    bars, _, manifest = load_inputs(BASE)
    checks, failures, coverage = [], [], []

    def save(row):
        checks.append(row)
        with (destination / "checks.jsonl").open("a") as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")

    def check(name, symbol, actual, expected, *, exact, **metadata):
        row = dict(test=name, symbol=symbol, exact=exact, **metadata)
        try:
            pd.testing.assert_frame_equal(
                actual, expected, check_dtype=True, check_freq=True,
                check_exact=exact, atol=ATOL, rtol=RTOL)
            row["passed"] = True
        except Exception as exc:
            row.update(passed=False, error=type(exc).__name__, message=str(exc))
            row["difference"] = differences(actual, expected, exact)
            failures.append(row)
        save(row)

    for record in manifest["series"]:
        symbol = record["symbol"]
        source = load_source(symbol, BASE)
        full = event_frame_numeric(source.close, source.volume)
        # A new output cannot silently escape either the continuous or exact test.
        assert set(full.columns) == set(CONTINUOUS + DISCRETE)
        for price_scale, volume_scale in SCALES:
            # Preserve the original binary64 stress: no Decimal normalization
            # after multiplication and no re-preparation of the scaled input.
            scaled = event_frame_numeric(
                source.close.astype(float) * price_scale,
                source.volume.astype(float) * volume_scale)
            normalized = scaled.copy()
            normalized[list(LOGS)] -= math.log(price_scale)
            normalized[list(PRICES)] /= price_scale
            metadata = dict(price_scale=price_scale, volume_scale=volume_scale)
            check("scaled_all_columns_and_types", symbol, normalized, full,
                  exact=False, **metadata)
            check("scaled_dates_and_discrete_exact", symbol,
                  scaled[list(DISCRETE)], full[list(DISCRETE)], exact=True, **metadata)
        cuts = sorted({len(source) // 3, 2 * len(source) // 3, len(source) - 1})
        for cut in cuts:
            cutoff = source.index[cut - 1]
            # Source strings are independently prepared from the same origin.
            # No state or factors are sliced out of the completed run.
            prefix_source = load_source(symbol, BASE, cutoff=cutoff)
            prefix = event_frame_numeric(prefix_source.close, prefix_source.volume)
            check("raw_prefix_prepared_upstream_all_columns_exact", symbol,
                  prefix, full.iloc[:cut], exact=True, rows=cut, cutoff=str(cutoff.date()))
        coverage.append(dict(
            symbol=symbol, source_rows=len(source), eligible_rows=len(bars[symbol]),
            source_sha256=record["source_sha256"], prepared_sha256=record["sha256"],
            fields=list(full.columns), dtypes={col: str(dtype) for col, dtype in full.dtypes.items()},
            cuts=cuts))
        print(json.dumps({
            "symbol": symbol, "checks": sum(x["symbol"] == symbol for x in checks),
            "failed": sum(not x["passed"] for x in checks if x["symbol"] == symbol),
        }), flush=True)
    for name, digest in hashes.items():
        save(dict(test="code_unchanged_during_validation", symbol=name,
                  passed=sha256(BASE / "code" / name) == digest))
    save(dict(test="prepared_manifest_unchanged_during_validation", symbol="manifest",
              passed=sha256(manifest_path) == manifest_hash))
    prohibited = ("participation", "campaign_engine", "run_study", "run_event_structure",
                  "run_competing_state")
    assert not any(module in sys.modules for module in prohibited)
    result = dict(
        started_utc=started, completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        meaning="Complete current numeric upstream contract on frozen source-precision-v1 inputs; no account",
        code_sha256=hashes, prepared_manifest_sha256=manifest_hash,
        source_manifest_sha256=manifest["source_manifest_sha256"],
        series_count=len(coverage), coverage=coverage, scales=SCALES,
        tolerances=dict(atol=ATOL, rtol=RTOL), prefix_exact=True,
        log_fields_subtract_log_price_scale=LOGS, raw_fields_divide_price_scale=PRICES,
        exact_fields=DISCRETE, total_model_fields=len(CONTINUOUS + DISCRETE),
        known_limit="Finite input/scale evidence, not a universal binary64 unit invariance theorem",
        old_price_attempt="Not a field or branch of this new contract. Original diagnostic failures remain recorded.",
        passed=sum(x["passed"] for x in checks), failed=sum(not x["passed"] for x in checks),
        checks=checks, failures=failures, account_runs=0, network_requests=0)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(report_path), "passed": result["passed"],
                      "failed": result["failed"]}), flush=True)
    return int(bool(result["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
