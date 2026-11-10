"""Finite, offline B5 contract checks. Frozen legacy functions are test oracles.

Prepare immutable fixtures before executing B5, then use a fresh output for each
attempt. Injected-event fixtures are policy units, never native-event evidence.
No market files, account engine, downloads, parameter sweep, or allclose checks.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import sys
import traceback

import numpy as np
import pandas as pd

from serialization import read_frame, write_frame


BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]
VALIDATION = BASE / "validation"
LEGACY = ROOT / "research_rounds/pv-participation-response-20261020/code"
B4_SOURCE = ROOT / "research_rounds/pv-strength-b4-20261025/code/model.py"
EVENT_COLUMNS = [
    "confirmation", "leg_direction", "developing_extreme", "confirmed_pivot",
    "event", "pivot_age", "developing_extreme_price", "confirmed_pivot_price",
    "confirmed_pivot_date", "developing_extreme_date",
]
PRICE_COLUMNS = ["open", "high", "low", "close"]
REQUIRED_FACTS = PRICE_COLUMNS + [
    "volume", "segment_id", "valid_price_observation", "valid_strength_observation",
    "price_observation", "ready", "previous_close", "volume_baseline",
    "volume_ratio", "declined", "high_effort", "decline_candidate",
    "candidate_lower", "candidate_reclaim",
] + EVENT_COLUMNS


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def normalized(obj):
    if isinstance(obj, dict):
        return {str(k): normalized(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [normalized(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        return float(obj) if math.isfinite(obj) else None
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if obj is pd.NA or obj is pd.NaT:
        return None
    if isinstance(obj, (pd.Timestamp, dt.datetime)):
        return obj.isoformat()
    return obj


def write_json(path, obj):
    with Path(path).open("x") as handle:
        json.dump(normalized(obj), handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def exact(left, right, dtype=True):
    pd.testing.assert_frame_equal(left, right, check_exact=True, check_dtype=dtype,
                                  check_freq=False, check_like=False)


def canonical_old_state(frame):
    """Declared adapter schema normalization, never numeric value rounding."""
    result = frame.copy()
    for column in result:
        if str(result[column].dtype) == "int64":
            result[column] = result[column].astype("Int64")
    return result


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def make_bars(close, volume=100., segment="s1", start="2020-01-01"):
    c = np.asarray(close, dtype=float)
    v = np.full(len(c), volume, dtype=float) if np.isscalar(volume) else np.asarray(volume, float)
    o = np.r_[c[0], c[:-1]]
    return pd.DataFrame({"open": o, "high": np.maximum(o, c) + 1.,
                         "low": np.minimum(o, c) - 1., "close": c, "volume": v,
                         "segment_id": segment, "valid_price_observation": True,
                         "valid_strength_observation": np.isfinite(v) & (v > 0)},
                        index=pd.bdate_range(start, periods=len(c), name="date"))


def witness(lower=98.):
    f = make_bars([100., 102.] * 32 + [100., 103., 96.])
    f.loc[f.index[64], ["low", "volume"]] = [lower, 200.]
    return f


def fixture_set():
    """Exactly 20 deterministic native-event paths, fixed without model calls."""
    a, b = witness(98.), witness(94.)
    native = {"same_cv_low98": a, "same_cv_low94": b,
              "warmup_63": a.iloc[:63].copy(), "warmup_64": a.iloc[:64].copy(),
              "warmup_65": a.iloc[:65].copy()}
    for name, position, close in (("missing_volume_reclaim", 65, 103.),
                                  ("missing_volume_reject", 65, 97.),
                                  ("missing_volume_exit", 66, 96.)):
        f = a.copy(deep=True)
        f.loc[f.index[position], ["close", "volume", "valid_strength_observation"]] = [close, np.nan, False]
        f.loc[f.index[position], "low"] = min(f.iloc[position].low, close - 1)
        native[name] = f
    native["stationary"] = make_bars([100.] * 90)
    native["abrupt_crash"] = make_bars([100.] * 65 + [103., 104., 105., 80., 78., 79., 81.])
    native["v_recovery"] = make_bars([100., 102.] * 32 + [100., 94., 90., 85., 90., 96., 103., 106.],
                                     [100.] * 64 + [100., 200., 300., 400., 100., 100., 100., 100.])
    for name, volume in (("low_volume_decline", 100.), ("high_volume_decline", 400.)):
        f = a.copy(deep=True)
        f.loc[f.index[64], "volume"] = volume
        native[name] = f
    f = pd.concat([a, b.assign(segment_id="s2")], ignore_index=True)
    f.index = pd.bdate_range("2020-01-01", periods=len(f), name="date")
    native["two_segments"] = f
    # Invalid source rows cannot advance either observation clock or policy.
    f = pd.concat([a.iloc[:65], a.iloc[[64]], a.iloc[65:]], ignore_index=True)
    f.index = pd.bdate_range("2020-01-01", periods=len(f), name="date")
    f.loc[f.index[65], PRICE_COLUMNS + ["volume"]] = [np.nan, np.inf, -1., 0., np.nan]
    f.loc[f.index[65], ["valid_price_observation", "valid_strength_observation"]] = False
    native["invalid_price_gap"] = f
    f = make_bars([100., 102.] * 32 + [100.] + [101.] * 180 + [103.])
    f.loc[f.index[64], ["volume", "low"]] = [200., 94.]
    native["persistent_memory"] = f
    f = make_bars([100., 102.] * 32 + [100., np.nextafter(102., np.inf),
                                                   np.nextafter(98., 0.), 103.])
    f.loc[f.index[64], ["volume", "low"]] = [200., 98.]
    native["binary64_boundary_ties"] = f
    f = make_bars([100., 102.] * 45)
    for i, v in ((20, np.nan), (40, 0.), (60, np.inf), (70, np.nan)):
        f.loc[f.index[i], ["volume", "valid_strength_observation"]] = [v, False]
    native["bad_volume_windows"] = f
    f = a.copy(deep=True)
    f.loc[f.index[[3, 20, 64, 65]], "valid_strength_observation"] = False
    native["strength_mask_only"] = f
    native["no_valid_volume"] = make_bars([100., 102.] * 35, volume=np.nan)
    assert len(native) == 20
    return native


def bar(close, volume=100., low=None):
    return {"open": close, "high": close + 1., "low": close - 1. if low is None else low,
            "close": close, "volume": volume}


def policy_fixture(tail, confirmations=None):
    warm = 26
    f = pd.DataFrame([bar(100.) for _ in range(warm)] + tail,
                     index=pd.bdate_range("2020-01-01", periods=warm + len(tail), name="date"))
    f["segment_id"] = "policy_unit"
    f["valid_price_observation"] = True
    f["valid_strength_observation"] = np.isfinite(f.volume) & f.volume.gt(0)
    e = pd.DataFrame({"event": 0., "leg_direction": -1., "confirmed_pivot_price": np.nan}, index=f.index)
    for offset, pivot in (confirmations or {}).items():
        e.loc[e.index[warm + offset], ["event", "confirmed_pivot_price"]] = [1., pivot]
    return f, e


def policy_fixture_set():
    return {
        "original_priority_no_response": policy_fixture([bar(96, 300, 94), bar(99)], {1: 95}),
        "original_priority_reclaim": policy_fixture([bar(96, 300, 94), bar(101)], {1: 97}),
        "original_on_memory_rejection": policy_fixture([bar(96, 300, 94), bar(93, 300, 92)], {1: 90}),
        "exit_day_no_reentry": policy_fixture([bar(100), bar(90, 300, 89), bar(101)], {0: 90, 1: 85}),
        "support_ratchet_missing_volume_exit": policy_fixture([bar(100), bar(101), bar(101), bar(94, np.nan)],
                                                              {0: 90, 1: 95, 2: 94}),
        "memory_rejected_recreated": policy_fixture([bar(96, 300, 94), bar(93, 300, 92), bar(97)]),
        "unresolved_not_replaced": policy_fixture([bar(96, 300, 94), bar(95, 400, 94.5), bar(99), bar(101)]),
        "long_memory": policy_fixture([bar(96, 300, 94)] + [bar(98)] * 180 + [bar(99)], {181: 95}),
        "tie_boundaries": policy_fixture([bar(96, 300, 94), bar(np.nextafter(100., np.inf)),
                                           bar(np.nextafter(94., 0.)), bar(100.1)]),
        "missing_volume_reclaim": policy_fixture([bar(96, 300, 94), bar(101, np.nan)]),
        "missing_volume_reject": policy_fixture([bar(96, 300, 94), bar(93, np.nan)]),
        "volume_threshold_inclusive": policy_fixture([bar(96, 200, 94), bar(101)]),
    }


def safe_output(path):
    path = Path(path).resolve()
    if path.parent != VALIDATION or not path.name.startswith("technical-"):
        raise ValueError("Fresh technical-* directory directly under B5 validation required")
    path.mkdir(parents=True, exist_ok=False)
    return path


def prepare(path):
    out = safe_output(path)
    native, injected = fixture_set(), policy_fixture_set()
    descriptions = []
    for name, frame in native.items():
        frame.to_parquet(out / f"native-{name}.parquet")
        descriptions.append({"name": name, "kind": "native_events_end_to_end", "rows": len(frame),
                             "prefix_lengths": sorted({1, min(21, len(frame)), min(63, len(frame)),
                                                        min(64, len(frame)), min(65, len(frame)),
                                                        len(frame) - 1, len(frame)})})
    for name, (frame, events) in injected.items():
        frame.to_parquet(out / f"unit-{name}-bars.parquet")
        events.to_parquet(out / f"unit-{name}-events.parquet")
        descriptions.append({"name": name, "kind": "injected_policy_unit_only", "rows": len(frame),
                             "prefix_lengths": sorted({1, 21, 26, 27, len(frame) - 1, len(frame)})})
    protocol = {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "scope": "Finite synthetic technical compatibility only; no accounts or market data",
        "native_paths": 20, "injected_policy_paths": 12, "fixtures": descriptions,
        "comparisons": "check_exact=True for every field, dtype, missingness and order; no allclose",
        "oracle": "Frozen numeric.event_frame_numeric and participation.participation_frame(mode='volume'), per source segment on valid price rows; original V retained independently of strength mask",
        "no_valid_volume_boundary": "Old numeric raises for no valid C/V; B5 is defined unknown/not-ready. This boundary is not an old-function identity claim.",
        "invalid_rows": "Unknown output rows, no price/event/strength clock advancement; policy state held internally",
        "segment_ledger": "Each segment independent; unresolved memory remains open in that segment, never fabricated as rejected",
        "serialization": "Parquet retains binary64 and extension dtypes; reload evidence without model recomputation",
        "prefix_ledger": "Project future resolutions to open as of each segment's available valid-price count",
        "enhancements": "True must be rejected; no enhancement mechanism implemented",
        "accounts": 0, "downloads": 0, "parameter_sweeps": 0,
        "fixture_generator_sha256": sha(__file__),
    }
    write_json(out / "protocol.json", protocol)
    write_json(out / "manifest.json", {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()})
    print(json.dumps({"prepared": str(out), "native_paths": 20, "policy_unit_paths": 12}))


def native_events(frame, numeric):
    good = frame.loc[frame.valid_price_observation]
    cv = np.isfinite(good[["close", "volume"]]).all(axis=1) & good[["close", "volume"]].gt(0).all(axis=1)
    if not cv.any():
        return None
    return numeric.event_frame_numeric(good.close, good.volume, joint=True, event_exit=False)


def test_facts(frame, events, numeric):
    """Independent fact construction for explicitly injected policy unit events."""
    e = frame.copy(deep=True)
    e["price_observation"] = np.arange(len(e), dtype=float)
    for col in EVENT_COLUMNS:
        e[col] = events[col] if col in events else np.nan
    v = frame.volume.where(np.isfinite(frame.volume) & frame.volume.gt(0))
    e["volume_baseline"] = v.shift().rolling(21, min_periods=21).median()
    e["volume_ratio"] = v / e.volume_baseline
    e["previous_close"] = e.close.shift()
    e["ready"] = events.leg_direction.notna().cummax()
    e["declined"] = [bool(pd.notna(p) and numeric.compare(c, p) < 0)
                       for c, p in zip(e.close, e.previous_close)]
    e["high_effort"] = [bool(math.isfinite(q) and numeric.compare(q, 2.) >= 0) for q in e.volume_ratio]
    e["decline_candidate"] = e.ready & e.declined & e.high_effort
    e["candidate_lower"] = e.low.where(e.decline_candidate)
    e["candidate_reclaim"] = e.previous_close.where(e.decline_candidate)
    return e


def ledger_asof(full, frame):
    """All columns and dtypes preserved; each segment has its own price clock."""
    pieces = []
    for segment, group in frame.groupby("segment_id", sort=False):
        good = group.loc[group.valid_price_observation]
        if good.empty:
            continue
        result = full.loc[full.segment_id.eq(segment) & full.created_observation.lt(len(good))].copy()
        future = result.resolved_date.isna() | result.resolved_date.gt(str(good.index[-1].date()))
        result.loc[future, "resolved_date"] = pd.NA
        result.loc[future, "outcome"] = "open"
        for col in ("response", "independent_entry", "original_entry_same_day"):
            result.loc[future, col] = 0
        result.loc[future, "resolution_volume_ratio"] = np.nan
        result.loc[future, "waiting_observations"] = len(good) - 1 - result.loc[future, "created_observation"]
        pieces.append(result)
    return pd.concat(pieces, ignore_index=True) if pieces else full.iloc[:0].copy()


class Checks:
    def __init__(self):
        self.records = []

    def run(self, name, function):
        try:
            function()
        except Exception:
            self.records.append({"check": name, "passed": False, "error": traceback.format_exc()})
        else:
            self.records.append({"check": name, "passed": True})


def assert_raises(function, types=(ValueError, TypeError, NotImplementedError)):
    try:
        function()
    except types:
        return
    raise AssertionError("Expected explicit contract rejection")


def run_suite(fixtures, output, addendum=None):
    fixture_dir, out = Path(fixtures).resolve(), safe_output(output)
    manifest = json.loads((fixture_dir / "manifest.json").read_text())
    for name, digest in manifest.items():
        assert sha(fixture_dir / name) == digest, f"Frozen fixture changed: {name}"
    protocol = json.loads((fixture_dir / "protocol.json").read_text())
    additions = None
    if addendum is not None:
        addition_dir = Path(addendum).resolve()
        addition_manifest = json.loads((addition_dir / "manifest.json").read_text())
        for name, digest in addition_manifest.items():
            assert sha(addition_dir / name) == digest, f"Frozen addendum changed: {name}"
        additions = json.loads((addition_dir / "protocol.json").read_text())
    sources = list((BASE / "code").glob("*.py")) + [LEGACY / "numeric.py", LEGACY / "participation.py", B4_SOURCE] + list(Path(__file__).parent.glob("*.py"))
    before = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    write_json(out / "source-hashes-before.json", before)
    for source in sources:
        if source.parent == BASE / "code":
            (out / f"source-{source.name}").write_bytes(source.read_bytes())
        elif source.parent == Path(__file__).parent:
            (out / f"validator-{source.name}").write_bytes(source.read_bytes())
    checks = Checks()
    products = {}
    fatal = None
    try:
        for freeze_name in ("freeze.json", "freeze-validation-v2.json"):
            frozen = json.loads((BASE / freeze_name).read_text())["sha256"]
            changed = [name for name, digest in frozen.items() if sha(ROOT / name) != digest]
            assert not changed, f"Frozen files changed: {changed}"
            checks.records.append({"check": "freeze_identity/" + freeze_name, "passed": True,
                                   "files": len(frozen)})
        numeric = load_module("numeric", LEGACY / "numeric.py")
        old = load_module("b5_test_oracle_participation", LEGACY / "participation.py")
        b4 = load_module("b5_test_oracle_b4", B4_SOURCE)
        sys.path.insert(0, str(BASE / "code"))
        api = load_module("b5_test_api", BASE / "code/api.py")
        evidence_module = sys.modules.get("evidence") or load_module("evidence", BASE / "code/evidence.py")
        policy_module = sys.modules.get("policy") or load_module("policy", BASE / "code/policy.py")

        def native_oracle_check(frame, result):
            evidence, state, ledger = result["evidence"], result["state"], result["ledger"]
            assert all(col in evidence for col in REQUIRED_FACTS)
            assert not any(c.startswith("e0_") for c in evidence)
            assert not {"target", "entered", "exited", "floor", "pending"}.intersection(evidence.columns)
            for segment, group in frame.groupby("segment_id", sort=False):
                good = group.loc[group.valid_price_observation]
                events = native_events(group, numeric)
                if events is None:
                    assert evidence.loc[group.index, "ready"].fillna(False).eq(False).all()
                    assert evidence.loc[group.index, "event"].fillna(0).eq(0).all()
                    continue
                exact(evidence.loc[good.index, EVENT_COLUMNS], events[EVENT_COLUMNS])
                expected, expected_ledger = old.participation_frame(good, events, mode="volume")
                actual = state.loc[good.index, expected.columns]
                exact(actual, canonical_old_state(expected))
                actual_ledger = ledger.loc[ledger.segment_id.eq(segment), expected_ledger.columns].reset_index(drop=True)
                exact(actual_ledger, expected_ledger)
                facts = test_facts(good, events, numeric)
                for column in ("previous_close", "volume_baseline", "volume_ratio"):
                    exact(evidence.loc[good.index, [column]], facts[[column]])
                for column in ("ready", "declined", "high_effort", "decline_candidate"):
                    assert evidence.loc[good.index, column].tolist() == facts[column].tolist(), column
                for column in ("candidate_lower", "candidate_reclaim"):
                    exact(evidence.loc[good.index, [column]], facts[[column]])

        def strength_identity(frame, result):
            expected, journal = b4.strength_frame(frame, joint=True)
            columns = ["strength_" + c for c in expected]
            actual = result["evidence"][columns].rename(columns=lambda c: c[len("strength_"):])
            exact(actual, expected)
            assert normalized(result["journal"]["strength"]) == normalized(journal)

        def strength_independence(result):
            e = result["evidence"]
            original, attrs = e.copy(deep=True), normalized(e.attrs)
            columns = [c for c in e if c.startswith("strength_")]
            assert columns
            reduced = e.drop(columns=columns)
            mutated = e.copy(deep=True)
            for column in columns:
                mutated[column] = "arbitrary_strength_payload"
            for candidate in (reduced, mutated):
                state, ledger = policy_module.e0_policy(candidate, enhancements=False)
                exact(state, result["state"])
                exact(ledger, result["ledger"])
            exact(e, original)
            assert normalized(e.attrs) == attrs

        def prefix_check(name, frame, full, lengths):
            for n in lengths:
                truncated = frame.iloc[:n]
                prefix = api.run_b5(truncated, enhancements=False)
                exact(prefix["evidence"], full["evidence"].iloc[:n])
                exact(prefix["state"], full["state"].iloc[:n])
                exact(prefix["ledger"], ledger_asof(full["ledger"], truncated))
                last_date = str(truncated.index[-1].date())
                for kind in ("events", "strength"):
                    expected = [j for j in full["journal"][kind] if j["date"] <= last_date]
                    assert normalized(prefix["journal"][kind]) == normalized(expected), (name, n, kind)

        for spec in protocol["fixtures"]:
            name = spec["name"]
            if spec["kind"] == "native_events_end_to_end":
                frame = pd.read_parquet(fixture_dir / f"native-{name}.parquet")
                def compute(name=name, frame=frame):
                    original, attrs = frame.copy(deep=True), normalized(frame.attrs)
                    result = api.run_b5(frame, enhancements=False)
                    assert set(result) == {"evidence", "journal", "state", "ledger"}
                    assert set(result["journal"]) == {"events", "strength"}
                    exact(frame, original)
                    assert normalized(frame.attrs) == attrs
                    products[name] = result
                    for key in ("evidence", "state", "ledger"):
                        write_frame(result[key], out / f"{name}-{key}.parquet")
                    write_json(out / f"{name}-journal.json", result["journal"])
                checks.run(f"native/{name}/compute_and_input_immutability", compute)
                if name not in products:
                    continue
                result = products[name]
                checks.run(f"native/{name}/legacy_exact", lambda f=frame, r=result: native_oracle_check(f, r))
                checks.run(f"native/{name}/b4_exact", lambda f=frame, r=result: strength_identity(f, r))
                checks.run(f"native/{name}/strength_independent", lambda r=result: strength_independence(r))
                def reload_check(name=name, result=result):
                    reload = read_frame(out / f"{name}-evidence.parquet")
                    exact(reload, result["evidence"])
                    state, ledger = policy_module.e0_policy(reload, enhancements=False)
                    exact(state, result["state"])
                    exact(ledger, result["ledger"])
                checks.run(f"native/{name}/serialized_policy_replay", reload_check)
                checks.run(f"native/{name}/physical_prefix_all_fields_journals_ledger",
                           lambda n=name, f=frame, r=result, p=spec["prefix_lengths"]: prefix_check(n, f, r, p))
            else:
                frame = pd.read_parquet(fixture_dir / f"unit-{name}-bars.parquet")
                events = pd.read_parquet(fixture_dir / f"unit-{name}-events.parquet")
                def unit(name=name, frame=frame, events=events, lengths=spec["prefix_lengths"]):
                    e = test_facts(frame, events, numeric)
                    before_e = e.copy(deep=True)
                    state, ledger = policy_module.e0_policy(e, enhancements=False)
                    expected, expected_ledger = old.participation_frame(frame, events, mode="volume")
                    exact(state.drop(columns="segment_id"), canonical_old_state(expected))
                    exact(ledger.drop(columns="segment_id"), expected_ledger)
                    exact(e, before_e)
                    for n in lengths:
                        ps, pl = policy_module.e0_policy(e.iloc[:n], enhancements=False)
                        exact(ps, state.iloc[:n])
                        exact(pl, ledger_asof(ledger, frame.iloc[:n]))
                    state.to_parquet(out / f"unit-{name}-state.parquet")
                    ledger.to_parquet(out / f"unit-{name}-ledger.parquet")
                    products["unit-" + name] = {"state": state, "ledger": ledger}
                checks.run(f"injected_policy_unit/{name}/exact_and_prefix", unit)

        if additions is not None:
            for spec in additions["reset_fixtures"]:
                name = spec["name"]
                frame = pd.read_parquet(addition_dir / f"{name}.parquet")
                def reset_check(name=name, frame=frame, spec=spec):
                    result = api.run_b5(frame, enhancements=False)
                    native_oracle_check(frame, result)
                    strength_identity(frame, result)
                    prefix_check(name, frame, result, spec["prefix_lengths"])
                    boundary = spec["first_segment_rows"]
                    assert result["state"].iloc[boundary].target == 0
                    assert result["state"].iloc[boundary].pending == 0
                    assert result["evidence"].iloc[boundary].price_observation == 0
                    assert result["evidence"].iloc[boundary].ready == 0
                    if name == "reset_pending":
                        assert result["state"].iloc[boundary - 1].pending == 1
                        old_memory = result["ledger"].loc[result["ledger"].segment_id.eq("s1")]
                        assert old_memory.iloc[0].outcome == "open"
                        assert pd.isna(old_memory.iloc[0].resolved_date)
                    else:
                        assert result["state"].iloc[boundary - 1].target == 1
                    for key in ("evidence", "state", "ledger"):
                        write_frame(result[key], out / f"{name}-{key}.parquet")
                    write_json(out / f"{name}-journal.json", result["journal"])
                checks.run(f"derived_boundary/{name}/reset_exact_and_prefix", reset_check)

        def witness_assertions():
            a, b = products["same_cv_low98"], products["same_cv_low94"]
            for result, lower in ((a, 98.), (b, 94.)):
                s = result["state"]
                assert s.iloc[64].created == 1 and s.iloc[64].pending_lower == lower
                assert s.iloc[65].independent_entry == 1 and s.iloc[65].floor == lower
                assert result["evidence"].iloc[65].event == 0
                assert 0 < result["evidence"].iloc[65].confirmation < 1
            assert a["state"].iloc[66].exited == 1 and b["state"].iloc[66].exited == 0
            cols = [c for c in a["evidence"] if c.startswith("strength_")]
            exact(a["evidence"][cols], b["evidence"][cols])
            assert normalized(a["journal"]["strength"]) == normalized(b["journal"]["strength"])
        checks.run("semantic/67_observation_information_loss_recovered", witness_assertions)

        def key_semantics():
            assert not products["warmup_64"]["evidence"].ready.any()
            assert products["warmup_65"]["evidence"].iloc[64].ready
            assert products["missing_volume_reclaim"]["state"].iloc[65].independent_entry == 1
            assert products["missing_volume_reject"]["state"].iloc[65].response == -1
            assert products["missing_volume_exit"]["state"].iloc[66].exited == 1
            assert products["low_volume_decline"]["state"].created.sum() == 0
            assert products["high_volume_decline"]["state"].iloc[64].created == 1
            exact(products["strength_mask_only"]["state"], products["same_cv_low98"]["state"])
            exact(products["strength_mask_only"]["ledger"], products["same_cv_low98"]["ledger"])
            masked = products["strength_mask_only"]["evidence"]
            original = products["same_cv_low98"]["evidence"]
            columns = [c for c in original if not c.startswith("strength_") and c != "valid_strength_observation"]
            exact(masked[columns], original[columns])
            invalid = products["invalid_price_gap"]["state"].iloc[65]
            assert invalid.drop(labels="segment_id").isna().all()
            assert products["persistent_memory"]["state"].iloc[64:245].pending.eq(1).all()
            expected = {"original_priority_no_response": ("base_confirmed", 95.),
                        "original_priority_reclaim": ("base_confirmed", 97.),
                        "original_on_memory_rejection": ("rejected", 90.)}
            for name, (outcome, floor) in expected.items():
                r = products["unit-" + name]
                assert r["ledger"].iloc[0].outcome == outcome and r["state"].iloc[-1].floor == floor
            s = products["unit-exit_day_no_reentry"]["state"].iloc[26:]
            assert s.target.tolist() == [1, 0, 1] and s.entered.tolist() == [1, 0, 1]
            s = products["unit-support_ratchet_missing_volume_exit"]["state"].iloc[26:]
            assert s.floor.tolist() == [90., 95., 95., 95.]
            r = products["unit-memory_rejected_recreated"]
            assert r["state"].iloc[27].ended_id == 1 and r["state"].iloc[27].pending_id == 2
            assert r["ledger"].outcome.tolist() == ["rejected", "reclaimed"]
            s = products["unit-tie_boundaries"]["state"].iloc[26:]
            assert s.response.tolist() == [0, 0, 0, 1]
            assert products["unit-long_memory"]["ledger"].iloc[0].waiting_observations == 181
        checks.run("semantic/warmup_masks_memory_priority_ties_and_ratchet", key_semantics)

        good = pd.read_parquet(fixture_dir / "native-same_cv_low98.parquet")
        checks.run("contract/enhancements_api_rejected", lambda: assert_raises(lambda: api.run_b5(good, enhancements=True), (NotImplementedError,)))
        checks.run("contract/enhancements_policy_rejected", lambda: assert_raises(lambda: policy_module.e0_policy(products["same_cv_low98"]["evidence"], enhancements=True), (NotImplementedError,)))
        for column in policy_module.REQUIRED_FACTS:
            checks.run("contract/policy_missing_" + column,
                       lambda c=column: assert_raises(lambda: policy_module.e0_policy(products["same_cv_low98"]["evidence"].drop(columns=c))))
        bads = {}
        for column in PRICE_COLUMNS + ["volume", "segment_id", "valid_price_observation", "valid_strength_observation"]:
            bads["missing_" + column] = good.drop(columns=column)
        bads["reverse_index"] = good.iloc[::-1]
        bads["duplicate_index"] = pd.concat([good, good.iloc[[-1]]])
        f = good.copy(); f.index = f.index.tz_localize("UTC"); bads["timezone"] = f
        f = good.copy(); index = list(f.index); index[1] = index[0] + pd.Timedelta(hours=1); f.index = pd.DatetimeIndex(index); bads["same_natural_day"] = f
        f = good.copy(); f.loc[f.index[1], "segment_id"] = "s2"; bads["noncontiguous_segment"] = f
        f = good.copy(); f.loc[f.index[1], "segment_id"] = None; bads["missing_segment"] = f
        f = good.copy(); f.loc[f.index[1], "segment_id"] = " "; bads["blank_segment"] = f
        for column in ("valid_price_observation", "valid_strength_observation"):
            f = good.copy(); f[column] = f[column].astype(int); bads["nonbool_" + column] = f
            f = good.copy(); f[column] = f[column].astype("boolean"); f.loc[f.index[1], column] = pd.NA; bads["null_" + column] = f
        f = good.copy(); f.loc[f.index[1], "valid_price_observation"] = False; bads["strength_outside_price_mask"] = f
        for column, value in (("close", 0.), ("open", np.nan), ("low", -1.), ("volume", np.inf)):
            f = good.copy(); f.loc[f.index[1], column] = value; bads["invalid_valid_" + column] = f
        for name, bad in bads.items():
            checks.run("contract/reject_" + name, lambda f=bad: assert_raises(lambda: evidence_module.build_evidence(f)))
    except Exception:
        fatal = traceback.format_exc()
        checks.records.append({"check": "suite_setup_or_orchestration", "passed": False, "error": fatal})
    after = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    checks.records.append({"check": "source_identity_before_after", "passed": before == after})
    payload = {
        "created_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "status": "PASS" if all(r["passed"] for r in checks.records) else "FAIL",
        "checks_run": len(checks.records), "passed": sum(r["passed"] for r in checks.records),
        "failed": sum(not r["passed"] for r in checks.records),
        "fixture_protocol_sha256": sha(fixture_dir / "protocol.json"),
        "fixture_manifest_sha256": sha(fixture_dir / "manifest.json"),
        "fixture_addendum_sha256": sha(addition_dir / "protocol.json") if additions else None,
        "native_paths": 20, "injected_policy_unit_paths": 12,
        "derived_reset_paths": len(additions["reset_fixtures"]) if additions else 0,
        "old_state_schema_normalization": "Every legacy int64 state column explicitly converted to Int64; all values, float bits, remaining dtypes and ordering compared exactly. Ledger unchanged.",
        "no_valid_volume_boundary_not_claimed_old_function_identity": True,
        "comparison": "check_exact=True; no allclose", "accounts": 0, "downloads": 0,
        "runtime": {"python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__},
        "source_hashes": before, "results": checks.records,
        "artifacts": {p.name: sha(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    write_json(out / "verification.json", payload)
    print(json.dumps({k: payload[k] for k in ("status", "checks_run", "passed", "failed", "accounts")}))
    for r in checks.records:
        if not r["passed"]:
            print(r["check"])
            print(r.get("error", "source changed")[-2200:])
    return 0 if payload["status"] == "PASS" else 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", type=Path)
    parser.add_argument("--fixtures", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--addendum", type=Path)
    args = parser.parse_args()
    if args.prepare:
        if args.fixtures or args.output:
            parser.error("--prepare cannot be combined with execution arguments")
        prepare(args.prepare)
        return 0
    if not (args.fixtures and args.output):
        parser.error("Both --fixtures and --output required for execution")
    return run_suite(args.fixtures, args.output, args.addendum)


if __name__ == "__main__":
    raise SystemExit(main())
