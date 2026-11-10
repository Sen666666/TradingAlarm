"""Read-only exact comparison of preserved v1/v2 real-history output artifacts."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

import pandas as pd


ROUND = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROUND / "inputs/manifest.json").read_text())
    records, failures = [], []
    for item in manifest["series"]:
        sid = item["id"]
        for name in ("evidence", "state", "ledger"):
            left = ROUND / "results-v1" / sid / f"{name}.parquet"
            right = ROUND / "results-v2" / sid / f"{name}.parquet"
            record = dict(series=sid, artifact=name, v1_sha256=sha(left), v2_sha256=sha(right))
            a, b = pd.read_parquet(left), pd.read_parquet(right)
            try:
                pd.testing.assert_frame_equal(a, b, check_exact=True, check_dtype=True)
                record.update(passed=True, rows=len(a), columns=len(a.columns))
            except Exception as error:
                record.update(passed=False, exception=type(error).__name__, message=str(error))
                failures.append(record)
            record["identical_parquet_bytes"] = record["v1_sha256"] == record["v2_sha256"]
            records.append(record)
        left = ROUND / "results-v1" / sid / "journal.json"
        right = ROUND / "results-v2" / sid / "journal.json"
        same = json.loads(left.read_text()) == json.loads(right.read_text())
        record = dict(series=sid, artifact="journal", passed=same,
                      v1_sha256=sha(left), v2_sha256=sha(right))
        record["identical_json_bytes"] = record["v1_sha256"] == record["v2_sha256"]
        records.append(record)
        if not same:
            failures.append(record)
    result = dict(recorded_at=datetime.now(timezone.utc).isoformat(), passed=not failures,
                  scope="15 fixed series; full evidence/state/ledger exact values and dtypes; full journals",
                  method="Read saved files only; no model reruns; check_exact=True and check_dtype=True",
                  account_runs=0, network_requests=0, model_runs=0,
                  script_sha256=sha(Path(__file__)), series_count=len(manifest["series"]),
                  table_checks=3 * len(manifest["series"]), journal_checks=len(manifest["series"]),
                  records=records, failures=failures)
    with (ROUND / "reviews/real-output-v1-v2.json").open("x") as handle:
        json.dump(result, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")
    print(json.dumps({key: result[key] for key in
                      ("passed", "series_count", "table_checks", "journal_checks", "failures")}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
