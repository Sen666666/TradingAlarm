"""Reviewed staged entrypoints; no account is created by import or prepare."""
from pathlib import Path
from types import MappingProxyType
import argparse
import copy
import gc
import gzip
import hashlib
import json
import sys
import time
import traceback

O = Path(__file__).resolve().parent
ROOT = O.parent
OLD = ROOT.parent / "new_price_trend_v1" / "funding"
sys.path.insert(0, str(OLD))
import input_loader as D
import run_entry as OLD_RUN
import confirmed_adapter as C

N, J, L, IO = C.N, C.J, C.L, C.IO
POLICY = "CORE_CONFIRMED_ZERO_PROBE_SAME_DAY_I_CP"
TECH_CUTS = {"long": "2022-01-14", "strong": "2025-07-15"}
FULL_SECONDS = {"long": 1600, "strong": 800}
BASELINES = {w: OLD / "runs" / (w + "_OFF") for w in D.WINDOWS}
STREAMS = OLD_RUN.STREAMS


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def save(path, value):
    IO.write_json(Path(path), J.W.canon(value))


def baseline_source_agreement():
    old = read(OLD / "SOURCE_FREEZE.json")
    prior_index = read(OLD.parent / "FINAL_ARTIFACT_SHA256.json")["artifacts"]
    output_manifest_path = OLD / "FULL_OUTPUT_SHA256.json"
    assert sha(output_manifest_path) == prior_index["funding/FULL_OUTPUT_SHA256.json"]
    assert sha(OLD / "SOURCE_FREEZE.json") == prior_index["funding/SOURCE_FREEZE.json"]
    output_manifest = read(output_manifest_path)
    checks = {p: sha(p) == digest for p, digest in old["sources"].items()}
    assert all(checks.values()), [p for p, ok in checks.items() if not ok]
    assert read(OLD / "runs" / "COMPLETE.json")["passed"]
    for window, path in BASELINES.items():
        artifacts = [path / "ORIGINAL_IDENTITY.json", path / "DONE.json", path / "pair" / "B.json.gz"]
        artifacts.extend(path / "pair" / (s + ".jsonl.gz") for s in STREAMS)
        for artifact in artifacts:
            assert sha(artifact) == output_manifest[str(artifact.resolve())], ("Old full output changed", str(artifact))
        proof = read(path / "ORIGINAL_IDENTITY.json")
        assert proof["passed"] and all(proof["checks"].values())
        assert read(path / "DONE.json")["completed"]
    return {
        "all_prior_freeze_sources_unchanged": True,
        "prior_source_files": len(checks),
        "original_complete_sha256": sha(OLD / "runs" / "COMPLETE.json"),
        "original_output_manifest_sha256": sha(output_manifest_path),
        "reused_book_six_streams_DONE_and_identity_bound_to_original_manifest": True,
        "old_full_identity_proofs": {w: sha(p / "ORIGINAL_IDENTITY.json") for w, p in BASELINES.items()},
        "new_complete_OFF_accounts": 0,
    }


def freeze():
    result = C.source_freeze()
    paths = [Path(__file__), ROOT / "PROTOCOL.txt", OLD / "input_loader.py", OLD / "entry_adapter.py",
             OLD / "run_entry.py", OLD / "SOURCE_FREEZE.json", OLD / "runs" / "COMPLETE.json",
             OLD / "FULL_OUTPUT_SHA256.json", OLD.parent / "FINAL_ARTIFACT_SHA256.json",
             *D.RECEIPT_MANIFESTS, *D.SCORES.values()]
    for path in BASELINES.values():
        paths.extend([path / "ORIGINAL_IDENTITY.json", path / "DONE.json", path / "pair" / "B.json.gz"])
        paths.extend(path / "pair" / (s + ".jsonl.gz") for s in STREAMS)
    result.update({str(p.resolve()): sha(p) for p in paths})
    return result


def prepare():
    C.prepare_sources()
    agreement = baseline_source_agreement()
    save(O / "BASELINE_SOURCE_AGREEMENT.json", agreement)
    value = {"policy": POLICY, "sources": freeze(), "windows": D.WINDOWS,
             "technical_cuts": TECH_CUTS, "technical_prefix_paths": 6,
             "technical_native_seconds": 180, "full_native_seconds_by_window": FULL_SECONDS,
             "full_new_ON_accounts": 2, "full_OFF_accounts_reused": 2,
             "baseline_pairs": {w: str(p / "pair") for w, p in BASELINES.items()},
             "cash_each": 1000000, "imported_financial_accounts": 0,
             "risk_contract_changed": True,
             "risk_change": "Probe pool limits no longer constrain newly permitted confirmed CORE; mature industry capital10/20 replaces2; sector1/I0.25/cash10/stock10 retained.",
             "baseline_source_agreement": agreement}
    path = O / "SOURCE_FREEZE.json"
    if path.exists():
        assert read(path) == J.W.canon(value), "Frozen candidate sources changed"
    else:
        save(path, value)
    print("PREPARED", path, flush=True)


class Budget:
    def __init__(self, limit, path):
        self.limit, self.path, self.used = limit, path, 0.0

    def run(self, callback):
        left = self.limit - self.used
        assert left > 0, "Frozen native compute budget exhausted"
        start = time.monotonic()
        try:
            return callback(left)
        finally:
            self.used += time.monotonic() - start
            save(self.path, {"limit_seconds": self.limit, "used_seconds": self.used,
                             "remaining_seconds": max(0, self.limit - self.used)})


def construct(value, mode):
    shared, receipts, cp, states, ir, _ = value
    runner = C.Runner(shared, receipts, core_confirmed_mode=mode, **C.S.kwargs(cp, states, ir))
    runner.source_freeze = dict(read(O / "SOURCE_FREEZE.json")["sources"])
    a = runner.accounts["B"]
    assert a.available == a.current_nav == a.initial_cash == J.D(1000000)
    assert not (a.positions or a.layers or a.trades or a.buys or a.exits or a.core_epoch
                or a.budget.orders or a.budget.lots or a.budget.losses)
    return runner


def run(runner, out, end, budget):
    out.mkdir(parents=True, exist_ok=False)
    with IO.atomic_runner_outputs(runner, L, out, canonicalize=J.W.canon):
        done = budget.run(lambda left: runner.run_prepared(out, left, end=end))
    if not done:
        raise RuntimeError("Native timeout saved checkpoint/partial; no automatic replay")
    return out / "pair"


def validate_authorization(auth, scope):
    assert auth["approved"] is True and auth["scope"] == scope
    assert auth["source_freeze_sha256"] == sha(O / "SOURCE_FREEZE.json")
    assert freeze() == read(O / "SOURCE_FREEZE.json")["sources"]
    for path, digest in auth.get("bound_reviews", {}).items():
        assert sha(path) == digest and read(path)["passed"] is True


def technical(auth):
    validate_authorization(auth, "CORE_CONFIRMED_TECHNICAL")
    root = O / "technical"
    root.mkdir(exist_ok=True)
    assert not (root / "TIMING.json").exists(), "Prior technical compute needs inspection; no replay"
    budget = Budget(180, root / "TIMING.json")
    proofs, preparation = {}, {}
    for window, cut in TECH_CUTS.items():
        N.configure_scores(D.SCORES[window])
        full_scores = N.SCORES
        start = time.monotonic()
        value = D.inputs(window)
        preparation[window] = time.monotonic() - start
        off = construct(value, "OFF")
        off_pair = run(off, root / (window + "_OFF"), cut, budget)
        # Full book equality at this cut is obtained from the saved old prefix
        # if available; old full books are not falsely compared to shorter books.
        old_prefix = OLD / "technical" / (window + "_OFF") / "pair"
        proof = OLD_RUN.compare_pairs(old_prefix, off_pair)
        full_prefix = OLD_RUN.compare_pairs(BASELINES[window] / "pair", off_pair, cut=cut, include_book=False)
        save(root / (window + "_OFF_IDENTITY.json"), {"native_old_prefix": proof, "full_old_prefix": full_prefix})
        assert proof["passed"] and full_prefix["passed"], "OFF differs from original No60"
        del off
        gc.collect()
        on = construct(value, "ON")
        on_pair = run(on, root / (window + "_ON_full_lookup"), cut, budget)
        del on
        gc.collect()
        physical = D.physical(value, cut)
        # Truncate all immutable future scores as well as native facts/receipts.
        N.SCORES = copy.copy(full_scores)
        N.SCORES.values = MappingProxyType({s: MappingProxyType({d: v for d, v in rows.items() if d <= cut})
                                          for s, rows in full_scores.values.items()})
        small = construct(physical, "ON")
        small_pair = run(small, root / (window + "_ON_physical"), cut, budget)
        prefix = OLD_RUN.compare_pairs(on_pair, small_pair)
        for name in C.EXTRA_STREAMS:
            prefix[name + "_exact"] = OLD_RUN.rows(on_pair / (name + ".jsonl.gz")) == OLD_RUN.rows(small_pair / (name + ".jsonl.gz"))
            prefix["passed"] = prefix["passed"] and prefix[name + "_exact"]
        save(root / (window + "_PHYSICAL_PREFIX.json"), prefix)
        assert prefix["passed"], "ON physical prefix differs"
        proofs[window] = {"off": proof, "old_full_prefix": full_prefix, "physical": prefix,
                          "fallback_audit_rows": len(OLD_RUN.rows(on_pair / "core-confirmed.jsonl.gz"))}
        N.SCORES = full_scores
        del small, physical, value
        gc.collect()
    assert freeze() == read(O / "SOURCE_FREEZE.json")["sources"]
    save(root / "GATE.json", {"passed": True, "proofs": proofs, "native_seconds": budget.used,
                             "input_preparation_seconds": preparation, "prefix_paths": 6,
                             "new_complete_accounts": 0, "source_freeze_sha256": sha(O / "SOURCE_FREEZE.json")})


def full(auth, window):
    validate_authorization(auth, "CORE_CONFIRMED_TWO_FULL_ON")
    assert window in D.WINDOWS
    gate = O / "technical" / "GATE.json"
    assert read(gate)["passed"] and auth["technical_gate_sha256"] == sha(gate)
    root = O / "runs"
    root.mkdir(exist_ok=True)
    timing = root / (window + "_TIMING.json")
    assert not timing.exists() and not (root / (window + "_ON")).exists(), "No automatic full-path replay"
    N.configure_scores(D.SCORES[window])
    start = time.monotonic()
    value = D.inputs(window)
    prep = time.monotonic() - start
    save(root / (window + "_INPUT_IDENTITY.json"), value[-1])
    print("INPUT_READY", window, "seconds", round(prep, 3), flush=True)
    runner = construct(value, "ON")
    save(root / (window + "_FRESH.json"), {"cash": 1000000, "positions": 0, "orders": 0, "imported_accounts": 0})
    budget = Budget(FULL_SECONDS[window], timing)
    out = root / (window + "_ON")
    run(runner, out, D.WINDOWS[window][1], budget)
    assert freeze() == read(O / "SOURCE_FREEZE.json")["sources"]
    save(root / (window + "_COMPLETE.json"), {"passed": True, "window": window, "new_ON_accounts": 1,
         "new_OFF_accounts": 0, "native_seconds": budget.used, "input_preparation_seconds": prep,
         "baseline_reused": str(BASELINES[window]), "source_freeze_sha256": sha(O / "SOURCE_FREEZE.json")})
    print("FULL_SAVED", window, "native_seconds", round(budget.used, 3), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "technical", "full"])
    parser.add_argument("--window", choices=list(D.WINDOWS))
    parser.add_argument("--authorization-file", type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        return prepare()
    assert args.authorization_file
    try:
        if args.action == "technical":
            technical(read(args.authorization_file))
        else:
            assert args.window
            full(read(args.authorization_file), args.window)
    except BaseException as error:
        suffix = args.action + ("_" + args.window if args.window else "")
        save(O / (suffix + "_FAILURE.json"), {"error": str(error), "traceback": traceback.format_exc(),
                                            "automatic_replay": False})
        raise


if __name__ == "__main__":
    main()
