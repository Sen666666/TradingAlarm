"""Fail-closed independent review + parent release + per-window O_EXCL lock."""
import os, json
from pathlib import Path
from runtime import O,SOURCE,sha,read,verify_original
SCOPE='ONE_FIXED_PRICE_DMI_PRIORITY_2022_2024_DYNAMIC_STOCK_COMPARISON'
REQUIRED_CODE={'runtime.py','priority.py','dmi_gates.py','run_dmi.py','features.py','run_baseline.py','test_priority.py','report_saved.py'}

def require_release(window):
    assert window in ('2022','2024'),'ONLY_TWO_FIXED_WINDOWS'
    path=O/'ROOT_DMI_AUTHORIZATION.json'
    if not path.exists():raise PermissionError('DMI_LOCKED_AWAITING_PARENT_RELEASE')
    a=read(path)
    assert a.get('explicit_root_authorized') is True and a.get('scope')==SCOPE
    assert a.get('windows')==['2022','2024'] and a.get('authorization_evidence')
    assert a.get('protocol_sha256')==sha(O/'DYNAMIC_PROTOCOL.json')
    audit=O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json'
    assert a.get('implementation_audit_sha256')==sha(audit)
    review=read(audit)
    assert review.get('pre_economic_checks_passed') is True
    assert review.get('reviewed_code_sha256')==a.get('code_sha256')
    assert review.get('reviewed_input_sha256')==a.get('input_sha256')
    assert REQUIRED_CODE <= set(a.get('code_sha256',{})), 'ALL_NEW_CODE_MUST_BE_REVIEWED'
    assert a.get('input_sha256')
    original=read(SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json')
    required_inputs=dict(original['input_sha256'])
    required_inputs.update(read(O/'features/INPUT_SHA256.json'))
    for p in [O/'DYNAMIC_PROTOCOL.json',O/'features/SEAL.json',O/'features/INPUT_SHA256.json',O/'features/QA.json',O/'features/ALL_PRICE_RECEIPT_FEATURES.parquet',SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json',SOURCE/'FINAL_RUN_SEAL.json',O.parent/'price_dmi_priority_preflight_v1/PROTOCOL.json']:
        required_inputs[str(p)]=sha(p)
    assert all(a['input_sha256'].get(p)==h for p,h in required_inputs.items()), 'ALL_ORIGINAL_AND_FEATURE_INPUTS_MUST_BE_REVIEWED'
    for name,h in read(O/'features/SEAL.json').items():
        assert Path(name).name==name, 'FEATURE_SEAL_MUST_BE_LOCAL'
        assert sha(O/'features'/name)==h, ('FEATURE_SEAL_DRIFT',name)
    for name,h in a['code_sha256'].items():assert sha(O/name)==h,('NEW_CODE_DRIFT',name)
    for path,h in a['input_sha256'].items():assert sha(path)==h,('NEW_INPUT_DRIFT',path)
    for w in ('2022','2024'):
        q=O/('baseline_exact_'+w)/'EXACT_QA.json'
        assert read(q)['result']=='PASS_ORIGINAL_JOINT_EXACT'
        assert review.get('baseline_qa_sha256',{}).get(w)==sha(q),'BASELINE_NOT_REVIEWED'
    assert review.get('feature_seal_sha256')==sha(O/'features/SEAL.json')
    verify_original()
    return dict(a,authorization_sha256=sha(O/'ROOT_DMI_AUTHORIZATION.json'))

def claim_once(window,a):
    p=O/('DMI_RUN_ONCE_'+window+'.json')
    fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:
        json.dump(dict(window=window,scope=SCOPE,authorization_sha256=a['authorization_sha256'],protocol_sha256=a['protocol_sha256'],retry=False),f,indent=2)
    return p
