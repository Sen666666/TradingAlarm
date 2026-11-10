"""Read-only source diagnostics. No account, target, exposure or trade engine.

This is an exploratory definition review, not a frozen candidate benchmark.
The output directory is exclusive-created to preserve every attempt.
"""
from pathlib import Path
import importlib.util
import hashlib
import json
import math
import platform
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
SOURCES = {
    "cumulative": ROOT / "TradingAlarm/research/cumulative_trend_strength.py",
    "markov": ROOT / "TradingAlarm/research/markov_trend_strength.py",
    "segmented": ROOT / "TradingAlarm/research/segmented_trend_strength.py",
    "swing": ROOT / "TradingAlarm/research/swing_structure_strength.py",
    "retained": ROOT / "research_rounds/pv-retained-impact-20261020/code/trend_retained_impact.py",
    "region": ROOT / "research_rounds/pv-price-region-20261020/code/trend_price_region.py",
    "ledger": ROOT / "research_rounds/path-ledger-design-20261020/code/path_ledger.py",
}


def module(name):
    spec = importlib.util.spec_from_file_location("definition_" + name, SOURCES[name])
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def main():
    destination = HERE / "legacy-diagnostics-v1"
    destination.mkdir(exist_ok=False)
    loaded = {name: module(name) for name in SOURCES}
    result = {
        "scope": "Exploratory source counterexamples; synthetic OHLCV only; no candidate or account claims",
        "runtime": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__},
        "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in SOURCES.values()},
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }

    # Correct cancellation still collapses signed totals to endpoint displacement.
    paths = [[.04, -.06, .04], [.04, .04, -.06]]
    ledger = [loaded["ledger"].cancel(path) for path in paths]
    result["same_endpoint_different_order"] = {"moves": paths, "ledger": ledger}
    rng = np.random.default_rng(20261025)
    errors = []
    for _ in range(1000):
        moves = rng.normal(0, .01, 63)
        weights = rng.uniform(.25, 4, 63)
        record = loaded["ledger"].cancel(moves, weights)
        errors.append(abs(record["net"] - moves.sum()))
        assert abs(record["net"] - moves.sum()) < 1e-12
        assert abs(record["retained_absolute"] - abs(record["net"])) < 1e-12
        if abs(record["net"]) > 1e-12:
            assert np.sign(record["weighted"]) == np.sign(record["net"])
    result["ledger_random_identity"] = {"paths": 1000, "max_net_error": max(errors)}

    # Equal empirical price mass can get different quantiles in the old code.
    q1 = loaded["region"].quantiles([0., 0., 1.], [1., 9., 1.]).tolist()
    q2 = loaded["region"].quantiles([0., 0., 1.], [9., 1., 1.]).tolist()
    result["equal_price_mass_tie_artifact"] = {"first": q1, "permuted_ties": q2, "q75_difference": q1[2] - q2[2]}

    # The same old move is counted again after a complete reversal and revisit.
    # Ends at +.03 in each case; all three have the same absolute end displacement.
    retained_records = []
    for k in [1, 3, 6]:
        y = np.zeros(100).tolist() + np.zeros(63 - 2 * k + 1).tolist()
        for _ in range(k - 1):
            y.extend([.03, 0.])
        y.append(.03)
        y = np.asarray(y)
        price = pd.Series(np.exp(y))
        volume = pd.Series(np.ones(len(y)))
        frame = loaded["retained"].retained_frame(price, volume, joint=True)
        retained_records.append({"up_crossings": k, "net_log_displacement": .03, **frame.iloc[-1].to_dict()})
    result["retained_revisit"] = retained_records

    # Scaling all log moves leaves normalized-return/velocity outputs unchanged.
    # This is valid for a relative-noise score, but it is not absolute speed.
    time = np.arange(180)
    base = .0005 * time + .0001 * np.sin(time / 3)
    index = pd.date_range("2000-01-01", periods=len(time))
    volume = pd.Series(1., index=index)
    p1 = pd.Series(np.exp(base), index=index)
    p10 = pd.Series(np.exp(10 * base), index=index)
    amplitude = {}
    for name, function in [
        ("cumulative", loaded["cumulative"].cumulative_frame),
        ("markov", loaded["markov"].markov_frame),
        ("segmented", loaded["segmented"].segmented_frame),
    ]:
        f1, f10 = function(p1, volume), function(p10, volume)
        amplitude[name] = {
            "terminal_strength_1x": float(f1.strength.iloc[-1]),
            "terminal_strength_10x": float(f10.strength.iloc[-1]),
            "max_strength_difference": float(np.nanmax(np.abs(f1.strength - f10.strength))),
        }
    result["log_move_amplitude_scaling"] = amplitude

    # An extreme single observation can saturate the old CUSUM cap. Its later
    # signal is evidence memory; it must not be described as fresh progression.
    pulse = loaded["cumulative"].accumulate([0.] * 10 + [20.] + [0.] * 40)
    result["cusum_pulse_then_zero"] = {
        str(k): pulse.iloc[10 + k].to_dict() for k in [0, 1, 5, 20, 30, 40]
    }

    # Global units should have no semantic effect. Actual old functions are used.
    random_y = np.cumsum(rng.normal(.0002, .01, 180))
    price = pd.Series(np.exp(random_y), index=index)
    volume = pd.Series(rng.lognormal(5, .3, len(index)), index=index)
    unit_checks = []
    for name, function in [
        ("cumulative", loaded["cumulative"].cumulative_frame),
        ("markov", loaded["markov"].markov_frame),
        ("retained", loaded["retained"].retained_frame),
    ]:
        f = function(price, volume, joint=True)
        g = function(price * 100, volume * 10000, joint=True)
        difference = float(np.nanmax(np.abs(f.strength - g.strength)))
        np.testing.assert_allclose(f.strength, g.strength, atol=1e-10, rtol=1e-10, equal_nan=True)
        unit_checks.append({"model": name, "max_strength_difference": difference, "pass": True})
    result["global_unit_scaling"] = unit_checks
    (destination / "diagnostics.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(destination), "source_modules_read": len(SOURCES), "accounts": 0, "new_candidate_runs": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
