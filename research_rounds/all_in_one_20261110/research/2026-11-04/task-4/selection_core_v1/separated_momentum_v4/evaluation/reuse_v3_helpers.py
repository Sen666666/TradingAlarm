"""Load frozen pure evaluation helpers only; no state/ranking/labels read on import."""
from pathlib import Path
import hashlib,importlib.util,json

def load_frozen_helpers():
    here=Path(__file__).resolve().parent
    inventory=json.loads((here/'EXISTING_INPUT_BINDINGS.json').read_text())
    source=Path(inventory['v3_helpers']['path'])
    actual=hashlib.sha256(source.read_bytes()).hexdigest()
    if actual!=inventory['v3_helpers']['sha256']:
        raise RuntimeError('Frozen v3 evaluation helper source changed; do not silently change v4 metrics.')
    spec=importlib.util.spec_from_file_location('frozen_v3_evaluation_core',source)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module

if __name__=='__main__':
    raise SystemExit('Pure-helper loader only. Wait for root-frozen v4 design/state before evaluation.')
