"""Deliver only the reviewed route documents; validate both roots first."""
import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

SOURCE = Path("/Users/bytedance/Documents/ChatGPT/money")
TARGET = Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm")
REVIEW = Path("docs/reviews/2026-10-20-tail-convergence")
REPORT = Path("docs/RESEARCH_TAIL_CONVERGENCE_2026_10_20.md")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


before = json.loads((SOURCE / REVIEW / "before-hashes.json").read_text())
manifest = json.loads((SOURCE / REVIEW / "manifest.json").read_text())
assert not (TARGET / REVIEW).exists(), "Refuse to overwrite a prior delivery"
assert not (TARGET / REPORT).exists(), "Refuse to overwrite an existing report"
for name, hashes in before.items():
    assert sha(TARGET / name) == hashes["target"], ("Target changed", name)
    assert sha(SOURCE / REVIEW / "prior" / name) == hashes["workspace"]
for name, digest in manifest.items():
    relative = Path(name)
    assert not relative.is_absolute() and ".." not in relative.parts
    assert name in before or relative == REPORT or relative.is_relative_to(REVIEW)
    source = SOURCE / relative
    destination = TARGET / relative
    assert source.resolve().is_relative_to(SOURCE.resolve())
    assert destination.resolve().is_relative_to(TARGET.resolve())
    assert sha(source) == digest, ("Source changed", name)

if "--apply" not in sys.argv:
    print(json.dumps({"preflight": "passed", "files": len(manifest)}, ensure_ascii=False))
    raise SystemExit(0)

shutil.copytree(SOURCE / REVIEW, TARGET / REVIEW)
for name in [*before, str(REPORT)]:
    destination = TARGET / name
    temporary = destination.with_name(destination.name + ".tail-convergence-tmp")
    assert not temporary.exists()
    shutil.copy2(SOURCE / name, temporary)
    temporary.replace(destination)
for name, digest in manifest.items():
    assert sha(TARGET / name) == digest, ("Delivery verification failed", name)
receipt = {
    "delivered_at": datetime.now(timezone.utc).isoformat(),
    "files_verified": len(manifest),
    "source": str(SOURCE),
    "target": str(TARGET),
    "manifest_sha256": sha(SOURCE / REVIEW / "manifest.json"),
    "scope": "Reviewed documents, prior snapshots, saved-result audit; no experiment code or account rerun",
}
for root in (SOURCE, TARGET):
    (root / REVIEW / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
    )
print(json.dumps(receipt, ensure_ascii=False))
