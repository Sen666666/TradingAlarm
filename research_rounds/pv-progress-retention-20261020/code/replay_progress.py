"""Relocate the frozen trajectory run into a fresh directory, without accounts."""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

BASE = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--prepare-only", action="store_true")
    a = p.parse_args()
    out = a.output.resolve()
    assert not out.exists(), "New output directory required"
    protocol = json.loads((BASE / "protocol-v0.json").read_text())
    relocated = {}
    for old, digest in protocol["input_sha256"].items():
        name = Path(old).name
        source = (a.repo / "TradingAlarm/research/results/pv-event-structure-20261020" / name
                  if name.endswith("-signals.csv") else BASE / "inputs" / name)
        assert source.is_file() and sha(source) == digest, source
        relocated[str(source.resolve())] = digest
    freeze = json.loads((BASE / "v0/freeze.json").read_text())
    for name in ["context_model.py", "progress_model.py", "run_progress.py"]:
        assert sha(BASE / "code" / name) == freeze["code_sha256"][name]
    (out / "code").mkdir(parents=True)
    for name in ["context_model.py", "progress_model.py", "run_progress.py"]:
        shutil.copy2(BASE / "code" / name, out / "code" / name)
    protocol["input_sha256"] = relocated
    protocol["replay_source_protocol_sha256"] = sha(BASE / "protocol-v0.json")
    protocol["replay_note"] = "Only input locations relocated; no parameters or cases changed."
    (out / "protocol-v0.json").write_text(json.dumps(protocol, ensure_ascii=False, indent=2))
    command = [sys.executable, str(out / "code/run_progress.py"), "--version", "v0"]
    if a.prepare_only:
        print(json.dumps({"prepared": str(out), "run": command, "accounts": 0}))
    else:
        subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
