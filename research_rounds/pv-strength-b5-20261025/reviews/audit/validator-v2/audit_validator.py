"""Small independent adversarial tests of validation-v2, with no B5 run."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import traceback

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[5]
ROUND = ROOT / "research_rounds/pv-strength-b5-20261025"
V2 = ROUND / "code-validation-v2"
sys.path.insert(0, str(V2))
import serialization


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


real = load("independent_validator_v2_real", V2 / "verify_real.py")
technical = load("independent_validator_v2_technical", V2 / "test_contract.py")


def fixture():
    index = pd.date_range("2020-01-01", periods=6, name="date")
    return pd.DataFrame({
        "floor": np.array([98., np.nextafter(98., np.inf), np.nan, 94., 1e-200, -1e200]),
        "pending_id": pd.array([1, pd.NA, 2, 3, 4, 5], dtype="Int64"),
        "event_date": pd.Series(["2020-01-01", None, pd.NA, np.nan, pd.NaT, "2020-01-06"], index=index, dtype=object),
        "entry_kind": pd.Series(["x", pd.NA, "y", "z", "a", "b"], index=index, dtype="string"),
    }, index=index)


def run(output):
    output.mkdir(parents=True, exist_ok=False)
    checks = []
    before = {str(p.relative_to(ROOT)): sha(p) for p in [V2 / "verify_real.py", V2 / "test_contract.py", V2 / "serialization.py"]}
    for p in (V2 / "verify_real.py", V2 / "test_contract.py", V2 / "serialization.py"):
        (output / ("reviewed-" + p.name)).write_bytes(p.read_bytes())

    def check(name, operation):
        detail = operation()
        checks.append({"name": name, "passed": True, "detail": detail})

    def equal(actual, expected):
        test = real.Checks()
        test.frame("unit", "exact", actual, expected)
        assert not test.differences, test.differences
        technical.exact(actual, expected)

    def different(actual, expected, *, column=None, position=None, minimum=1):
        test = real.Checks()
        test.frame("unit", "exact", actual, expected)
        assert len(test.differences) >= minimum, test.differences
        if column is not None:
            assert any(d.get("column") == column and (position is None or d.get("position") == position) for d in test.differences), test.differences
        try:
            technical.exact(actual, expected)
        except AssertionError:
            pass
        else:
            raise AssertionError("Technical exact comparator missed the same alteration")
        return {"real_difference_count": len(test.differences), "technical_exact_rejected": True}

    def rejects(operation):
        try:
            operation()
        except (ValueError, TypeError, FileExistsError) as error:
            return {"exception": type(error).__name__, "message": str(error)}
        raise AssertionError("Expected explicit rejection")

    try:
        original = fixture()
        check("identical_nullable_frame_does_not_raise_or_differ", lambda: equal(original.copy(deep=True), original))
        ulp = original.copy(deep=True)
        ulp.iloc[0, 0] = np.nextafter(ulp.iloc[0, 0], np.inf)
        assert ulp.iloc[0, 0] != original.iloc[0, 0]
        check("one_ULP_floor_difference_detected", lambda: different(ulp, original, column="floor", position=0))
        null_shift = original.copy(deep=True)
        null_shift.iloc[1, 0], null_shift.iloc[2, 0] = np.nan, original.iloc[1, 0]
        check("float_null_position_shift_detected", lambda: different(null_shift, original, column="floor", minimum=2))
        nullable_shift = original.copy(deep=True)
        nullable_shift["pending_id"] = pd.array([pd.NA, 1, 2, 3, 4, 5], dtype="Int64")
        check("nullable_integer_null_shift_detected", lambda: different(nullable_shift, original, column="pending_id", minimum=2))
        changed_string = original.copy(deep=True)
        changed_string.iloc[0, 3] = "different"
        check("string_value_difference_detected", lambda: different(changed_string, original, column="entry_kind", position=0))
        changed_object_null = original.copy(deep=True)
        changed_object_null.iloc[0, 2], changed_object_null.iloc[1, 2] = None, "2020-01-01"
        check("object_null_position_shift_detected", lambda: different(changed_object_null, original, column="event_date", minimum=2))
        typed = original.copy(deep=True)
        typed["pending_id"] = typed.pending_id.astype("Float64")
        check("dtype_difference_detected_even_with_equal_values", lambda: different(typed, original, column="pending_id"))
        reordered = original[list(reversed(original.columns))]
        check("column_order_difference_detected", lambda: different(reordered, original))
        wrong_index = original.copy(deep=True)
        wrong_index.index = wrong_index.index + pd.Timedelta(days=1)
        check("index_difference_detected", lambda: different(wrong_index, original))

        path = output / "roundtrip.parquet"
        serialization.write_frame(original, path)
        restored = serialization.read_frame(path)
        check("serialization_roundtrip_preserves_exact_values_and_dtypes", lambda: equal(restored, original))
        check("object_null_sentinels_restored_by_declared_kind", lambda: (
            None if restored.iloc[1, 2] is None and restored.iloc[2, 2] is pd.NA
            and np.isnan(restored.iloc[3, 2]) and restored.iloc[4, 2] is pd.NaT
            else (_ for _ in ()).throw(AssertionError(restored.event_date))))
        check("float_binary64_payloads_unchanged_by_roundtrip", lambda: (
            None if np.array_equal(restored.floor.to_numpy().view(np.uint64), original.floor.to_numpy().view(np.uint64))
            else (_ for _ in ()).throw(AssertionError("float bit change"))))
        schema = json.loads(Path(str(path) + ".schema.json").read_text())
        assert set(schema) == {"version", "columns", "rows", "dtypes", "object_nulls", "restoration"}
        assert set(schema["object_nulls"]) == {"event_date"}
        assert schema["dtypes"]["floor"] == "float64"
        checks.append({"name": "sidecar_has_only_declared_schema_and_object_null_locations", "passed": True})
        check("serialization_refuses_existing_artifact_overwrite", lambda: rejects(lambda: serialization.write_frame(original, path)))

        def tampered_copy(name, change):
            candidate = output / (name + ".parquet")
            serialization.write_frame(original, candidate)
            physical = pd.read_parquet(candidate)
            change(physical)
            physical.to_parquet(candidate)
            return candidate

        tampered_ulp = tampered_copy("tampered-ulp", lambda f: f.__setitem__("floor", ulp.floor))
        read_ulp = serialization.read_frame(tampered_ulp)
        check("sidecar_does_not_restore_or_mask_changed_float", lambda: different(read_ulp, original, column="floor", position=0))
        assert read_ulp.floor.iloc[0] == ulp.floor.iloc[0]
        tampered_null = tampered_copy("tampered-float-null", lambda f: f.__setitem__("floor", null_shift.floor))
        read_null = serialization.read_frame(tampered_null)
        check("sidecar_does_not_restore_or_mask_changed_float_nulls", lambda: different(read_null, original, column="floor", minimum=2))
        tampered_date = tampered_copy("tampered-object-nonnull", lambda f: f.loc.__setitem__((f.index[0], "event_date"), "2099-01-01"))
        read_date = serialization.read_frame(tampered_date)
        check("sidecar_preserves_changed_nonnull_date_for_detection", lambda: different(read_date, original, column="event_date", position=0))
        null_to_value = tampered_copy("tampered-object-null-to-value", lambda f: f.loc.__setitem__((f.index[1], "event_date"), "2099-01-01"))
        check("sidecar_rejects_null_to_value_instead_of_overwriting_it", lambda: rejects(lambda: serialization.read_frame(null_to_value)))
        value_to_null = tampered_copy("tampered-object-value-to-null", lambda f: f.loc.__setitem__((f.index[0], "event_date"), None))
        check("sidecar_rejects_value_to_null_instead_of_restoring_original", lambda: rejects(lambda: serialization.read_frame(value_to_null)))
        wrong_dtype = tampered_copy("tampered-float-dtype", lambda f: f.__setitem__("floor", f.floor.astype("Float64")))
        check("sidecar_rejects_nondeclared_float_dtype_change", lambda: rejects(lambda: serialization.read_frame(wrong_dtype)))
        dup = output / "duplicate-null.parquet"
        serialization.write_frame(original, dup)
        dup_schema_path = Path(str(dup) + ".schema.json")
        dup_schema = json.loads(dup_schema_path.read_text())
        dup_schema["object_nulls"]["event_date"]["none"].append(2)
        dup_schema_path.write_text(json.dumps(dup_schema))
        check("sidecar_rejects_duplicate_null_positions", lambda: rejects(lambda: serialization.read_frame(dup)))

        original_freeze = json.loads((ROUND / "freeze.json").read_text())
        freeze_differences = [p for p,h in original_freeze["sha256"].items() if sha(ROOT / p) != h]
        assert not freeze_differences, freeze_differences
        checks.append({"name": "all_original_77_frozen_files_still_unchanged", "passed": True, "count": len(original_freeze["sha256"])})
        after = {p: sha(ROOT / p) for p in before}
        assert before == after, {p: (before[p], after[p]) for p in before if before[p] != after[p]}
        checks.append({"name": "reviewed_v2_source_bytes_unchanged_during_audit", "passed": True})
        receipt = {"passed": True, "count": len(checks), "checks": checks, "source_sha256": before,
                   "accounts": 0, "b5_model_runs": 0,
                   "scope": "Adversarial unit checks of exact comparators and schema-only serialization; not the real-history compatibility result."}
        (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"passed": True, "checks": len(checks), "accounts": 0}))
    except Exception:
        failure = {"passed": False, "checks": checks, "source_sha256": before, "traceback": traceback.format_exc()}
        (output / "failure.json").write_text(json.dumps(failure, ensure_ascii=False, indent=2) + "\n")
        raise


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
