"""Reuse original C full/physical economic projection; retain raw provenance."""
from pathlib import Path
import importlib.util,json
import resume_runtime_v2 as C
OLD=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/g-s-C-nextsession-native-20261102/compare_branches.py')
spec=importlib.util.spec_from_file_location('frozen_C_branch_comparison',OLD);original=importlib.util.module_from_spec(spec);spec.loader.exec_module(original)
def view(r):
 x=original.normalized(r)
 x['completed_no_subscription_proofs']=json.loads(json.dumps(r.no_subscription_actions,default=C.E.encode))
 return x
def hashes(r):
 x=view(r);return dict(whole=C.E.digest(x),fields={k:C.E.digest(v) for k,v in x.items()})
