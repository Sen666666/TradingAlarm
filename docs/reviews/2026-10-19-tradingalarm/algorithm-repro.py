"""Read-only, synthetic reproductions for the 2026-10-19 algorithm review.

AST-extract only named pure functions: no research module is imported and no
historical experiment main() is run. Original source/result files are unchanged.
"""
import argparse
import ast
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


FUNCTIONS = [
    ("pairwise_trend_strength.py", ["pair_slope"]),
    ("trend_equal_weight.py", ["equal_scores"]),
    ("trend_shock_scale.py", ["score_of", "shock_entry"]),
    ("trend_quiet_scale.py", ["opposing_rms", "quiet_entry"]),
    ("trend_half_slow.py", ["quiet_half_slow"]),
    ("trend_thrust_fail.py", ["thrust_state"]),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm"))
    parser.add_argument("--output", type=Path, default=Path(__file__).with_suffix(".json"))
    args = parser.parse_args()
    research = args.repo / "TradingAlarm/research"
    ns = {"np": np, "pd": pd, "math": math}
    hashes = {}
    # Read the actual source constants instead of silently supplying new values.
    for filename, wanted in [
        ("trend_background_hold.py", {"ENTRY", "VIOLENT"}),
        ("trend_positive_connect.py", {"NEUTRAL"}),
        ("trend_half_slow.py", {"OPEN_HALF"}),
    ]:
        path = research / filename
        source = path.read_bytes()
        hashes[filename] = hashlib.sha256(source).hexdigest()
        tree = ast.parse(source, filename=str(path))
        nodes = [n for n in tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id in wanted for t in n.targets)]
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)
    for filename, names in FUNCTIONS:
        path = research / filename
        source = path.read_bytes()
        hashes[filename] = hashlib.sha256(source).hexdigest()
        tree = ast.parse(source, filename=str(path))
        nodes = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names]
        assert len(nodes) == len(names), (filename, names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(path), "exec"), ns)

    rng = np.random.default_rng(123)
    index = pd.date_range("2000-01-01", periods=180)
    prices = pd.Series(100 * np.exp(np.cumsum(rng.normal(.002, .01, len(index)))), index=index)
    amount_constant = pd.Series(np.ones(len(index)), index=index)
    amount_perturbed = pd.Series(np.exp(rng.normal(0, 5, len(index))), index=index)
    first = ns["equal_scores"](prices, amount_constant)
    second = ns["equal_scores"](prices, amount_perturbed)
    open_first = ns["quiet_half_slow"](prices, amount_constant, first)
    open_second = ns["quiet_half_slow"](prices, amount_perturbed, second)
    amount_result = {
        "seed": 123, "bars": len(index),
        "perturbed_amount_min": float(amount_perturbed.min()),
        "perturbed_amount_max": float(amount_perturbed.max()),
        "fast_slow_background_exactly_equal": first.equals(second),
        "half_slow_opener_exactly_equal": open_first.equals(open_second),
        "scope": "All prices and amounts remain finite and strictly positive. Amount still controls row eligibility; this does not test missing/zero amount rows.",
    }
    assert amount_result["fast_slow_background_exactly_equal"]
    assert amount_result["half_slow_opener_exactly_equal"]

    entry = [9., 9., 4.9, 4.5]
    fast = list(entry)
    slow = [.001] * 4
    paths = {"never_above_signal": [100., 100., 99., 98.],
             "epsilon_above_once": [100., 100.000001, 99., 98.]}
    memory_result = {
        "entry": entry, "fast": fast, "slow": slow,
        "paths": {name: {"close": close, "held": ns["thrust_state"](entry, fast, slow, close).tolist()}
                  for name, close in paths.items()},
        "interpretation": "One arbitrarily small higher close permanently disables the failed-thrust exit for that holding. This is causal trading memory, not evidence of look-ahead. Scores are held fixed to isolate the state machine; these four bars are not a complete fitted market example.",
    }
    assert memory_result["paths"]["never_above_signal"]["held"] == [1., 1., 0., 0.]
    assert memory_result["paths"]["epsilon_above_once"]["held"] == [1., 1., 1., 1.]

    report = {
        "review_date": "2026-10-19", "repo": str(args.repo.resolve()),
        "method": "AST extraction of named pure functions/constants; synthetic inputs only; no original module import/main, historical backtest, credentials, or network access.",
        "versions": {"numpy": np.__version__, "pandas": pd.__version__},
        "source_sha256": hashes,
        "review_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "amount_invariance": amount_result, "signal_price_memory": memory_result,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"output": str(args.output.resolve()), "amount_invariance": True,
                      "signal_price_memory_reproduced": True}, ensure_ascii=False))


if __name__ == "__main__":
    main()
