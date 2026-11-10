from pathlib import Path
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
manifest = json.loads((HERE / "manifest.json").read_text())
workspace = Path(manifest["workspace"])
formal = Path(manifest["formal"])
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
if (HERE / "receipt.json").exists():
    raise SystemExit("Already delivered; do not rerun")

# Validate all sources and destinations before the first mutation.
for item in manifest["files"]:
    relative = Path(item["relative"])
    assert not relative.is_absolute() and ".." not in relative.parts
    source = Path(item["source"])
    assert sha(source) == item["after_sha256"], str(source)
    destination = formal / relative
    if item["kind"] == "new":
        assert not destination.exists(), str(destination)
    else:
        assert sha(destination) == item["before_sha256"], str(destination)
    if item["kind"] == "update":
        assert sha(workspace / relative) == item["before_sha256"], str(relative)

for item in manifest["files"]:
    relative = Path(item["relative"])
    source = Path(item["source"])
    destination = formal / relative
    if item["kind"] == "update":
        backup = formal / HERE.relative_to(workspace) / "prior" / relative
        backup.parent.mkdir(parents=True, exist_ok=True)
        assert not backup.exists()
        shutil.copy2(destination, backup)
        shutil.copy2(source, destination)
        shutil.copy2(source, workspace / relative)
    elif item["kind"] == "new":
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("xb") as output:
            output.write(source.read_bytes())
    assert sha(destination) == item["after_sha256"], str(destination)

receipt = {
    "date": "2026-10-22",
    "status": "all_destination_hashes_verified",
    "files": len(manifest["files"]),
    "entry_updates": sum(x["kind"] == "update" for x in manifest["files"]),
    "new_files": sum(x["kind"] == "new" for x in manifest["files"]),
    "manifest_sha256": sha(HERE / "manifest.json"),
    "new_account_runs": 0,
    "frozen_algorithm_changes": 0,
    "new_network_data_requests": 0,
    "existing_evidence_overwritten": False,
}
(HERE / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n")
delivery = formal / HERE.relative_to(workspace)
delivery.mkdir(parents=True, exist_ok=True)
for name in ["manifest.json", "changes.diff", "receipt.json", "deploy.py"]:
    assert not (delivery / name).exists()
    shutil.copy2(HERE / name, delivery / name)
print(json.dumps(receipt, ensure_ascii=False))
