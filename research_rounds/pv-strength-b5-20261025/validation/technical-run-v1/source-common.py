"""Offline research bookkeeping; no account or network imports."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import math
import numpy as np

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[1]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if math.isfinite(float(x)) else None
    return x

def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        json.dump(clean(value), stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')

def read(path):
    return json.loads(Path(path).read_text())

def old_identity():
    sets = {
        'e0_r_r1': ('research_rounds/algorithm-baselines-20261024/registry.json', 'sha256'),
        'b4_core': ('research_rounds/pv-strength-b4-20261025/freeze.json', 'sha256'),
        'b4_artifacts': ('research_rounds/pv-strength-b4-20261025/complete.json', 'sha256'),
        'earlier_strength': ('research_rounds/pv-strength-b4-20261025/freeze.json', 'old_files'),
        'b4_contract': ('research_rounds/b4-baseline-contract-20261025/complete.json', 'sha256'),
    }
    summary = {}
    for label, (file, key) in sets.items():
        hashes = read(REPO / file)[key]
        failures = [name for name, expected in hashes.items()
                    if not (REPO / name).is_file() or sha(REPO / name) != expected]
        summary[label] = dict(checked=len(hashes), failures=failures, passed=not failures)
    return dict(recorded_at=now(), passed=all(x['passed'] for x in summary.values()), sets=summary)
