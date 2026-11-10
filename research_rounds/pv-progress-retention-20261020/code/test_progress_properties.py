"""Independent synthetic-only checks. Does not import a trajectory/account runner."""
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
EPS = 1e-12


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def model(path):
    spec = importlib.util.spec_from_file_location("independent_progress_check", path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded.progress_frame


def series(seed=4, n=550):
    rng = np.random.default_rng(seed)
    index = pd.date_range("2000-01-01", periods=n)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(.0002, .009, n))), index=index)
    volume = pd.Series(np.exp(rng.normal(5, .4, n)), index=index)
    return close, volume


def nested_path():
    prices = list(100 * np.exp(.006 * np.sin(np.arange(100) / 7)))
    for endpoint, n in [(140, 45), (122, 20), (134, 16), (124, 16),
                        (133, 16), (125, 16), (132, 16), (145, 24),
                        (105, 35), (153, 35)]:
        prices.extend(np.linspace(prices[-1], endpoint, n + 1)[1:])
    index = pd.date_range("2010-01-01", periods=len(prices))
    return pd.Series(prices, index=index), pd.Series(
        100 * np.exp(.3 * np.sin(np.arange(len(prices)) / 11)), index=index
    )


def assert_structure(frame):
    q = frame.loc[frame.valid]
    flips = parents = nested_flips = 0
    for k, (_, now) in enumerate(q.iterrows()):
        t = int(now.valid_idx)
        assert t == k
        if now.primary_direction:
            origin, extreme = int(now.primary_origin_idx), int(now.primary_extreme_idx)
            assert origin <= extreme <= t
            assert origin <= now.primary_origin_confirmed_idx <= t
            assert now.primary_extreme_known_idx == extreme
            # A developing current extreme is never declared confirmed in place.
            assert pd.isna(now.primary_extreme_confirmed_idx)
            run = q.log_price.iloc[origin:t + 1]
            wanted = run.max() if now.primary_direction == 1 else run.min()
            assert abs(wanted - now.primary_extreme) <= 2e-12
            if np.isfinite(now.retention):
                assert abs(now.retention + now.erosion - 1) < 1e-10
            if np.isfinite(now.recovery):
                assert -1e-10 <= now.recovery <= 1 + 1e-10
        else:
            assert now.stage == "unestablished"
        if now.primary_initialized:
            origin = int(now.primary_origin_idx)
            distance = now.primary_direction * (now.log_price - q.log_price.iloc[origin])
            assert distance >= np.sqrt(21) * q.sigma.iloc[origin] - 1e-12
            assert now.primary_origin_confirmed_idx == t
            assert now.primary_event == now.primary_direction
        if not k:
            continue
        before = q.iloc[k - 1]
        if before.primary_direction and not now.primary_flip:
            assert now.primary_origin_idx == before.primary_origin_idx
            assert now.primary_origin_confirmed_idx == before.primary_origin_confirmed_idx
        if now.primary_flip:
            flips += 1
            extreme = int(before.primary_extreme_idx)
            sigma_at_extreme = q.sigma.iloc[extreme]
            reverse = before.primary_direction * (
                before.primary_extreme - now.log_price
            )
            assert reverse >= np.sqrt(21) * sigma_at_extreme - 1e-12
            assert now.primary_direction == -before.primary_direction
            assert now.primary_origin_idx == extreme
            assert now.primary_origin_confirmed_idx == t
            assert now.confirmed_extreme_idx == extreme
            assert now.confirmed_extreme_confirmed_idx == t
            assert now.confirmed_extreme_date == before.primary_extreme_date
        else:
            assert pd.isna(now.confirmed_extreme_idx)
            if before.primary_direction:
                extreme = int(before.primary_extreme_idx)
                reverse = before.primary_direction * (
                    before.primary_extreme - now.log_price
                )
                assert reverse < np.sqrt(21) * q.sigma.iloc[extreme] + 1e-12
        if now.parent_direction:
            parents += 1
            assert now.parent_age == t - now.parent_created_idx
            assert now.parent_created_idx >= now.parent_extreme_idx
            assert now.parent_extreme_confirmed_idx == now.parent_created_idx
            assert now.parent_origin_confirmed_idx <= now.parent_created_idx
        if before.parent_direction:
            d = before.parent_direction
            above_extreme = d * (now.log_price - before.parent_extreme) > EPS
            below_origin = d * (now.log_price - before.parent_origin) < -EPS
            if not above_extreme and not below_origin:
                for field in ("parent_direction", "parent_origin_idx", "parent_extreme_idx",
                              "parent_created_idx", "parent_origin_confirmed_idx"):
                    assert now[field] == before[field], (t, field)
                if now.primary_flip:
                    nested_flips += 1
            else:
                assert now.parent_resolution_count >= 1
                assert now.parent_resolution_1_created_idx == before.parent_created_idx
                expected = "reclaimed" if above_extreme else "fully_eroded"
                assert now.parent_resolution_1 == expected
    return {"flips": flips, "parent_observations": parents,
            "nested_flips_with_parent_unchanged": nested_flips}


def tests(calc):
    checks = []
    total = {"flips": 0, "parent_observations": 0,
             "nested_flips_with_parent_unchanged": 0}
    for seed in range(10):
        c, v = series(seed)
        f = calc(c, v)
        counts = assert_structure(f)
        for name, count in counts.items():
            total[name] += count
    c, v = nested_path()
    f = calc(c, v)
    counts = assert_structure(f)
    assert counts["nested_flips_with_parent_unchanged"] >= 2, counts
    checks.append({"name": "anchors_extreme_scales_confirmation_parent_lifetimes",
                   "passed": True, "random_seeds": list(range(10)),
                   "random_totals": total, "nested_fixture": counts})

    index = pd.date_range("2005-01-01", periods=220)
    constant = calc(pd.Series(100., index=index), pd.Series(500., index=index))
    assert constant.primary_direction.eq(0).all()
    assert constant.primary_event.eq(0).all()
    assert constant.stage.eq("unestablished").all()
    monotonic = calc(pd.Series(100 * np.exp(.002 * np.arange(220)), index=index),
                     pd.Series(500., index=index))
    first = monotonic.loc[monotonic.primary_initialized].iloc[0]
    assert first.primary_direction == 1
    assert first.primary_origin_confirmed_idx == first.valid_idx
    assert monotonic.loc[:first.name].iloc[:-1].primary_direction.eq(0).all()
    # There are no alternating HH/HL pairs on a monotonic path.
    assert monotonic.primary_initialized.sum() == 1
    checks.append({"name": "flat_unknown_monotonic_initializes_without_HHHL",
                   "passed": True, "monotonic_confirmation_idx": int(first.valid_idx)})

    c, v = series()
    f = calc(c, v)
    cutoffs = [65, 85, 100, 151, 300, len(c) - 10]
    for n in cutoffs:
        pd.testing.assert_frame_equal(f.iloc[:n], calc(c.iloc[:n], v.iloc[:n]))
    branch = c.copy()
    branch.iloc[300:] *= np.exp(-np.arange(len(branch) - 300) * .01)
    pd.testing.assert_frame_equal(f.iloc[:300], calc(branch, v).iloc[:300])
    future_missing = c.copy()
    future_missing.iloc[410] = np.nan
    pd.testing.assert_frame_equal(f.iloc[:300], calc(future_missing, v).iloc[:300])
    checks.append({"name": "prefix_and_future_branch_dtype_causality",
                   "passed": True, "prefixes": cutoffs})

    missing_c, missing_v = c.copy(), v.copy()
    missing_c.iloc[[0, 1, 120, 121]] = np.nan
    missing_v.iloc[[177, 178]] = 0
    missing = calc(missing_c, missing_v)
    invalid = ~missing.valid
    assert not missing.loc[invalid, [
        "local_event", "primary_event", "primary_initialized",
        "primary_flip", "parent_created", "parent_resolution_count",
    ]].any().any()
    assert missing.loc[invalid, "confirmed_extreme_idx"].isna().all()
    assert missing.loc[invalid, "log_price"].isna().all()
    for n in [70, 120, 177, 300]:
        pd.testing.assert_frame_equal(
            missing.iloc[:n], calc(missing_c.iloc[:n], missing_v.iloc[:n])
        )
    assert_structure(missing)
    checks.append({"name": "missing_rows_no_events_or_confirmations",
                   "passed": True, "missing_rows": int(invalid.sum())})

    price_fields = [
        "primary_direction", "primary_event", "primary_initialized", "primary_flip",
        "primary_origin", "primary_origin_idx", "primary_origin_confirmed_idx",
        "primary_extreme", "primary_extreme_idx", "reaction_extreme_idx",
        "confirmed_extreme_idx", "confirmed_extreme_confirmed_idx",
        "parent_direction", "parent_origin_idx", "parent_extreme_idx",
        "parent_created_idx", "parent_resolution", "retention", "erosion",
        "recovery", "stage",
    ]
    altered_v = pd.Series(np.exp(np.random.default_rng(8).normal(4, 1, len(v))), index=v.index)
    altered = calc(c, altered_v)
    pd.testing.assert_frame_equal(f[price_fields], altered[price_fields])
    changed = int(f.volume_context.ne(altered.volume_context).sum())
    assert changed > 0
    checks.append({"name": "positive_volume_changes_only_descriptions",
                   "passed": True, "volume_context_changed_rows": changed})

    categorical = ["primary_direction", "primary_event", "primary_flip", "stage",
                   "parent_context", "parent_resolution", "volume_context"]
    invariant_numeric = ["retention", "erosion", "recovery", "drawdown_z",
                         "advance_activity", "erosion_activity", "recovery_activity"]
    for label, scaled_c, scaled_v in [
        ("price_units", c * 7, v), ("volume_units", c, v * 11),
    ]:
        scaled = calc(scaled_c, scaled_v)
        pd.testing.assert_frame_equal(f[categorical], scaled[categorical])
        np.testing.assert_allclose(
            f[invariant_numeric].to_numpy(), scaled[invariant_numeric].to_numpy(),
            rtol=1e-8, atol=1e-9, equal_nan=True,
        )
        checks.append({"name": label, "passed": True})
    checks.append({"name": "scope", "passed": True, "real_series": 0,
                   "account_calls": 0, "trajectory_runner_calls": 0})
    return checks


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--model", type=Path, default=BASE / "code/progress_model.py")
    p.add_argument("--output", type=Path, default=BASE / "mechanical-validation-synthetic.json")
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    dependencies = [args.model.resolve(), args.model.resolve().parent / "context_model.py"]
    hashes = {str(path): sha(path) for path in dependencies}
    report = {
        "created_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "synthetic mechanical properties only",
        "script_sha256": sha(__file__), "code_sha256": hashes,
        "real_series": 0, "account_calls": 0,
    }
    try:
        report["checks"] = tests(model(args.model))
        assert all(sha(path) == digest for path, digest in hashes.items())
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["failure"] = traceback.format_exc()
    with args.output.open("x") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    print(json.dumps({"passed": report["passed"],
                      "check_groups": len(report.get("checks", [])),
                      "output": str(args.output), "real_series": 0, "account_calls": 0}))
    if not report["passed"]:
        print(report["failure"])
        raise SystemExit(1)


if __name__ == "__main__":
    main()
