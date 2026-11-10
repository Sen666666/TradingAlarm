"""Independent mechanical checks for a context model; no accounts or runner.

Example:
    python test_context_properties.py --model context_model_v1.py \
        --output ../mechanical-validation-v1.json

The saved failed model is used only as a negative control for a concrete
candidate-lifetime defect. Its pandas boolean assignments are adapted in memory
so that the structural defect, rather than the earlier dtype crash, is tested.
No source or prior result is changed.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
from pathlib import Path
import traceback

import numpy as np
import pandas as pd


BASE = Path(__file__).resolve().parents[1]
DEFAULT_SAVED = (
    BASE.parents[1] / "TradingAlarm/research/results/"
    "pv-event-structure-20261020/HK09618-signals.csv"
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_model(path):
    spec = importlib.util.spec_from_file_location("mechanical_check_model", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.context_frame


def load_legacy_for_negative_control(path):
    source = Path(path).read_text()
    old_bool = "output.loc[invalid, field] = 0"
    old_ready = 'output.loc[before_first, ["regime", "ready"]] = 0'
    assert old_bool in source and old_ready in source, "unexpected legacy fixture"
    source = source.replace(
        old_bool, 'output.loc[invalid, field] = 0 if field == "event" else False'
    ).replace(
        old_ready,
        'output.loc[before_first, "regime"] = 0\n'
        '    output.loc[before_first, "ready"] = False',
    )
    namespace = {}
    exec(compile(source, str(path), "exec"), namespace)
    return namespace["context_frame"]


def synthetic(seed=1, n=500):
    rng = np.random.default_rng(seed)
    close = pd.Series(
        100 * np.exp(np.cumsum(rng.normal(0, .01, n))),
        index=pd.date_range("2000-01-01", periods=n),
    )
    volume = pd.Series(np.exp(rng.normal(5, .4, n)), index=close.index)
    return close, volume


def promotions(frame):
    """Check the actual observed path, independently of the update branches."""
    valid = frame.loc[frame.valid].copy()
    failures, count = [], 0
    for k in np.flatnonzero(valid.boundary_earned.to_numpy()):
        assert k > 0, "cannot earn a boundary before a previous observation"
        before, now = valid.iloc[k - 1], valid.iloc[k]
        stem = "up_candidate" if before.regime == 1 else "down_candidate"
        assert before.regime in (-1, 1)
        confirmed = int(before[f"{stem}_confirmed_idx"])
        assert confirmed < now.valid_idx
        observations = valid.loc[
            valid.valid_idx.gt(confirmed) & valid.valid_idx.le(now.valid_idx),
            "log_price",
        ]
        if before.regime == 1:
            boundary = float(before.up_candidate_low)
            crossed = observations.le(boundary)
            earned = float(now.structure_floor)
            reference_broken = now.log_price > before.up_candidate_high
        else:
            boundary = float(before.down_candidate_high)
            crossed = observations.ge(boundary)
            earned = float(now.structure_ceiling)
            reference_broken = now.log_price < before.down_candidate_low
        assert np.isclose(earned, boundary, rtol=0, atol=1e-12)
        assert reference_broken, "promotion without reference-price break"
        count += 1
        if crossed.any():
            failures.append({
                "valid_idx": int(now.valid_idx),
                "candidate_confirmed_idx": confirmed,
                "regime": int(before.regime),
                "boundary": boundary,
                "first_cross_date": str(crossed.loc[crossed].index[0]),
            })
    return count, failures


def assert_established_boundaries(frame):
    valid = frame.loc[frame.valid]
    up = valid.loc[valid.regime.eq(1)]
    down = valid.loc[valid.regime.eq(-1)]
    assert up.log_price.gt(up.structure_floor).all()
    assert down.log_price.lt(down.structure_ceiling).all()


def assert_prefix(calc, close, volume, cutoffs):
    full = calc(close, volume)
    used = []
    for cutoff in sorted(set(cutoffs)):
        if 0 < cutoff < len(close):
            short = calc(close.iloc[:cutoff], volume.iloc[:cutoff])
            # Keep strict dtype and value checks; future missing rows must not
            # change the dtype or diagnostics of an earlier valid prefix.
            pd.testing.assert_frame_equal(full.iloc[:cutoff], short)
            used.append(cutoff)
    return used


def run_checks(calc, saved_path, legacy_path):
    checks = []
    close, volume = synthetic()
    current = calc(close, volume)
    legacy = load_legacy_for_negative_control(legacy_path)(close, volume)
    _, legacy_failures = promotions(legacy)
    assert any(x["valid_idx"] == 122 for x in legacy_failures)
    count, failures = promotions(current)
    assert not failures, failures
    checks.append({
        "name": "known_invalidated_candidate_negative_control",
        "passed": True,
        "legacy_expected_failures": legacy_failures,
        "fixed_model_promotions": count,
        "fixed_model_invalid_promotions": 0,
        "legacy_in_memory_adaptation": "boolean assignment dtype only",
    })

    total_promotions = 0
    for seed in range(12):
        c, v = synthetic(seed)
        f = calc(c, v)
        number, failures = promotions(f)
        assert not failures, {"seed": seed, "violations": failures}
        assert_established_boundaries(f)
        total_promotions += number
    assert total_promotions > 0, "vacuous boundary test"
    checks.append({
        "name": "candidate_survival_and_valid_boundaries",
        "passed": True, "synthetic_seeds": list(range(12)),
        "checked_promotions": total_promotions,
    })

    skeleton = [
        "regime", "developing_direction", "event", "broken", "boundary_earned",
        "structure_floor", "structure_ceiling", "pivot", "pivot_idx",
        "confirmation", "state_reason",
    ]
    changed_volume = pd.Series(
        np.exp(np.random.default_rng(912).normal(4, 1, len(volume))),
        index=volume.index,
    )
    rearranged = calc(close, changed_volume)
    pd.testing.assert_frame_equal(current[skeleton], rearranged[skeleton])
    checks.append({
        "name": "positive_volume_changes_quality_not_price_skeleton",
        "passed": True,
        "phase_changed_rows": int(current.phase.ne(rearranged.phase).sum()),
        "skeleton_fields": skeleton,
    })

    log_fields = [
        "log_price", "developing_extreme", "pivot", "structure_floor",
        "structure_ceiling", "broken_boundary",
        "last_high", "previous_high", "last_low", "previous_low",
        "up_candidate_low", "up_candidate_high",
        "down_candidate_low", "down_candidate_high",
    ]
    invariant = [
        "regime", "developing_direction", "phase", "price_phase", "event",
        "broken", "boundary_earned", "state_reason", "valid", "ready",
    ]
    numeric_invariant = [
        "sigma", "volume_ratio", "confirmation", "e", "s", "retrace",
        "oneil_inspired_score", "percent_b", "bandwidth",
    ]
    for name, c, v, log_shift in [
        ("price_unit_scale", close * 1e5, volume, np.log(1e5)),
        ("volume_unit_scale", close, volume * 1e7, 0.),
    ]:
        scaled = calc(c, v)
        pd.testing.assert_frame_equal(current[invariant], scaled[invariant])
        np.testing.assert_allclose(
            current[numeric_invariant].to_numpy(dtype=float),
            scaled[numeric_invariant].to_numpy(dtype=float),
            rtol=1e-8, atol=1e-9, equal_nan=True,
        )
        np.testing.assert_allclose(
            current[log_fields].to_numpy(dtype=float),
            scaled[log_fields].to_numpy(dtype=float) - log_shift,
            rtol=1e-9, atol=1e-9, equal_nan=True,
        )
        checks.append({"name": name, "passed": True})

    cutoffs = assert_prefix(
        calc, close, volume, [64, 65, 107, 121, 122, 123, 250, 499]
    )
    checks.append({"name": "synthetic_prefix_causality", "passed": True,
                   "cutoffs": cutoffs})

    missing_close, missing_volume = close.copy(), volume.copy()
    missing_close.iloc[[0, 1, 2, 122, 176]] = np.nan
    missing_volume.iloc[[25, 177]] = 0.
    missing = calc(missing_close, missing_volume)
    assert not missing.loc[~missing.valid, ["event", "broken", "boundary_earned"]].any().any()
    assert missing.loc[~missing.valid, "pivot"].isna().all()
    assert missing.loc[~missing.valid, "log_price"].isna().all()
    cutoffs = assert_prefix(calc, missing_close, missing_volume, [90, 122, 176, 280])
    checks.append({"name": "missing_rows_emit_no_new_events", "passed": True,
                   "invalid_rows": int((~missing.valid).sum()),
                   "cutoffs": cutoffs})

    future_missing_close = close.copy()
    future_missing_close.iloc[400] = np.nan
    future_missing = calc(future_missing_close, volume)
    pure_prefix = calc(close.iloc[:300], volume.iloc[:300])
    pd.testing.assert_frame_equal(future_missing.iloc[:300], pure_prefix)
    checks.append({"name": "future_missing_cannot_change_prefix_dtype_or_values",
                   "passed": True, "prefix_rows": 300, "missing_row": 400})

    branch = close.copy()
    branch.iloc[300:] *= np.exp(-np.arange(len(close) - 300) * .01)
    other = calc(branch, volume)
    pd.testing.assert_frame_equal(current.iloc[:300], other.iloc[:300])
    checks.append({"name": "same_prefix_diverging_future", "passed": True,
                   "prefix_rows": 300})

    saved = pd.read_csv(saved_path, index_col="date", parse_dates=True)
    saved_frame = calc(saved.close, saved.volume)
    number, failures = promotions(saved_frame)
    assert not failures, failures
    assert_established_boundaries(saved_frame)
    cutoffs = assert_prefix(
        calc, saved.close, saved.volume,
        [100, len(saved) // 2, len(saved) - 17],
    )
    checks.append({"name": "saved_market_series_properties", "passed": True,
                   "path": str(saved_path), "rows": len(saved),
                   "checked_promotions": number, "cutoffs": cutoffs})
    return checks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=Path, default=BASE / "code/context_model.py")
    parser.add_argument("--output", type=Path, default=BASE / "mechanical-validation.json")
    parser.add_argument("--saved-source", type=Path, default=DEFAULT_SAVED)
    parser.add_argument(
        "--legacy-model", type=Path,
        default=BASE / "v0-attempt1-failed/context_model.py",
    )
    args = parser.parse_args()
    paths = [args.model.resolve(), args.saved_source.resolve(), args.legacy_model.resolve()]
    if args.output.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence: {args.output}")
    hashes = {str(path): sha(path) for path in paths}
    report = {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "purpose": "mechanical properties only; no accounts or profitability",
        "model": str(paths[0]), "script_sha256": sha(__file__),
        "input_sha256": hashes, "account_calls": 0,
    }
    try:
        report["checks"] = run_checks(load_model(paths[0]), paths[1], paths[2])
        assert all(sha(path) == digest for path, digest in hashes.items())
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["failure"] = traceback.format_exc()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)
    print(json.dumps({
        "passed": report["passed"], "output": str(args.output.resolve()),
        "check_groups": len(report.get("checks", [])), "account_calls": 0,
    }))
    if not report["passed"]:
        print(report["failure"])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
