"""Check saved values and integrity only; never imports or executes F1."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd

O=Path(__file__).resolve().parent;P=O/'run-v1';B=O.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()


def numeric(x):
    # Parquet all-UNKNOWN columns may be NullType/None, not float NaN.
    return pd.to_numeric(x,errors='raise').to_numpy(dtype=float,na_value=np.nan)


def main():
    nodes=json.loads((P/'ALL_NODES.json').read_text());checks=[]
    for n in nodes:
        if n['status']!='INPUT_READY':continue
        f=pd.read_parquet(P/'daily'/(n['node_id']+'.parquet'))
        allowed=f.close.notna()&f.breadth.gt(.6)&f['mode'].eq('ACTIVE')&f.effective_status.eq('ACTIVE')
        assert not (f.permit_next_open&~allowed).any()
        z=pd.read_parquet(n['input_file']);z.index=z.index.strftime('%Y-%m-%d');z=z.reindex(f.index)
        np.testing.assert_allclose(numeric(f.close),numeric(z.price_input),rtol=0,atol=0,equal_nan=True)
        np.testing.assert_allclose(numeric(f.breadth),numeric(z.breadth),rtol=0,atol=0,equal_nan=True)
        checks.append(dict(node_id=n['node_id'],rows=len(f),permission_known_ACTIVE_only=True,prices_exact_input=True,breadth_exact_input=True))
    for root in [B/'v2-frozen',B/'historical-shadow/run-v1',B/'input-preparation/prepared-v2']:
        manifest=json.loads((root/'ARTIFACT_SHA256.json').read_text())
        assert all(sha(root/name)==h for name,h in manifest.items())
    result=dict(passed=True,all_node_checks=checks,frozen_core_contract_original_four_and_previous_inputs_unchanged=True,
                no_FSM_reexecution_in_integrity_check=True,validator_sha256=sha(Path(__file__)))
    (P/'INTEGRITY.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(passed=True,node_checks=len(checks),FSM_reexecutions=0)))


if __name__=='__main__':main()
