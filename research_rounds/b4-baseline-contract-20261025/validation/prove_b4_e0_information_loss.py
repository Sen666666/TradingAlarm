"""One fixed native-function counterexample; no accounts or parameter search.

Writes a fresh output directory only. Existing model sources remain read-only.
Run with PYTHONDONTWRITEBYTECODE=1 and the repository research Python.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import platform
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
B4_SOURCE = ROOT / "research_rounds/pv-strength-b4-20261025/code/model.py"
NUMERIC_SOURCE = ROOT / "research_rounds/pv-participation-response-20261020/code/numeric.py"
E0_SOURCE = ROOT / "research_rounds/pv-participation-response-20261020/code/participation.py"
PROTOCOL = HERE / "compat-protocol.json"


def digest(path):
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
    if obj is pd.NA:
        return None
    return obj


def write_json(path, obj):
    Path(path).write_text(json.dumps(normalized(obj), ensure_ascii=False,
                                    indent=2, allow_nan=False) + "\n")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def same_frame(a, b):
    pd.testing.assert_frame_equal(a, b, check_exact=True)


def bars():
    c = np.array([100.0, 102.0] * 32 + [100.0, 103.0, 96.0])
    v = np.full(len(c), 100.0)
    v[64] = 200.0
    o = np.r_[c[0], c[:-1]]
    a = pd.DataFrame({"open": o, "high": np.maximum(o, c) + 1.0,
                      "low": np.minimum(o, c) - 1.0, "close": c, "volume": v,
                      "segment_id": "synthetic_same_segment",
                      "valid_strength_observation": True},
                     index=pd.bdate_range("2020-01-01", periods=len(c), name="date"))
    a.loc[a.index[64], "low"] = 98.0
    b = a.copy(deep=True)
    b.loc[b.index[64], "low"] = 94.0
    return a, b


def legal(frame):
    raw = frame[["open", "high", "low", "close", "volume"]]
    assert np.isfinite(raw.to_numpy()).all() and raw.gt(0).all().all()
    assert frame.low.le(frame[["open", "close"]].min(axis=1)).all()
    assert frame.high.ge(frame[["open", "close"]].max(axis=1)).all()
    assert frame.low.le(frame.high).all()
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    assert frame.valid_strength_observation.all()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE / "compat-output-v1")
    args = parser.parse_args()
    out = args.output.resolve()
    if not out.is_relative_to(HERE):
        raise ValueError("Output must remain under this validation directory")
    out.mkdir(parents=True, exist_ok=False)
    sources = [B4_SOURCE, NUMERIC_SOURCE, E0_SOURCE, PROTOCOL, Path(__file__)]
    before = {str(p.relative_to(ROOT)): digest(p) for p in sources}
    write_json(out / "source-hashes-before.json", before)
    protocol = json.loads(PROTOCOL.read_text())
    a, b = bars()
    for frame in (a, b):
        legal(frame)
    same_frame(a.drop(columns="low"), b.drop(columns="low"))
    assert np.flatnonzero(a.low.ne(b.low)).tolist() == [64]
    a.to_csv(out / "input-a-low98.csv", float_format="%.17g")
    b.to_csv(out / "input-b-low94.csv", float_format="%.17g")
    # Input CSVs and protocol are saved before invoking any model function.
    write_json(out / "input-manifest.json", {
        "protocol_sha256": digest(PROTOCOL),
        "rows_per_sequence": len(a),
        "differing_cells": [{"observation_zero_based": 64, "date": str(a.index[64].date()),
                             "column": "low", "a": 98, "b": 94}],
        "files": {p.name: digest(p) for p in sorted(out.glob("input-*.csv"))},
    })
    b4 = load_module("compat_native_b4", B4_SOURCE)
    numeric = load_module("numeric", NUMERIC_SOURCE)
    participation = load_module("compat_native_participation", E0_SOURCE)

    def compute(frame):
        native_b4, journal = b4.strength_frame(frame, joint=True)
        event = numeric.event_frame_numeric(frame.close, frame.volume,
                                            joint=True, event_exit=False)
        e0, ledger = participation.participation_frame(frame, event, mode="volume")
        return native_b4, journal, event, e0, ledger

    runs = {"a": compute(a), "b": compute(b)}
    b4a, ja, ea, e0a, la = runs["a"]
    b4b, jb, eb, e0b, lb = runs["b"]
    same_frame(b4a, b4b)
    assert normalized(ja) == normalized(jb)
    assert normalized(b4a.attrs) == normalized(b4b.attrs)
    same_frame(ea, eb)
    assert not any(name.startswith("e0_") for name in b4a.columns)
    for frame, lower in ((e0a, 98), (e0b, 94)):
        assert frame.iloc[64].created == 1 and frame.iloc[64].pending == 1
        assert frame.iloc[64].pending_lower == lower
        assert frame.iloc[65].independent_entry == 1
        assert frame.iloc[65].entry_kind == "participation_reclaim"
        assert frame.iloc[65].floor == lower and frame.iloc[65].target == 1
    assert ea.iloc[65].event == 0 and 0 < ea.iloc[65].confirmation < 1
    assert ea.target.eq(0).all()  # This is the upstream target, explicitly not E0.
    assert e0a.iloc[66].exited == 1 and e0a.iloc[66].target == 0
    assert e0b.iloc[66].exited == 0 and e0b.iloc[66].target == 1

    prefix_checks = []
    for label, frame in (("a", a), ("b", b)):
        full_b4, full_journal, full_event, full_e0, _ = runs[label]
        for n in protocol["prefix_lengths"]:
            pre_b4, pre_journal, pre_event, pre_e0, _ = compute(frame.iloc[:n])
            same_frame(pre_b4, full_b4.iloc[:n])
            same_frame(pre_event, full_event.iloc[:n])
            same_frame(pre_e0, full_e0.iloc[:n])
            expected_journal = [j for j in full_journal if j["observation"] < n]
            assert normalized(pre_journal) == normalized(expected_journal)
            prefix_checks.append({"sequence": label, "length": n,
                                  "b4_all_columns": True, "b4_journal": True,
                                  "upstream_event_all_columns": True, "e0_all_columns": True})

    b4a.to_csv(out / "b4-native-shared.csv", float_format="%.17g")
    ea.to_csv(out / "upstream-event-shared-not-e0.csv", float_format="%.17g")
    for label, frame, ledger in (("a", e0a, la), ("b", e0b, lb)):
        frame.to_csv(out / f"e0-{label}.csv", float_format="%.17g")
        ledger.to_csv(out / f"e0-memory-ledger-{label}.csv", index=False, float_format="%.17g")
    write_json(out / "b4-native-journal-shared.json", ja)
    write_json(out / "b4-native-attrs-shared.json", b4a.attrs)
    witness = a.loc[a.index[63:]].copy()
    witness["low_b"] = b.low
    witness["upstream_event"] = ea.event
    witness["upstream_confirmation"] = ea.confirmation
    witness["b4_S21"] = b4a.S21
    witness["b4_S63"] = b4a.S63
    for column in ("pending_lower", "floor", "entered", "exited", "target", "entry_kind"):
        witness[f"e0_a_{column}"] = e0a[column]
        witness[f"e0_b_{column}"] = e0b[column]
    witness.to_csv(out / "witness-last-four.csv", float_format="%.17g")
    after = {str(p.relative_to(ROOT)): digest(p) for p in sources}
    assert before == after
    target_differences = np.flatnonzero(e0a.target.ne(e0b.target)).tolist()
    checks = {
        "status": "PASS_counterexample_established",
        "claim_refuted": "A strategy using only complete native B4 outputs/history can exactly reproduce canonical E0 for all admissible OHLCV inputs.",
        "inputs": {"legal_positive_finite_ohlcv": True, "identical_except_one_low": True,
                   "identical_b4_input_columns": b4.INPUT_COLUMNS, "rows_per_sequence": len(a)},
        "b4_exact_identity": {"all_native_columns": list(b4a.columns),
                              "column_count": len(b4a.columns), "rows": len(b4a),
                              "dataframe": True, "journal": True, "journal_records": len(ja),
                              "attrs_including_terminal_state": True,
                              "no_imported_e0_columns": True},
        "upstream_event_frames_identical": True,
        "upstream_numeric_target_is_not_e0": True,
        "independent_reclaim_observation": 65,
        "reclaim_confirmation_below_original_event_threshold": float(ea.iloc[65].confirmation),
        "different_supports": {"a": float(e0a.iloc[65].floor), "b": float(e0b.iloc[65].floor)},
        "e0_target_difference_observations_zero_based": target_differences,
        "exit_witness": {"date": str(a.index[66].date()), "close": float(a.iloc[66].close),
                         "a_exited": int(e0a.iloc[66].exited), "a_target": int(e0a.iloc[66].target),
                         "b_exited": int(e0b.iloc[66].exited), "b_target": int(e0b.iloc[66].target)},
        "physical_prefix_checks": prefix_checks,
        "source_hashes_before_after_identical": before == after,
        "source_hashes": before,
        "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "accounts": 0, "downloads": 0, "parameter_sweeps": 0,
        "model_edits": 0, "mocked_events": False,
        "artifacts": {p.name: digest(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    write_json(out / "verification.json", checks)
    print(json.dumps({k: checks[k] for k in ("status", "reclaim_confirmation_below_original_event_threshold",
                                              "different_supports", "exit_witness")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
