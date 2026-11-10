"""Independent checks for pre-freeze input/schema findings; no accounts."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import traceback

import numpy as np
import pandas as pd

from audit_boundaries import CODE, ROOT, digest, evidence, fixture, frame_equal, policy


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    checks = []
    source_hashes = {str(p.relative_to(ROOT)): digest(p) for p in [CODE / "evidence.py", CODE / "policy.py"]}

    def rejects(name, callback):
        try:
            callback()
        except ValueError as exc:
            checks.append({"name": name, "passed": True, "message": str(exc)})
        else:
            raise AssertionError(name + " accepted invalid input")

    try:
        f = fixture()
        facts, _ = evidence.build_evidence(f)
        colliding = f.copy()
        colliding["segment_id"] = pd.Series([1] * 70 + ["1"] * (len(f) - 70), index=f.index, dtype=object)
        rejects("build_rejects_stringified_segment_collision", lambda: evidence.build_evidence(colliding))
        facts_collision = facts.copy()
        facts_collision["segment_id"] = colliding.segment_id
        rejects("policy_rejects_stringified_segment_collision", lambda: policy.e0_policy(facts_collision))

        daily_duplicate = facts.copy()
        dates = daily_duplicate.index.to_numpy(copy=True)
        dates[1] = dates[0] + np.timedelta64(1, "h")
        daily_duplicate.index = pd.DatetimeIndex(dates)
        rejects("policy_rejects_two_times_same_calendar_day", lambda: policy.e0_policy(daily_duplicate))
        blank_segment = facts.copy()
        blank_segment["segment_id"] = "   "
        rejects("policy_rejects_whitespace_segment", lambda: policy.e0_policy(blank_segment))
        incomplete_facts = facts.copy()
        incomplete_facts.loc[incomplete_facts.index[65], "decline_candidate"] = np.nan
        rejects("policy_rejects_missing_binary_candidate_fact", lambda: policy.e0_policy(incomplete_facts))

        # Appending an unknown-price future row cannot change older dtypes.
        future = f.iloc[[-1]].copy()
        future.index = pd.DatetimeIndex([f.index[-1] + pd.Timedelta(days=1)], name=f.index.name)
        future[["valid_price_observation", "valid_strength_observation"]] = False
        full_facts, _ = evidence.build_evidence(pd.concat([f, future]))
        short_state, _ = policy.e0_policy(facts)
        full_state, _ = policy.e0_policy(full_facts)
        frame_equal(short_state, full_state.loc[short_state.index])
        checks.append({"name": "future_invalid_price_cannot_change_past_state_schema", "passed": True})
        for col, dtype in policy.STATE_TYPES.items():
            if dtype in ("int64", "Int64"):
                assert str(short_state[col].dtype) == "Int64"
        checks.append({"name": "all_state_integer_columns_have_stable_nullable_schema", "passed": True})
        assert source_hashes == {str(p.relative_to(ROOT)): digest(p) for p in [CODE / "evidence.py", CODE / "policy.py"]}
        checks.append({"name": "source_bytes_unchanged", "passed": True})
        receipt = {"passed": True, "count": len(checks), "checks": checks, "source_sha256": source_hashes, "accounts": 0}
        (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"passed": True, "checks": len(checks)}))
    except Exception:
        (output / "failure.json").write_text(json.dumps({"passed": False, "checks": checks, "traceback": traceback.format_exc()}, ensure_ascii=False, indent=2) + "\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
