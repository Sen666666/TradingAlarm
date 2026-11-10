"""Causal source-precision repair. No model/account import or data acquisition.

Nine explicitly identified total-return histories replace daily telescoping
price products with action-only factor recurrence. A-stock theoretical-ex-price
histories and unadjusted indices retain saved prices; they are not re-derived.
"""
from __future__ import annotations

import argparse
import csv
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import json
import math
from pathlib import Path
import shutil

import numpy as np
import pandas as pd

from data_utils import eligible_prices, sha256

BASE = Path(__file__).resolve().parents[1]
OHLC = ("open", "high", "low", "close")
RAW_OHLC = tuple("raw_" + x for x in OHLC)
CLASSIFICATION = {
    "USHJ518880": ("ETF", "total_return", "2018-07-17"),
    "USHJ512480": ("ETF", "total_return", "2019-06-12"),
    "USHJ510300": ("ETF", "total_return", "2018-07-17"),
    "HK00002": ("HK stock", "total_return", "2020-01-02"),
    "HK09618": ("HK stock", "total_return", "2020-06-18"),
    "HK00700": ("HK stock", "total_return", "2020-01-02"),
    "HK03033": ("HK ETF", "total_return", "2020-08-28"),
    "HK00101": ("HK stock", "total_return", "2020-01-02"),
    "HK03690": ("HK stock", "total_return", "2020-04-27"),
    "600919.SH": ("A stock", "saved_theoretical_factor", "2023-09-06"),
    "600059.SH": ("A stock", "saved_theoretical_factor", "2023-09-06"),
    "600917.SH": ("A stock", "saved_theoretical_factor", "2023-09-06"),
    "URFI881129": ("communication theme index proxy", "unadjusted_index", "2007-08-01"),
    "UZZI000994": ("communication theme index proxy", "unadjusted_index", "2005-01-04"),
}


def decimal_text(value):
    if not isinstance(value, str):
        raise TypeError("Source price/action values must be CSV strings, never Decimal(float)")
    result = Decimal(value)
    if not result.is_finite():
        raise ValueError("Non-finite source decimal")
    return result


def native_strings(raw, unit_scale="1"):
    """Decode an explicit source-unit transform before any float conversion.

    A positive Decimal unit scalar applies to raw OHLC, saved OHLC and cash.
    This supplements, not replaces, independent binary64 scaling stress tests.
    """
    result = raw.copy()
    if "date" in result:
        result = result.set_index("date")
    result.index = pd.DatetimeIndex(result.index, name="date")
    if not result.index.is_unique or not result.index.is_monotonic_increasing:
        raise ValueError("Ordered unique source clock required")
    with localcontext() as context:
        context.prec, context.rounding = 40, ROUND_HALF_EVEN
        scale = decimal_text(unit_scale)
        if scale <= 0:
            raise ValueError("Positive declared price unit required")
        for col in OHLC + RAW_OHLC + ("cash_signal_adjustment",):
            if col in result:
                result[col] = result[col].map(
                    lambda value: format((decimal_text(value) / scale).normalize(), "f"))
    return result


def prepare_frame(raw, symbol, unit_scale="1"):
    """Pure prefix-causal preparation from the original, explicit source start.

    unit_scale='7' means supplied dimensional price/cash strings are in 7x
    units; the result is canonical native-unit prices. No date may be silently
    used as a new origin. Exact source strings remain in the immutable inputs.
    """
    if symbol not in CLASSIFICATION:
        raise ValueError("Symbol outside audited source whitelist")
    source = native_strings(raw, unit_scale)
    if source.empty:
        raise ValueError("Empty source prefix")
    _, method, first_date = CLASSIFICATION[symbol]
    if source.index[0] != pd.Timestamp(first_date):
        raise ValueError("Truncated-start source requires an explicit earlier factor state")
    if decimal_text(source.iloc[0].adjustment_factor) != 1:
        raise ValueError("Original source factor must start at 1")
    result = source.copy()
    with localcontext() as context:
        context.prec, context.rounding = 40, ROUND_HALF_EVEN
        if method == "total_return":
            needed = set(RAW_OHLC) | {"cash_signal_adjustment", "split_ratio"}
            if not needed.issubset(source.columns):
                raise ValueError("Missing explicit total-return source fields")
            if decimal_text(source.iloc[0].cash_signal_adjustment) != 0 or decimal_text(source.iloc[0].split_ratio) != 1:
                raise ValueError("First observation cannot silently discard an action")
            factor = Decimal(1)
            columns = {col: [] for col in OHLC + ("adjustment_factor",)}
            for _, row in source.iterrows():
                raw_close = decimal_text(row.raw_close)
                cash, split = decimal_text(row.cash_signal_adjustment), decimal_text(row.split_ratio)
                if raw_close <= 0 or cash < 0 or split <= 0:
                    raise ValueError("Invalid explicit price/action")
                if cash != 0 and split != 1:
                    raise ValueError("Same-day cash and split remain unsupported")
                if cash != 0 or split != 1:
                    factor *= split + cash / raw_close
                # No-action observations do not recompute or reassign factor.
                for col in OHLC:
                    raw_price = decimal_text(row["raw_" + col])
                    if raw_price <= 0:
                        raise ValueError("Invalid raw price")
                    columns[col].append(float(raw_price * factor))
                columns["adjustment_factor"].append(float(factor))
            for col, values in columns.items():
                result[col] = values
        else:
            # A stocks preserve saved theoretical-ex-price signals. Re-multiply
            # their rounded factor would define a different, unapproved series.
            for col in OHLC + ("adjustment_factor",):
                result[col] = source[col].map(lambda x: float(decimal_text(x)))
            if method == "unadjusted_index" and not result.adjustment_factor.eq(1).all():
                raise ValueError("Index with a non-unit factor is outside this contract")
        # Deliberately preserve the previous volume convention and values.
        for col in ("volume", "volume_factor"):
            result[col] = source[col].map(lambda x: float(decimal_text(x)))
    return result


def scaled_source_strings(raw, scale):
    result = raw.copy()
    with localcontext() as context:
        context.prec, context.rounding = 40, ROUND_HALF_EVEN
        multiplier = decimal_text(scale)
        for col in OHLC + RAW_OHLC + ("cash_signal_adjustment",):
            if col in result:
                result[col] = result[col].map(lambda x: str(decimal_text(x) * multiplier))
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=BASE / "prepared/source-precision-v1")
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise FileExistsError("Refuse to overwrite prepared evidence")
    output.mkdir(parents=True)
    source_dir = BASE / "inputs"
    manifest = json.loads((source_dir / "manifest.json").read_text())
    masks = {x["symbol"]: x for x in json.loads(
        (source_dir / "observation-mask-addendum.json").read_text())["series"]}
    if {r["symbol"] for r in manifest["series"]} != set(CLASSIFICATION):
        raise ValueError("Manifest differs from the audited 14-series whitelist")
    summary, details, factor_segments, checks, prepared_series = [], [], [], [], []
    for record in manifest["series"]:
        symbol, file = record["symbol"], record["file"]
        kind, method, _ = CLASSIFICATION[symbol]
        if record["source_metadata"]["kind"] != kind:
            raise ValueError("Source manifest kind mismatch")
        path = source_dir / file
        if sha256(path) != record["sha256"]:
            raise ValueError("Frozen source bytes changed")
        raw = pd.read_csv(path, dtype=str, keep_default_na=False, index_col="date")
        prepared = prepare_frame(raw, symbol)
        original = pd.read_csv(path, float_precision="round_trip", index_col="date", parse_dates=True)
        if method == "total_return":
            source_dates = {
                str(pd.Timestamp(date).date()) for date, row in raw.iterrows()
                if decimal_text(row.cash_signal_adjustment) != 0 or decimal_text(row.split_ratio) != 1}
            metadata = record["source_metadata"]
            declared_dates = {str(x["ex_date"]) for x in
                              metadata.get("dividends", []) + metadata.get("in_kind_signal_adjustments", [])}
            declared_dates |= {str(x["date"]) for x in metadata.get("splits", [])}
            if source_dates != declared_dates:
                raise ValueError("Stored action markers differ from declared source actions")
            segment = -1
            last_factor = None
            for date, row in prepared.iterrows():
                action = str(date.date()) in source_dates
                if segment < 0 or action:
                    segment += 1
                    factor_segments.append(dict(symbol=symbol, segment=segment,
                                                start=str(date.date()), factor=repr(row.adjustment_factor),
                                                action=action))
                elif row.adjustment_factor != last_factor:
                    raise AssertionError("Factor drifted on a no-action observation")
                last_factor = row.adjustment_factor
        else:
            source_dates = set()
            assert np.array_equal(prepared[list(OHLC)].to_numpy(), original[list(OHLC)].to_numpy())
        assert np.array_equal(prepared.volume.to_numpy(), original.volume.to_numpy())
        assert np.array_equal(prepared.volume_factor.to_numpy(), original.volume_factor.to_numpy())
        old_mask = eligible_prices(original, symbol, masks[symbol]["exclude_price_dates"])
        new_mask = eligible_prices(prepared, symbol, masks[symbol]["exclude_price_dates"])
        assert old_mask.index.equals(new_mask.index), "Observation mask changed"
        assert len(new_mask) == record["price_observed_rows"], "Original observation count changed"
        checks.append(dict(symbol=symbol, test="source_kind_actions_volume_mask", passed=True))
        maximum = 0.0
        changed_cells = 0
        # Conservative operation-count guard for the old positive telescoping
        # arithmetic. This is a reconstruction diagnostic, never a price rule.
        operations = 8 * len(raw) + 32
        u = np.finfo(float).eps / 2
        numeric_budget = operations * u / (1 - operations * u)
        for col in OHLC + ("adjustment_factor",):
            before, after = original[col], prepared[col]
            relative = (after - before).abs() / before.abs()
            maximum = max(maximum, float(relative.max()))
            for date in prepared.index[after.ne(before)]:
                changed_cells += 1
                details.append(dict(symbol=symbol, date=str(date.date()), field=col,
                                    original=repr(before.loc[date]), prepared=repr(after.loc[date]),
                                    relative_difference=relative.loc[date],
                                    action_date=str(date.date()) in source_dates))
        assert maximum <= numeric_budget, "Difference exceeds the declared arithmetic reconstruction guard"
        for cut in sorted({len(raw) // 3, 2 * len(raw) // 3, len(raw) - 1}):
            pd.testing.assert_frame_equal(prepare_frame(raw.iloc[:cut], symbol), prepared.iloc[:cut], check_exact=True)
            checks.append(dict(symbol=symbol, test="source_prefix_exact", rows=cut, passed=True))
        for scale in ("7", "0.1"):
            transformed = scaled_source_strings(raw, scale)
            normalized = prepare_frame(transformed, symbol, unit_scale=scale)
            pd.testing.assert_frame_equal(normalized, prepared, check_exact=True)
            checks.append(dict(symbol=symbol, test="explicit_decimal_unit_roundtrip_exact", scale=scale, passed=True))
        prepared.to_csv(output / file, index_label="date")
        reread = pd.read_csv(output / file, float_precision="round_trip", index_col="date", parse_dates=True)
        pd.testing.assert_frame_equal(reread[list(OHLC) + ["volume", "adjustment_factor", "volume_factor"]],
                                      prepared[list(OHLC) + ["volume", "adjustment_factor", "volume_factor"]], check_exact=True)
        checks.append(dict(symbol=symbol, test="prepared_csv_roundtrip_core_exact", passed=True))
        summary.append(dict(symbol=symbol, method=method, rows=len(raw), eligible_rows=len(new_mask),
                            explicit_actions=len(source_dates), changed_price_factor_cells=changed_cells,
                            max_relative_difference=maximum, operation_count_guard=numeric_budget))
        new_record = dict(record)
        new_record.update(sha256=sha256(output / file), source=str(path.relative_to(BASE)),
                          source_sha256=record["sha256"], precision_method=method)
        prepared_series.append(new_record)
    for file in ("cases.json", "observation-mask-addendum.json"):
        shutil.copy2(source_dir / file, output / file)
    pd.DataFrame(details).to_csv(output / "changes.csv", index=False)
    pd.DataFrame(factor_segments).to_csv(output / "factor-segments.csv", index=False)
    prepared_manifest = {
        "meaning": "Independent source-precision representation; original inputs remain immutable",
        "source_manifest_sha256": sha256(source_dir / "manifest.json"),
        "code_sha256": sha256(Path(__file__)),
        "decimal_context": {"precision": 40, "rounding": "ROUND_HALF_EVEN"},
        "parser": "CSV strings for preparation; float_precision=round_trip for binary64 ingestion",
        "series": prepared_series, "cases_sha256": sha256(output / "cases.json"),
        "copied_files": {"observation-mask-addendum.json":
                         {"sha256": sha256(output / "observation-mask-addendum.json")}},
        "volume_rule_changed": False, "history": "Previously seen development history",
        "unit_scope": "Explicit source Decimal normalization supplements, never replaces, rounded-float scaling tests",
    }
    (output / "manifest.json").write_text(json.dumps(prepared_manifest, ensure_ascii=False, indent=2) + "\n")
    validation = dict(series=summary, checks=checks, passed=len(checks), failed=0,
                      observation_rows=sum(x["eligible_rows"] for x in summary),
                      account_runs=0, model_runs=0, source_manifest_sha256=prepared_manifest["source_manifest_sha256"])
    (output / "preparation-validation.json").write_text(json.dumps(validation, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(output=str(output), checks=len(checks), series=summary), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
