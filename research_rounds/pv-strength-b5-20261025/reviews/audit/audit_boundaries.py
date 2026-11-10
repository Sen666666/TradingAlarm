"""Independent B5 architecture tests; never run an account or edit model code.

Run with --output <new-directory>. Every output directory is refusal-on-exist.
Frozen E0 is used only in the explicit oracle section, outside profile guards.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[4]
ROUND = ROOT / "research_rounds/pv-strength-b5-20261025"
CODE = ROUND / "code"
OLD = ROOT / "research_rounds/pv-participation-response-20261020/code"
FROZEN_B4 = ROOT / "research_rounds/pv-strength-b4-20261025/code/model.py"
sys.path.insert(0, str(CODE))
import evidence
import policy


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def frame_equal(a, b):
    pd.testing.assert_frame_equal(a, b, check_exact=True)


def equal_json(a, b):
    assert json.dumps(a, sort_keys=True, allow_nan=True) == json.dumps(b, sort_keys=True, allow_nan=True)


def bars(close, volume=None):
    close = np.asarray(close, dtype=float)
    opening = np.r_[close[0], close[:-1]]
    return pd.DataFrame({
        "open": opening, "high": np.maximum(opening, close) + 1,
        "low": np.minimum(opening, close) - 1, "close": close,
        "volume": np.full(len(close), 100.) if volume is None else volume,
        "segment_id": "audit", "valid_price_observation": True,
        "valid_strength_observation": True,
    }, index=pd.date_range("2020-01-01", periods=len(close), name="date"))


def fixture():
    x = bars([100., 102.] * 32 + [100., 103., 96.] + [96., 97.] * 20)
    x.loc[x.index[64], ["volume", "low"]] = [200., 98.]
    return x


def stripped_function(path, name):
    tree = ast.parse(path.read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    if isinstance(fn.body[0], ast.Expr) and isinstance(fn.body[0].value, ast.Constant):
        fn.body.pop(0)
    return ast.dump(fn, include_attributes=False)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    checks, calls = [], set()
    before = {str(p.relative_to(ROOT)): digest(p) for p in [
        OLD / "numeric.py", OLD / "participation.py", FROZEN_B4,
        *[CODE / name for name in ("arithmetic.py", "evidence.py", "policy.py", "api.py")],
    ]}

    def record(name, action):
        action()
        checks.append({"name": name, "passed": True})

    def guard(frame, event, arg):
        if event == "call":
            source = Path(frame.f_code.co_filename)
            if source.is_relative_to(ROOT):
                calls.add(str(source.relative_to(ROOT)))
            if source.is_relative_to(OLD):
                raise AssertionError("Production path called legacy E0: " + str(source))

    try:
        # These AST identity checks exclude only function docstrings.
        for name in ("compare", "log_ratio", "higher"):
            record("exact_scalar_ast_" + name, lambda n=name: (
                None if stripped_function(OLD / "numeric.py", n) == stripped_function(CODE / "arithmetic.py", n)
                else (_ for _ in ()).throw(AssertionError(n))))

        tree = ast.parse((CODE / "evidence.py").read_text())
        names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
        record("evidence_has_no_policy_state_names", lambda: (
            None if not names.intersection({"active", "floor", "pending", "target", "entered", "exited"})
            else (_ for _ in ()).throw(AssertionError(sorted(names)))))
        policy_tree = ast.parse((CODE / "policy.py").read_text())
        literals = {node.value for node in ast.walk(policy_tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
        record("policy_has_no_strength_field_literals", lambda: (
            None if not any(s.startswith("strength_") for s in literals)
            else (_ for _ in ()).throw(AssertionError(sorted(literals)))))
        imports = []
        for name in ("arithmetic.py", "evidence.py", "policy.py", "api.py"):
            for node in ast.walk(ast.parse((CODE / name).read_text())):
                if isinstance(node, ast.Import):
                    imports += [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    imports += [node.module]
        record("production_has_no_legacy_import", lambda: (
            None if not set(imports).intersection({"numeric", "participation"})
            else (_ for _ in ()).throw(AssertionError(imports))))

        f = fixture()
        source_before = f.copy(deep=True)
        sys.setprofile(guard)
        base, journal = evidence.build_evidence(f)
        state, ledger = policy.e0_policy(base)
        sys.setprofile(None)
        record("production_profile_has_no_legacy_E0_call", lambda: None)
        record("build_does_not_mutate_source", lambda: frame_equal(source_before, f))
        saved, saved_attrs, saved_journal = base.copy(deep=True), copy.deepcopy(base.attrs), copy.deepcopy(journal)

        forged = f.copy()
        for col in ("e0_target", "e0_entered", "e0_floor", "target", "entered", "floor", "pending", "account_cash", "pnl"):
            forged[col] = np.arange(len(f)) + 12345.
        altered, altered_journal = evidence.build_evidence(forged)
        record("forged_policy_and_account_inputs_cannot_change_facts", lambda: frame_equal(base, altered))
        record("forged_policy_inputs_cannot_change_fact_journal", lambda: equal_json(journal, altered_journal))
        record("forged_policy_inputs_cannot_change_fact_attrs", lambda: equal_json(base.attrs, altered.attrs))

        minimal = base[[c for c in base if not c.startswith("strength_")]].copy()
        minimal.attrs = {}
        minimal_state, minimal_ledger = policy.e0_policy(minimal)
        record("policy_without_strength_columns_or_attrs", lambda: (frame_equal(state, minimal_state), frame_equal(ledger, minimal_ledger)))
        poisoned = base.copy()
        for col in [c for c in poisoned if c.startswith("strength_")]:
            poisoned[col] = "MUST_NOT_READ_THIS_STRENGTH_VALUE"
        poisoned.attrs = {"target": 0, "floor": 999999, "fake_policy": "ignored"}
        poisoned_state, poisoned_ledger = policy.e0_policy(poisoned)
        record("policy_ignores_poisoned_strength_and_attrs", lambda: (frame_equal(state, poisoned_state), frame_equal(ledger, poisoned_ledger)))
        try:
            policy.e0_policy(base, enhancements=True)
        except NotImplementedError:
            checks.append({"name": "enhancements_true_explicitly_rejected", "passed": True})
        else:
            raise AssertionError("enhancements=True was not rejected")
        record("all_policy_calls_leave_market_frame_unchanged", lambda: frame_equal(base, saved))
        record("all_policy_calls_leave_market_attrs_unchanged", lambda: equal_json(base.attrs, saved_attrs))
        record("all_policy_calls_leave_journal_unchanged", lambda: equal_json(journal, saved_journal))

        # The supplied strength mask must not influence E0's C/V event clock.
        restricted = f.copy()
        restricted.loc[restricted.index[20:90:2], "valid_strength_observation"] = False
        restricted_facts, restricted_journal = evidence.build_evidence(restricted)
        independent_cols = [c for c in base if not c.startswith("strength_") and c != "valid_strength_observation"]
        record("strength_mask_does_not_filter_original_event_clock", lambda: frame_equal(base[independent_cols], restricted_facts[independent_cols]))
        restricted_state, restricted_ledger = policy.e0_policy(restricted_facts)
        record("strength_mask_does_not_change_E0_policy", lambda: (frame_equal(state, restricted_state), frame_equal(ledger, restricted_ledger)))
        record("strength_mask_does_not_change_event_journal", lambda: equal_json(journal["events"], restricted_journal["events"]))
        assert base.strength_mu5.notna().sum() != restricted_facts.strength_mu5.notna().sum()
        checks.append({"name": "strength_mask_actually_changes_B4_channel", "passed": True})

        # This is the only section allowed to execute the frozen E0 oracle.
        old_numeric = load("numeric", OLD / "numeric.py")
        old_policy = load("participation", OLD / "participation.py")
        missing = f.copy()
        missing.loc[missing.index[[65, 72, 73]], "volume"] = [np.nan, 0., np.inf]
        missing.loc[missing.index[[65, 72, 73]], "valid_strength_observation"] = False
        missing_facts, _ = evidence.build_evidence(missing)
        missing_state, missing_ledger = policy.e0_policy(missing_facts)
        old_events = old_numeric.event_frame_numeric(missing.close, missing.volume, joint=True, event_exit=False)
        old_state, old_ledger = old_policy.participation_frame(missing, old_events, mode="volume")
        # B5 freezes nullable integer state columns so future invalid rows do
        # not change the schema of an earlier physical prefix. Values remain
        # exact and floats are not rounded or compared with a tolerance.
        old_state = old_state.astype({c: "Int64" for c, d in policy.STATE_TYPES.items() if d in ("int64", "Int64")})
        record("missing_volume_market_events_match_original_exactly", lambda: frame_equal(missing_facts[evidence.EVENT_COLUMNS], old_events[evidence.EVENT_COLUMNS]))
        record("missing_volume_policy_and_ledger_match_original_exactly", lambda: (
            frame_equal(missing_state.drop(columns="segment_id"), old_state),
            frame_equal(missing_ledger.drop(columns="segment_id"), old_ledger)))
        record("missing_volume_reclaim_occurs_on_price_clock", lambda: (
            None if missing_state.iloc[65].independent_entry == 1 and missing_state.iloc[66].exited == 1
            else (_ for _ in ()).throw(AssertionError(missing_state.iloc[64:67]))))

        # Facts exist while policy is active, rather than inheriting its gate.
        trend = bars([100., 102.] * 32 + [100., 106., 110., 109., 108., 115.])
        trend.loc[trend.index[67], "volume"] = 200.
        trend_facts, trend_journal = evidence.build_evidence(trend)
        trend_state, _ = policy.e0_policy(trend_facts)
        record("candidate_fact_not_gated_by_policy_active", lambda: (
            None if trend_facts.iloc[67].decline_candidate == 1 and trend_state.iloc[67].target == 1 and trend_state.iloc[67].created == 0
            else (_ for _ in ()).throw(AssertionError(trend_state.iloc[64:]))))
        record("unconsumed_candidate_still_has_market_receipt", lambda: (
            None if any(e["kind"] == "high_participation_decline" and e["date"] == str(trend.index[67].date()) for e in trend_journal["events"])
            else (_ for _ in ()).throw(AssertionError(trend_journal["events"]))))

        after = {name: digest(ROOT / name) for name in before}
        record("audited_and_frozen_source_bytes_unchanged", lambda: equal_json(before, after))
        receipt = {"passed": True, "checks": checks, "count": len(checks), "source_sha256": before,
                   "profile_repository_python_sources": sorted(calls), "accounts": 0,
                   "notes": "Finite architecture contract tests; no universal floating-point or economic validity claim."}
        (output / "receipt.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n")
        print(json.dumps({"passed": True, "checks": len(checks), "output": str(output)}))
    except Exception:
        sys.setprofile(None)
        failure = {"passed": False, "checks": checks, "source_sha256": before, "traceback": traceback.format_exc()}
        (output / "failure.json").write_text(json.dumps(failure, indent=2, ensure_ascii=False) + "\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output)
