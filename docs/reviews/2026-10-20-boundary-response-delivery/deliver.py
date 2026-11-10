"""Deliver one authorized offline research round, with bounded backups and hashes."""
from pathlib import Path
import datetime
import hashlib
import json
import shutil

SOURCE = Path("/Users/bytedance/Documents/ChatGPT/money")
TARGET = Path("/Users/bytedance/repos/TradingAlarm/TradingAlarm")
ROUND = Path("research_rounds/pv-boundary-response-20261020")
RECEIPTS = Path("docs/reviews/2026-10-20-boundary-response-delivery")
REPORT = "docs/RESEARCH_BOUNDARY_RESPONSE_2026_10_20.md"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    baseline = json.loads((SOURCE / ROUND / "delivery-baseline.json").read_text())
    manifest = json.loads((SOURCE / ROUND / "manifest.json").read_text())
    if (TARGET / ROUND).exists() or (TARGET / RECEIPTS).exists():
        raise FileExistsError("Refusing to overwrite delivered evidence")
    if (TARGET / REPORT).exists():
        raise FileExistsError("Report destination already exists")
    for relative, expected in baseline.items():
        assert sha(TARGET / relative) == expected, f"Target changed: {relative}"
    for relative, expected in manifest["files"].items():
        p = Path(relative)
        assert not p.is_absolute() and ".." not in p.parts
        assert sha(SOURCE / ROUND / p) == expected, f"Payload changed: {relative}"
    docs = list(baseline) + [REPORT]
    after = {relative: sha(SOURCE / relative) for relative in docs}
    prior = TARGET / RECEIPTS / "prior"
    prior.mkdir(parents=True)
    for relative in baseline:
        dest = prior / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(TARGET / relative, dest)
    shutil.copytree(SOURCE / ROUND, TARGET / ROUND)
    for relative in docs:
        shutil.copy2(SOURCE / relative, TARGET / relative)
    shutil.copy2(Path(__file__), TARGET / RECEIPTS / "deliver.py")
    for relative, expected in manifest["files"].items():
        assert sha(TARGET / ROUND / relative) == expected
    assert sha(TARGET / ROUND / "manifest.json") == sha(SOURCE / ROUND / "manifest.json")
    for relative in docs:
        assert sha(TARGET / relative) == after[relative]
    receipt = dict(
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        status="verified",
        new_result=str(ROUND),
        result_files_in_manifest=len(manifest["files"]),
        result_manifest_sha256=sha(SOURCE / ROUND / "manifest.json"),
        docs={x: dict(before=baseline.get(x), after=after[x]) for x in docs},
        prior_docs=str(prior),
        accounts_run=0,
        remote_actions=0,
    )
    for base in (SOURCE, TARGET):
        (base / RECEIPTS / "receipt.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n"
        )
    print(json.dumps({"status": "verified", "result_files": len(manifest["files"]),
                      "docs": len(docs), "receipt": str(TARGET / RECEIPTS / "receipt.json")}))


if __name__ == "__main__":
    main()
