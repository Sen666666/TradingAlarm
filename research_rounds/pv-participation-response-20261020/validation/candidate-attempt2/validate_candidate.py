"""Independent full-contract signal/ledger checks. No accounts or PnL."""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
import shutil
import sys

import numpy as np
import pandas as pd

from data_utils import eligible_prices, load_inputs, sha256
from numeric import compare, event_frame_numeric
from participation import participation_frame

BASE = Path(__file__).resolve().parents[1]
MODES = ("none", "volume", "all")
SCALES = ((7.0, 11.0), (0.1, 0.01))
STATE_PRICES = ("floor", "pending_reclaim", "pending_lower")
LEDGER_PRICES = ("reclaim", "lower", "event_open", "event_high", "event_close")
LEDGER_VOLUMES = ("event_volume", "volume_baseline")
STATE_DISCRETE = ("target", "entered", "exited", "pending", "pending_id",
                  "pending_since", "created", "response", "consumed_by_base",
                  "independent_entry", "ended_id", "entry_kind", "high_effort",
                  "declined", "price_event", "ready")
LEDGER_DISCRETE = ("id", "created_date", "created_observation", "created_on_exit",
                   "resolved_date", "outcome", "response", "independent_entry",
                   "original_entry_same_day", "waiting_observations")
ATOL = RTOL = 1e-10


def value(x):
    if x is None or x is pd.NA:
        return None
    if isinstance(x, (float, np.floating)) and not math.isfinite(x):
        return str(x)
    if isinstance(x, np.generic):
        return x.item()
    if isinstance(x, (pd.Timestamp, dt.datetime)):
        return x.isoformat()
    return x


def differences(actual, expected, exact):
    detail = {
        "actual_shape": list(actual.shape), "expected_shape": list(expected.shape),
        "actual_columns": list(actual.columns), "expected_columns": list(expected.columns),
        "dtype_differences": {},
        "actual_only_indices": [value(x) for x in actual.index.difference(expected.index)],
        "expected_only_indices": [value(x) for x in expected.index.difference(actual.index)],
        "values": [],
    }
    indices = actual.index.intersection(expected.index)
    for col in actual.columns.intersection(expected.columns):
        a, b = actual.loc[indices, col], expected.loc[indices, col]
        if a.dtype != b.dtype:
            detail["dtype_differences"][col] = [str(a.dtype), str(b.dtype)]
        if pd.api.types.is_numeric_dtype(a) and pd.api.types.is_numeric_dtype(b):
            aa, bb = a.to_numpy(dtype=float, na_value=np.nan), b.to_numpy(dtype=float, na_value=np.nan)
            same = (aa == bb) | (np.isnan(aa) & np.isnan(bb)) if exact else np.isclose(
                aa, bb, atol=ATOL, rtol=RTOL, equal_nan=True)
        else:
            same = (a.fillna("<missing>").astype(str) == b.fillna("<missing>").astype(str)).to_numpy()
        for index in indices[~same]:
            row = {"index": value(index), "column": col,
                   "actual": value(actual.loc[index, col]), "expected": value(expected.loc[index, col])}
            for anchor in ("id", "created_date", "resolved_date"):
                if anchor in actual:
                    row[anchor] = value(actual.loc[index, anchor])
            detail["values"].append(row)
    return detail


def ledger_asof(ledger, cutoff, last_observation):
    """Full ledger's causal view: future outcomes are unknown at the cutoff."""
    result = ledger.loc[ledger.created_date.le(str(cutoff.date()))].copy()
    unresolved = result.resolved_date.isna() | result.resolved_date.gt(str(cutoff.date()))
    result.loc[unresolved, "resolved_date"] = pd.NA
    result.loc[unresolved, "outcome"] = "open"
    for col in ("response", "independent_entry", "original_entry_same_day"):
        result.loc[unresolved, col] = 0
    result.loc[unresolved, "resolution_volume_ratio"] = np.nan
    result.loc[unresolved, "waiting_observations"] = (
        last_observation - result.loc[unresolved, "created_observation"])
    return result.reset_index(drop=True)


def branch_predicates(bars, events, states):
    """Audit actual booleans used in price/volume conditional branches.

    Continuous canonical prices are checked separately. A relation not consulted
    by the state machine on this observation is NA, not a fabricated decision.
    """
    result = []
    before = None
    previous_close = math.nan
    for date, bar in bars.iterrows():
        state, event = states.loc[date], events.loc[date]
        row = {"date": date, "declined_predicate": None, "high_effort_predicate": None,
               "floor_failed_predicate": None, "lower_broken_predicate": None,
               "reclaim_crossed_predicate": None, "old_floor_raised_predicate": None}
        if math.isfinite(previous_close):
            row["declined_predicate"] = compare(bar.close, previous_close) < 0
        if math.isfinite(state.volume_ratio):
            row["high_effort_predicate"] = compare(state.volume_ratio, 2.0) >= 0
        if before is not None and before.target == 1:
            row["floor_failed_predicate"] = compare(bar.close, before.floor) <= 0
            if event.event == 1 and not row["floor_failed_predicate"]:
                row["old_floor_raised_predicate"] = compare(event.confirmed_pivot_price, before.floor) > 0
        if before is not None and before.pending == 1:
            row["lower_broken_predicate"] = compare(bar.close, before.pending_lower) < 0
            # This upper predicate is not evaluated after a lower rejection.
            if not row["lower_broken_predicate"]:
                row["reclaim_crossed_predicate"] = compare(bar.close, before.pending_reclaim) > 0
        result.append(row)
        previous_close, before = float(bar.close), state
    frame = pd.DataFrame(result).set_index("date")
    for col in frame:
        frame[col] = frame[col].astype("boolean")
    return frame


def main():
    validation = BASE / "validation"
    validation.mkdir(exist_ok=True)
    if (validation / "candidate.json").exists():
        raise FileExistsError("Refuse to overwrite completed candidate validation")
    attempt = 1
    while (validation / f"candidate-attempt{attempt}.json").exists():
        attempt += 1
    # Reserve a new evidence directory, including the code used for this attempt.
    artifact = validation / f"candidate-attempt{attempt}"
    artifact.mkdir(exist_ok=False)
    code_names = ("participation.py", "numeric.py", "data_utils.py", "validate_candidate.py")
    code_hash = {name: sha256(BASE / "code" / name) for name in code_names}
    for name in code_names:
        shutil.copy2(BASE / "code" / name, artifact / name)
    started = dt.datetime.now(dt.timezone.utc).isoformat()
    frames, cases, manifest = load_inputs(BASE)
    mask = {x["symbol"]: x for x in json.loads(
        (BASE / "inputs/observation-mask-addendum.json").read_text())["series"]}
    checks, failures, coverage = [], [], []

    def append_check(row):
        checks.append(row)
        # Persist completed checks even if later harness preparation fails.
        with (artifact / "checks.jsonl").open("a") as stream:
            saved = dict(row)
            if "difference_index" in saved:
                saved["difference"] = failures[saved["difference_index"]]
            stream.write(json.dumps(saved, ensure_ascii=False) + "\n")

    def check_frame(name, symbol, actual, expected, *, exact=False, **metadata):
        row = dict(test=name, symbol=symbol, exact=exact, **metadata)
        try:
            pd.testing.assert_frame_equal(actual, expected, check_dtype=True, check_freq=True,
                                          check_exact=exact, atol=ATOL, rtol=RTOL)
            row["passed"] = True
        except Exception as exc:
            row.update(passed=False, error=type(exc).__name__, message=str(exc).split("\n\n")[0])
            row["difference_index"] = len(failures)
            failures.append(dict(test=name, symbol=symbol, **metadata,
                                 detail=differences(actual, expected, exact)))
        append_check(row)

    def check_invariant(name, symbol, condition, detail=None):
        passed = bool(condition)
        append_check(dict(test=name, symbol=symbol, passed=passed, detail=detail))
        if not passed:
            failures.append(dict(test=name, symbol=symbol, detail=detail))

    for symbol, bars in frames.items():
        source = pd.read_csv(BASE / "inputs" / f"{symbol}.csv", index_col="date", parse_dates=True)
        upstream = event_frame_numeric(source.close, source.volume)
        aligned = upstream.reindex(bars.index)
        full = {mode: participation_frame(bars, upstream, mode) for mode in MODES}
        branches = {mode: branch_predicates(bars, aligned, full[mode][0]) for mode in MODES}
        excluded = upstream.loc[~upstream.index.isin(bars.index)]
        check_invariant("excluded_source_rows_have_no_events_or_transitions", symbol,
                        excluded.event.eq(0).all() and excluded.entered.eq(0).all() and excluded.exited.eq(0).all(),
                        [dict(date=str(date.date()), event=value(row.event), entered=value(row.entered),
                              exited=value(row.exited)) for date, row in excluded.iterrows()])
        canonical = aligned[["target", "entered", "exited", "structure_floor_price"]].rename(
            columns={"structure_floor_price": "floor"})
        canonical[["target", "entered", "exited"]] = canonical[["target", "entered", "exited"]].astype("int64")
        check_frame("none_restores_numeric_upstream", symbol,
                    full["none"][0][canonical.columns], canonical, exact=True)
        constant = bars.copy()
        constant.loc[:, "volume"] = 100.0
        constant_state, constant_ledger = participation_frame(constant, upstream, "volume")
        check_frame("constant_new_volume_state_restores_none", symbol,
                    constant_state[list(canonical.columns)], full["none"][0][canonical.columns], exact=True)
        check_invariant("constant_new_volume_has_no_memory", symbol,
                        constant_ledger.empty and constant_state.created.eq(0).all() and constant_state.pending.eq(0).all())
        for cut in sorted({len(bars) // 3, 2 * len(bars) // 3, len(bars) - 1}):
            cutoff = bars.index[cut - 1]
            prefix_source = source.loc[:cutoff]
            prefix_bars = eligible_prices(prefix_source, symbol, mask[symbol]["exclude_price_dates"])
            prefix_upstream = event_frame_numeric(prefix_source.close, prefix_source.volume)
            for mode in MODES:
                state, ledger = participation_frame(prefix_bars, prefix_upstream, mode)
                check_frame("prefix_state_all_columns_and_types", symbol, state, full[mode][0].iloc[:cut],
                            exact=True, mode=mode, cut=cut, cutoff=str(cutoff.date()))
                check_frame("prefix_ledger_asof_all_columns_and_types", symbol, ledger,
                            ledger_asof(full[mode][1], cutoff, cut - 1),
                            exact=True, mode=mode, cut=cut, cutoff=str(cutoff.date()))
        for price_factor, volume_factor in SCALES:
            scaled_source = source.copy()
            for column in ("open", "high", "low", "close"):
                scaled_source[column] = scaled_source[column].astype(float) * price_factor
            scaled_source["volume"] = scaled_source.volume.astype(float) * volume_factor
            scaled_bars = eligible_prices(scaled_source, symbol, mask[symbol]["exclude_price_dates"])
            scaled_upstream = event_frame_numeric(scaled_source.close, scaled_source.volume)
            check_invariant("scaled_observation_clock", symbol, scaled_bars.index.equals(bars.index),
                            dict(price_factor=price_factor, volume_factor=volume_factor))
            for mode in MODES:
                state, ledger = participation_frame(scaled_bars, scaled_upstream, mode)
                meta = dict(mode=mode, price_factor=price_factor, volume_factor=volume_factor)
                normalized_state, normalized_ledger = state.copy(), ledger.copy()
                normalized_state.loc[:, list(STATE_PRICES)] /= price_factor
                normalized_ledger.loc[:, list(LEDGER_PRICES)] /= price_factor
                normalized_ledger.loc[:, list(LEDGER_VOLUMES)] /= volume_factor
                check_frame("unit_state_all_columns_and_types", symbol, normalized_state, full[mode][0], **meta)
                check_frame("unit_state_discrete_exact", symbol, state[list(STATE_DISCRETE)],
                            full[mode][0][list(STATE_DISCRETE)], exact=True, **meta)
                check_frame("unit_ledger_all_columns_and_types", symbol, normalized_ledger, full[mode][1], **meta)
                check_frame("unit_ledger_discrete_exact", symbol, ledger[list(LEDGER_DISCRETE)],
                            full[mode][1][list(LEDGER_DISCRETE)], exact=True, **meta)
                check_frame("unit_actual_branch_predicates_exact", symbol,
                            branch_predicates(scaled_bars, scaled_upstream.reindex(scaled_bars.index), state),
                            branches[mode], exact=True, **meta)
        coverage.append(dict(symbol=symbol, source_rows=len(source), eligible_rows=len(bars),
                             input_sha256=sha256(BASE / "inputs" / f"{symbol}.csv"),
                             volume_events=len(full["volume"][1])))
        print(json.dumps(dict(symbol=symbol, checks=sum(x["symbol"] == symbol for x in checks),
                              failed=sum(not x["passed"] for x in checks if x["symbol"] == symbol))), flush=True)
    for name, digest in code_hash.items():
        check_invariant("code_unchanged_during_validation", name,
                        sha256(BASE / "code" / name) == digest)
    forbidden = ("campaign_engine", "run_study", "run_event_structure", "run_competing_state")
    assert not any(name in sys.modules for name in forbidden)
    record = dict(
        started_utc=started, completed_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        meaning="Independent full signal/ledger validation on fixed development inputs; no account or economic result",
        code_sha256=code_hash, input_manifest_sha256=sha256(BASE / "inputs/manifest.json"),
        series_count=len(frames), cases=len(cases), coverage=coverage, checks=checks,
        passed=sum(x["passed"] for x in checks), failed=sum(not x["passed"] for x in checks),
        scales=SCALES, tolerances=dict(atol=ATOL, rtol=RTOL),
        scope=dict(prefix="All columns and dtypes; exact state and causal ledger at three fixed cutoffs",
                   units="All state/ledger fields; discrete and actual branch predicates separately exact",
                   ledger="Future outcomes are reset to open; waiting age uses only prefix observations"),
        failures=failures, artifact_directory=str(artifact.relative_to(BASE)),
        account_runs=0, network_requests=0)
    attempt_path = validation / f"candidate-attempt{attempt}.json"
    attempt_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    if not record["failed"]:
        (validation / "candidate.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(dict(output=str(attempt_path), passed=record["passed"], failed=record["failed"])))
    return int(bool(record["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
