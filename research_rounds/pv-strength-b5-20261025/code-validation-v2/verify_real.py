"""Validation-only v2: nullable-safe exact comparison and lossless I/O schema.

Only this validator imports the old E0 policy. Comparisons use equality and
matching missing positions, never numerical tolerance. The legacy adapter
restarts each source segment and maps price-invalid rows to unknown, as fixed
in PROTOCOL.md. Persisted B4/E0 values are compared independently as well.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys
import traceback

import numpy as np
import pandas as pd


ROUND = Path(__file__).resolve().parents[1]
REPO = ROUND.parents[1]
sys.path.insert(0, str(ROUND / "code"))
from serialization import write_frame, read_frame as read_saved_frame

LEGACY = REPO / "research_rounds/pv-participation-response-20261020/code"
B4 = REPO / "research_rounds/pv-strength-b4-20261025/code/model.py"
FROZEN_SOURCES = {
    LEGACY / "numeric.py": "b07f92f309864ba1cfdb84f76adbf7c4d97d5eff6d90b6b25acd62577be0c2e3",
    LEGACY / "participation.py": "7a7017c7cd43dd2bdd7cfae4cfed29bf16d1b7452e9c411fe53c968692017cf0",
    B4: "0beb0b16f2f2cac4f1aff23258b7c45722dc12f16e495be27bf5635c03888cf1",
}
EVENT_COLUMNS = [
    "confirmation", "leg_direction", "developing_extreme", "confirmed_pivot",
    "event", "pivot_age", "developing_extreme_price", "confirmed_pivot_price",
    "confirmed_pivot_date", "developing_extreme_date",
]
STATE_INTS = [
    "target", "entered", "exited", "pending", "pending_id", "created",
    "response", "consumed_by_base", "independent_entry", "ended_id",
    "high_effort", "declined", "price_event", "ready",
]
OLD_FIVE = ["ready", "target", "entered", "exited", "floor"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(value):
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        if math.isnan(value):
            return None
        return float(value) if math.isfinite(value) else str(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    return value


def write(path, data):
    with Path(path).open("x", encoding="utf-8") as handle:
        json.dump(clean(data), handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class Checks:
    """Keep every unequal cell and every exception while continuing the suite."""

    def __init__(self):
        self.differences = []
        self.completed = Counter()

    def issue(self, sid, check, **detail):
        self.differences.append(dict(series=sid, check=check, **detail))

    def guard(self, sid, check, operation):
        before = len(self.differences)
        try:
            result = operation()
        except Exception as error:
            self.issue(sid, check, exception=type(error).__name__, message=str(error),
                       traceback=traceback.format_exc())
            return None
        self.completed[check] += 1
        return dict(result=result, differences=len(self.differences) - before)

    def frame(self, sid, check, actual, expected, *, dtype=True):
        if list(actual.columns) != list(expected.columns):
            self.issue(sid, check, kind="columns", actual=list(actual.columns),
                       expected=list(expected.columns))
        if not actual.index.equals(expected.index):
            self.issue(sid, check, kind="index", actual=list(actual.index),
                       expected=list(expected.index))
            return
        for column in expected.columns:
            if column not in actual:
                continue
            a, b = actual[column], expected[column]
            if dtype and str(a.dtype) != str(b.dtype):
                self.issue(sid, check, kind="dtype", column=column,
                           actual=str(a.dtype), expected=str(b.dtype))
            # Coerce only to object for element comparison. Float values are
            # never rounded, serialized to decimal text or cast to float32.
            missing_a, missing_b = a.isna().to_numpy(), b.isna().to_numpy()
            equal = missing_a & missing_b
            present = ~missing_a & ~missing_b
            positions = np.flatnonzero(present)
            equal[present] = (a.iloc[positions].to_numpy(dtype=object)
                              == b.iloc[positions].to_numpy(dtype=object))
            for position in np.flatnonzero(~equal):
                self.issue(sid, check, kind="value", column=column,
                           position=int(position), index=actual.index[position],
                           actual=a.iloc[position], expected=b.iloc[position])

    def nested(self, sid, check, actual, expected, path="$"):
        if isinstance(actual, dict) and isinstance(expected, dict):
            if set(actual) != set(expected):
                self.issue(sid, check, kind="keys", path=path,
                           actual=sorted(actual), expected=sorted(expected))
            for key in expected.keys() & actual.keys():
                self.nested(sid, check, actual[key], expected[key], f"{path}.{key}")
        elif isinstance(actual, (list, tuple)) and isinstance(expected, (list, tuple)):
            if len(actual) != len(expected):
                self.issue(sid, check, kind="length", path=path,
                           actual=len(actual), expected=len(expected))
            for n, (a, b) in enumerate(zip(actual, expected)):
                self.nested(sid, check, a, b, f"{path}[{n}]")
        else:
            a, b = clean(actual), clean(expected)
            if a != b:
                self.issue(sid, check, kind="value", path=path, actual=a, expected=b)


def legacy_oracle(f, numeric, participation):
    """The explicit adapter; all legacy formulas run unchanged per price clock."""
    states, events, ledgers, journal = [], [], [], []
    previous_segment = None
    for segment, group in f.groupby("segment_id", sort=False):
        segment = str(segment)
        if previous_segment is not None:
            journal.append(dict(segment=segment, date=str(group.index[0].date()),
                                kind="source_discontinuity", previous_segment=previous_segment,
                                observation=None))
        previous_segment = segment
        bars = group.loc[group.valid_price_observation,
                         ["open", "high", "low", "close", "volume"]].astype(float)
        if bars.empty:
            continue
        # No-volume segments are an explicitly separate extension boundary,
        # never silently accepted as a legacy exact-compatibility success.
        old_events = numeric.event_frame_numeric(bars.close, bars.volume)
        state, ledger = participation.participation_frame(bars, old_events, mode="volume")
        state["segment_id"] = segment
        ledger["segment_id"] = pd.Series(segment, index=ledger.index, dtype="string")
        states.append(state)
        events.append(old_events[EVENT_COLUMNS])
        ledgers.append(ledger)
        cv = bars[["close", "volume"]]
        event_dates = cv.index[cv.gt(0).all(axis=1) & np.isfinite(cv).all(axis=1)]
        event_positions = {date: n for n, date in enumerate(event_dates)}
        v = bars.volume.where(np.isfinite(bars.volume) & bars.volume.gt(0))
        baseline = v.shift().rolling(21, min_periods=21).median()
        previous = bars.close.shift()
        for n, date in enumerate(bars.index):
            event, policy = old_events.loc[date], state.loc[date]
            if event.event:
                journal.append(dict(segment=segment, date=str(date.date()), observation=n,
                                    event_observation=event_positions[date], kind="event_confirmed",
                                    direction=int(event.event), confirmation=float(event.confirmation),
                                    pivot_price=float(event.confirmed_pivot_price),
                                    pivot_date=event.confirmed_pivot_date, pivot_age=int(event.pivot_age)))
            if policy.ready and policy.declined and policy.high_effort:
                journal.append(dict(segment=segment, date=str(date.date()), observation=n,
                                    kind="high_participation_decline", lower=float(bars.loc[date, "low"]),
                                    reclaim=float(previous.loc[date]), volume_ratio=float(policy.volume_ratio),
                                    volume_baseline=float(baseline.loc[date])))
    if not states:
        raise ValueError("Real-history oracle requires at least one valid price observation")
    state = pd.concat(states).reindex(f.index)
    # B5 explicitly uses nullable integers to make schema independent of a
    # future invalid row. This changes representation, not formula or values.
    state = state.astype({column: "Int64" for column in STATE_INTS})
    state["segment_id"] = f.segment_id.astype("string")
    event = pd.concat(events).reindex(f.index)[EVENT_COLUMNS]
    ledger = pd.concat(ledgers, ignore_index=True)
    return event, state, ledger, journal


def ledger_asof(full, prefix):
    """Project future-resolved and terminal-open records into prefix knowledge."""
    pieces = []
    for segment, group in prefix.groupby("segment_id", sort=False):
        bars = group.loc[group.valid_price_observation]
        if bars.empty:
            continue
        n, last_date = len(bars), str(bars.index[-1].date())
        part = full.loc[full.segment_id.eq(str(segment)) & full.created_observation.lt(n)].copy()
        future = part.resolved_date.isna() | part.resolved_date.gt(last_date)
        part.loc[future, "resolved_date"] = pd.NA
        part.loc[future, "outcome"] = "open"
        for column in ("response", "independent_entry", "original_entry_same_day"):
            part.loc[future, column] = 0
        part.loc[future, "resolution_volume_ratio"] = np.nan
        part.loc[future, "waiting_observations"] = n - 1 - part.loc[future, "created_observation"]
        pieces.append(part)
    return pd.concat(pieces, ignore_index=True) if pieces else full.iloc[:0].copy()


def journal_asof(full, last_date):
    last = str(last_date.date())
    return {key: [record for record in records if record["date"] <= last]
            for key, records in full.items()}


def read_frame(path):
    path = Path(path)
    if path.suffix in {".parquet", ".parq"}:
        return pd.read_parquet(path)
    return pd.read_csv(path, index_col=0, parse_dates=True, float_precision="round_trip")


def verify_series(item, output, checks, numeric, participation, b4, run_b5, e0_policy):
    sid = item["id"]
    before = len(checks.differences)
    folder = output / sid
    folder.mkdir()
    path = ROUND / item["file"]
    if sha(path) != item["sha256"]:
        raise ValueError(f"Input hash mismatch: {path}")
    for source, expected in item.get("source_files", {}).items():
        if sha(REPO / source) != expected:
            raise ValueError(f"Original source hash mismatch: {source}")
    f = read_frame(path)
    if len(f) != item["rows"]:
        raise ValueError("Manifest row count mismatch")
    result = run_b5(f, enhancements=False)
    evidence, state, ledger, journal = [result[k] for k in ("evidence", "state", "ledger", "journal")]
    for name in ("evidence", "state", "ledger"):
        write_frame(result[name], folder / f"{name}.parquet")
    write(folder / "journal.json", journal)

    def compare_old():
        old_events, old_state, old_ledger, old_journal = legacy_oracle(f, numeric, participation)
        checks.frame(sid, "legacy_events", evidence[EVENT_COLUMNS], old_events)
        checks.frame(sid, "legacy_policy_all_fields", state, old_state)
        checks.frame(sid, "legacy_ledger_all_fields", ledger, old_ledger)
        checks.nested(sid, "legacy_event_receipts", journal["events"], old_journal)
    checks.guard(sid, "legacy_oracle", compare_old)

    def compare_b4():
        strength, old_journal = b4.strength_frame(f, joint=True)
        if len(strength.columns) != 101:
            raise AssertionError(f"Frozen B4 must expose 101 columns, got {len(strength.columns)}")
        columns = [f"strength_{column}" for column in strength.columns]
        actual = evidence[columns].copy()
        actual.columns = strength.columns
        checks.frame(sid, "b4_current_all_101", actual, strength)
        checks.nested(sid, "b4_current_journal", journal["strength"], old_journal)
        if item.get("old_b4_path"):
            old_path = REPO / item["old_b4_path"]
            saved = read_frame(old_path)
            checks.frame(sid, "b4_saved_all_101", actual, saved[list(strength.columns)], dtype=False)
            saved_journal = old_path.with_name(f"{old_path.stem}-events.json")
            if not saved_journal.is_file():
                raise FileNotFoundError(f"Required saved B4 journal: {saved_journal}")
            checks.nested(sid, "b4_saved_journal", journal["strength"],
                          json.loads(saved_journal.read_text()))
    checks.guard(sid, "b4_oracles", compare_b4)

    def compare_saved_e0():
        saved = read_frame(REPO / item["old_e0_path"])
        prefix = item.get("old_e0_prefix", "e0_")
        expected = saved[[prefix + column for column in OLD_FIVE]].copy()
        expected.columns = OLD_FIVE
        checks.frame(sid, "e0_saved_five_fields", state[OLD_FIVE], expected, dtype=False)
    if item.get("old_e0_path"):
        checks.guard(sid, "saved_e0", compare_saved_e0)

    def policy_invariance():
        reloaded = read_saved_frame(folder / "evidence.parquet")
        checks.frame(sid, "evidence_serialization", reloaded, evidence)
        strength_columns = [column for column in evidence if column.startswith("strength_")]
        mutated = evidence.copy()
        # Every strength column, including dates and labels, is overwritten.
        # A policy that even tries to interpret strength will encounter strings.
        for n, column in enumerate(strength_columns):
            mutated[column] = f"not-policy-input-{n}"
        variants = {"serialized": reloaded,
                    "strength_removed": evidence.drop(columns=strength_columns),
                    "strength_all_perturbed": mutated}
        for label, facts in variants.items():
            observed_state, observed_ledger = e0_policy(facts, enhancements=False)
            checks.frame(sid, f"policy_{label}", observed_state, state)
            checks.frame(sid, f"ledger_{label}", observed_ledger, ledger)
    checks.guard(sid, "policy_boundary", policy_invariance)

    valid_state = state.loc[f.valid_price_observation]
    updates = 0
    for _, group in valid_state.groupby("segment_id", sort=False):
        updates += int((group.target.eq(1) & group.target.shift().eq(1)
                        & group.floor.gt(group.floor.shift())).sum())
    summary = dict(
        id=sid, group=item["group"], rows=len(f), price_observations=int(f.valid_price_observation.sum()),
        strength_observations=int(f.valid_strength_observation.sum()),
        events=int(evidence.event.fillna(0).ne(0).sum()), entries=int(state.entered.sum()),
        exits=int(state.exited.sum()), floor_updates=updates, memories=int(state.created.sum()),
        ledger_records=len(ledger), first=str(f.index[0].date()), last=str(f.index[-1].date()),
        historical_b4_compared=bool(item.get("old_b4_path")),
        historical_e0_compared=bool(item.get("old_e0_path")), prefixes=[],
    )
    print(json.dumps(dict(series=sid, phase="full", rows=len(f), events=summary["events"],
                          entries=summary["entries"], exits=summary["exits"],
                          differences=len(checks.differences) - before)), flush=True)
    lengths = sorted({min(65, len(f)), max(1, len(f) // 3),
                      max(1, len(f) * 2 // 3), max(1, len(f) - 1)})
    for length in lengths:
        check_name = f"prefix_{length}"

        def compare_prefix():
            prefix = f.iloc[:length]
            observed = run_b5(prefix, enhancements=False)
            for name in ("evidence", "state"):
                checks.frame(sid, f"{check_name}_{name}", observed[name], result[name].iloc[:length])
            checks.frame(sid, f"{check_name}_ledger_asof", observed["ledger"], ledger_asof(ledger, prefix))
            checks.nested(sid, f"{check_name}_journal", observed["journal"],
                          journal_asof(journal, prefix.index[-1]))
            return dict(rows=length, last=str(prefix.index[-1].date()),
                        price_observations=int(prefix.valid_price_observation.sum()),
                        ledger_records=len(observed["ledger"]),
                        open_memories=int(observed["ledger"].outcome.eq("open").sum()))

        outcome = checks.guard(sid, check_name, compare_prefix)
        summary["prefixes"].append(dict(rows=length, completed=outcome is not None,
                                        **({"differences": outcome["differences"],
                                            "details": outcome["result"]} if outcome else {})))
        print(json.dumps(dict(series=sid, phase="prefix", rows=length,
                              differences=outcome["differences"] if outcome else "exception")), flush=True)
    summary["differences"] = len(checks.differences) - before
    summary["passed"] = summary["differences"] == 0
    summary["sha256"] = {path.name: sha(path) for path in sorted(folder.iterdir()) if path.is_file()}
    write(folder / "summary.json", summary)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=ROUND / "inputs/manifest.json")
    parser.add_argument("--freeze", type=Path, default=ROUND / "freeze.json")
    parser.add_argument("--validation-freeze", type=Path, default=ROUND / "freeze-validation-v2.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROUND) or output == ROUND:
        parser.error("Output must be a new child directory inside this B5 round")
    if not args.freeze.is_file():
        parser.error("Formal freeze.json is required before executing real-history validation")
    if not args.validation_freeze.is_file():
        parser.error("Separate validation-v2 freeze is required before executing real-history validation")
    freeze_checks, frozen_files = [], {}
    for freeze_path in (args.freeze, args.validation_freeze):
        frozen = json.loads(freeze_path.read_text())
        registered = frozen["sha256"]
        failures = [path for path, expected in registered.items()
                    if not (REPO / path).is_file() or sha(REPO / path) != expected]
        if failures:
            raise RuntimeError(f"Frozen inputs/code changed in {freeze_path}: {failures}")
        frozen_files.update(registered)
        freeze_checks.append(dict(path=str(freeze_path), sha256=sha(freeze_path),
                                  checked_files=len(registered), failures=failures))
    v2_registered = json.loads(args.validation_freeze.read_text())["sha256"]
    for required in (Path(__file__), Path(__file__).with_name("serialization.py")):
        if str(required.resolve().relative_to(REPO)) not in v2_registered:
            raise RuntimeError(f"Validation freeze does not register {required}")
    manifest_key = str(args.manifest.resolve().relative_to(REPO))
    original_registered = json.loads(args.freeze.read_text())["sha256"]
    if manifest_key not in original_registered:
        raise RuntimeError("Selected real-history manifest is not registered in the original freeze")
    manifest = json.loads(args.manifest.read_text())
    series = manifest["series"]
    if len(series) != 15 or len({item["id"] for item in series}) != 15:
        parser.error("Fixed real-history registry requires exactly 15 distinct series IDs")
    if any(Path(item["id"]).name != item["id"] for item in series):
        parser.error("Unsafe series ID")
    for path, expected in FROZEN_SOURCES.items():
        if sha(path) != expected:
            raise RuntimeError(f"Frozen legacy source changed: {path}")
    output.mkdir(parents=True, exist_ok=False)
    checks, summaries = Checks(), []
    fingerprints = {str(path.relative_to(REPO)): sha(path) for path in FROZEN_SOURCES}
    fingerprints.update({str(path.relative_to(REPO)): sha(path)
                         for path in sorted((ROUND / "code").glob("*.py"))})
    fingerprints.update({str(path.relative_to(REPO)): sha(path)
                         for path in sorted((ROUND / "code-validation-v2").glob("*.py"))})
    write(output / "run.json", dict(
        started_at=datetime.now(timezone.utc).isoformat(), manifest_sha256=sha(args.manifest),
        freeze_sha256=sha(args.freeze), protocol_sha256=sha(ROUND / "PROTOCOL.md"),
        validation_freeze_sha256=sha(args.validation_freeze), freeze_checks=freeze_checks,
        validation_revision="v2: nullable-safe exact equality and typed Parquet sidecar; production unchanged",
        code_sha256=fingerprints, python=sys.version, numpy=np.__version__, pandas=pd.__version__,
        comparison="exact values and matching missing positions; nullable Int64 legacy adapter; no tolerance",
        account_runs=0, network_requests=0,
    ))
    numeric = load_module("_b5_validation_numeric", LEGACY / "numeric.py")
    previous_numeric = sys.modules.get("numeric")
    sys.modules["numeric"] = numeric
    try:
        participation = load_module("_b5_validation_participation", LEGACY / "participation.py")
    finally:
        if previous_numeric is None:
            del sys.modules["numeric"]
        else:
            sys.modules["numeric"] = previous_numeric
    b4 = load_module("_b5_validation_b4", B4)
    from api import run_b5
    from policy import e0_policy

    for item in series:
        outcome = checks.guard(item["id"], "series", lambda: verify_series(
            item, output, checks, numeric, participation, b4, run_b5, e0_policy))
        if outcome is not None:
            summaries.append(outcome["result"])
        else:
            summaries.append(dict(id=item["id"], group=item["group"], passed=False,
                                  exception=True, rows=item["rows"]))
            print(json.dumps(dict(series=item["id"], phase="exception", continuing=True)), flush=True)
    for path, expected in fingerprints.items():
        checks.guard("all", "source_unchanged", lambda path=path, expected=expected:
                     checks.nested("all", "source_unchanged", sha(REPO / path), expected, path))
    for path, expected in frozen_files.items():
        checks.guard("all", "frozen_identity_after", lambda path=path, expected=expected:
                     checks.nested("all", "frozen_identity_after", sha(REPO / path), expected, path))
    write(output / "differences.json", checks.differences)
    counts = ["rows", "price_observations", "strength_observations", "events", "entries",
              "exits", "floor_updates", "memories", "ledger_records"]
    summary = dict(
        completed_at=datetime.now(timezone.utc).isoformat(), passed=not checks.differences,
        series=summaries, series_count=len(series), completed_series=sum(not x.get("exception", False) for x in summaries),
        totals={key: sum(x.get(key, 0) for x in summaries) for key in counts},
        prefix_checks=sum(len(x.get("prefixes", [])) for x in summaries),
        differences=len(checks.differences), completed_checks=dict(checks.completed),
        historical_scope="seen development; overlapping source histories are not independent samples",
        account_runs=0, network_requests=0,
    )
    write(output / "summary.json", summary)
    print(json.dumps(dict(passed=summary["passed"], series=len(series), totals=summary["totals"],
                          prefixes=summary["prefix_checks"], differences=summary["differences"])), flush=True)
    return 0 if summary["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
