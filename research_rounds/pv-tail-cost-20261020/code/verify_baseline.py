"""Verify the frozen, unchanged signal implementation against saved trajectories."""
from pathlib import Path
import hashlib
import importlib.util
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
ROUND = Path(__file__).resolve().parents[1]
OLD = ROOT / "TradingAlarm/research/results/pv-event-structure-20261020"
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()


if __name__ == "__main__":
    output = ROUND / "validation/baseline-identity.json"
    assert not output.exists(), "Refuse to overwrite validation evidence"
    protocol = json.loads((ROUND / "protocol.json").read_text())
    assert sha(ROUND / "protocol.json") == json.loads(
        (ROUND / "protocol-freeze.json").read_text())["sha256"]
    original = OLD / "code/trend_event_structure.py"
    frozen = ROUND / "code/baseline_event_structure.py"
    assert sha(original) == sha(frozen) == protocol["baseline_sha256"]
    inputs = json.loads((ROUND / "inputs/source-manifest.json").read_text())
    for name, digest in inputs.items():
        assert sha(ROOT / name) == digest, ("Source evidence changed", name)
    spec = importlib.util.spec_from_file_location("frozen_event_baseline", frozen)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for file in sorted(OLD.glob("*-signals.csv")):
        frame = pd.read_csv(file, index_col="date", parse_dates=True)
        result = module.event_frame(frame.close, frame.volume)
        pd.testing.assert_frame_equal(result, frame[result.columns], check_dtype=False,
                                      check_freq=False, atol=1e-10, rtol=1e-10)
        rows.append({"symbol": file.stem.removesuffix("-signals"),
                     "observations": len(frame), "saved_signal_match": True})
    # No portfolio, order generation or trade simulation is imported.
    assert not any(name in sys.modules for name in
                   ["run_event_structure", "run_competing_state", "campaign_engine"])
    record = {
        "meaning": "Byte-identical baseline and all saved signal trajectories reproduced; no new model or account performance.",
        "baseline_sha256": sha(frozen), "verified_input_files": len(inputs),
        "signal_series": rows, "mechanism_revisions": 0, "account_runs": 0,
        "original_causality_evidence": {
            "path": str((OLD / "validation.json").relative_to(ROOT)),
            "sha256": sha(OLD / "validation.json"),
            "scope": "Retained original 7 synthetic/27 sampled real prefix checks and scale tests; not claimed rerun here",
        },
        "versions": {"python": sys.version, "pandas": pd.__version__, "numpy": np.__version__},
        "verification_script_sha256": sha(Path(__file__)),
    }
    output.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"series": len(rows), "observations": sum(x["observations"] for x in rows),
                      "match": True, "account_runs": 0}))
