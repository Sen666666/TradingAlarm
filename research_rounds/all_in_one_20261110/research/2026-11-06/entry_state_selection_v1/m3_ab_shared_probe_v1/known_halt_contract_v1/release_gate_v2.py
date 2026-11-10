"""Fail-closed reviewed-byte gate. No source loads, state mutation or cohort execution."""
from pathlib import Path
import hashlib,json

def digest(data):return hashlib.sha256(data).hexdigest()
def load_reviewed_contract(root,*,stage_name='PRE_RUN_STAGE_SEAL_V2.json',contract_name='RECOVERY_COHORT_CONTRACT_V2.json'):
    root=Path(root).resolve()
    release=json.loads((root/'INDEPENDENT_REVIEW_RELEASE.json').read_bytes())
    if release.get('status')!='PASS' or release.get('scope')!='RUN_2022_COHORT_ONCE':raise ValueError('Independent release not granted')
    stage_bytes=(root/stage_name).read_bytes()
    if release.get('reviewed_stage_sha256')!=digest(stage_bytes):raise ValueError('Reviewed stage seal changed')
    stage=json.loads(stage_bytes);verified={}
    if not isinstance(stage,dict) or contract_name not in stage:raise ValueError('Contract is not bound by reviewed stage')
    for relative,expected in stage.items():
        path=(root/relative).resolve()
        if Path(relative).is_absolute() or not path.is_relative_to(root):raise ValueError('Stage path outside review package')
        data=path.read_bytes()
        if digest(data)!=expected:raise ValueError('Reviewed stage dependency changed: '+relative)
        if relative==contract_name:verified[relative]=data
    # Parse the same verified bytes, not another unverified disk read.
    contract=json.loads(verified[contract_name])
    for name,expected in contract['code_hashes'].items():
        if digest(Path(name).read_bytes())!=expected:raise ValueError('Frozen code/source dependency changed: '+name)
    return contract
