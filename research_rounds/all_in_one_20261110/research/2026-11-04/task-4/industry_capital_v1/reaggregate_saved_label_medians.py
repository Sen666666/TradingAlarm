"""Correct display medians only; reuse saved labels without any financial operation."""
import gzip
import hashlib
import json
import time
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

root = Path(__file__).resolve().parent
folder = root / "labels_new"
labels = folder / "FIRST_REJECT_SHADOW_LABELS.jsonl.gz"
summary = folder / "LABEL_PRODUCTION_SUMMARY.json"
saved = folder / "LABEL_PRODUCTION_SUMMARY.pre_conventional_median.json"
started = time.monotonic()
original = summary.read_bytes()
if saved.exists():
    raise RuntimeError("Display correction already has a preserved original; inspect before rerunning")
saved.write_bytes(original)
groups = defaultdict(list)
with gzip.open(labels, "rt") as stream:
    for line in stream:
        row = json.loads(line)
        if row["known_net"] and row["net_return_pct"] is not None:
            groups[(row["window"], row["status"])].append(Decimal(row["net_return_pct"]))
data = json.loads(original)
changes = []
for row in data["groups"]:
    values = sorted(groups[(row["window"], row["status"])])
    if not values:
        continue
    n = len(values)
    assert n == row["known_net"]
    median = (values[(n - 1) // 2] + values[n // 2]) / 2
    previous = row["net_return_pct"]["median"]
    row["net_return_pct"]["median"] = str(median)
    changes.append({"window": row["window"], "status": row["status"], "n": n,
                    "previous_upper_middle": previous, "conventional_median": str(median)})
data["median_definition"] = "Conventional median; for even N, mean of the two central saved values."
data["display_correction"] = "Saved labels unchanged; only group median displays corrected. Other existing order-statistic percentiles unchanged."
summary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
record = {"scope": "Saved display arithmetic only; no new ledger, market read, or path.",
          "source_labels_sha256": hashlib.sha256(labels.read_bytes()).hexdigest(),
          "original_summary_sha256": hashlib.sha256(original).hexdigest(),
          "corrected_summary_sha256": hashlib.sha256(summary.read_bytes()).hexdigest(),
          "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          "changes": changes, "new_ledgers": 0, "new_market_reads": 0,
          "seconds": time.monotonic() - started}
(folder / "DISPLAY_MEDIAN_CORRECTION.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
print(json.dumps(record, ensure_ascii=False, indent=2))
