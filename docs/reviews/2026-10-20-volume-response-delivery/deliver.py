"""Hash-checked delivery of this finite offline mechanism study only."""
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("/Users/bytedance/Documents/ChatGPT/money")
TARGET = Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm")
ROUND = Path("research_rounds/pv-volume-response-20261020")
REVIEW = Path("docs/reviews/2026-10-20-volume-response-delivery")
REPORT = Path("docs/RESEARCH_VOLUME_RESPONSE_2026_10_20.md")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


before = json.loads((SOURCE / ROUND / "delivery-baseline.json").read_text())
manifest = json.loads((SOURCE / REVIEW / "manifest.json").read_text())
for directory in (ROUND, REVIEW):
    assert not (TARGET / directory).exists(), ("Existing delivery", str(directory))
assert not (TARGET / REPORT).exists()
for name, old in before.items():
    assert sha(TARGET / name) == old["target"], ("Target changed", name)
    assert sha(SOURCE / REVIEW / "prior" / name) == old["target"]
for name, digest in manifest.items():
    relative = Path(name)
    assert not relative.is_absolute() and ".." not in relative.parts
    assert (name in before or relative == REPORT or
            relative.is_relative_to(ROUND) or relative.is_relative_to(REVIEW))
    assert (SOURCE / relative).resolve().is_relative_to(SOURCE.resolve())
    assert (TARGET / relative).resolve().is_relative_to(TARGET.resolve())
    assert sha(SOURCE / relative) == digest, ("Source changed", name)
inputs = json.loads((SOURCE / ROUND / "inputs/manifest.json").read_text())
dependencies = inputs["series"] + list(inputs["copied_files"].values()) + [inputs["baseline"]]
for record in dependencies:
    for root in (SOURCE, TARGET):
        assert sha(root / record["source"]) == record["sha256"], (
            "Original input or baseline changed", record["source"])

if "--apply" not in sys.argv:
    print(json.dumps({"preflight": "passed", "files": len(manifest),
                      "existing_documents": len(before), "account_runs": 0}))
    raise SystemExit(0)

for directory in (ROUND, REVIEW):
    shutil.copytree(SOURCE / directory, TARGET / directory)
for name in [*before, str(REPORT)]:
    destination = TARGET / name
    temporary = destination.with_name(destination.name + ".volume-response-tmp")
    assert not temporary.exists()
    shutil.copy2(SOURCE / name, temporary)
    temporary.replace(destination)
for name, digest in manifest.items():
    assert sha(TARGET / name) == digest, ("Delivery mismatch", name)
receipt = {
    "delivered_utc": datetime.now(timezone.utc).isoformat(),
    "files_verified": len(manifest),
    "manifest_sha256": sha(SOURCE / REVIEW / "manifest.json"),
    "round": str(ROUND), "target": str(TARGET),
    "new_candidates": 1, "post_candidate_mechanism_revisions": 0,
    "new_account_runs": 0, "adopted": False,
    "validation": "20 synthetic groups passed; real checks 239 passed / 11 failed, failures preserved",
    "scope": "New offline volume-state prototype, controls, charts, audits, documentation; original evidence preserved",
}
for root in (SOURCE, TARGET):
    (root / REVIEW / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
print(json.dumps(receipt, ensure_ascii=False))
