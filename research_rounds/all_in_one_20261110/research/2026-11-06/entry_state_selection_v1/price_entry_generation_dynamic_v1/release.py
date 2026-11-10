"""Independent-review + explicit-parent-release + per-window once locks."""
import os,json
from runtime import O,SOURCE,sha,read,verify_original
SCOPE='ONE_FIXED_PRICE_ENTRY_GENERATION_2022_2024_DYNAMIC_STOCK_COMPARISON'
REQUIRED_CODE={'runtime.py','generation.py','build_market_tape.py','entry_gate.py','release.py','run_gate.py','test_gate.py','freeze.py'}

def require_release(window):
    assert window in ('2022','2024'),'ONLY_TWO_WINDOWS'
    p=O/'ROOT_ENTRY_GATE_AUTHORIZATION.json'
    if not p.exists():raise PermissionError('ENTRY_GATE_LOCKED_AWAITING_PARENT_RELEASE')
    a=read(p);assert a.get('explicit_root_authorized') is True and a.get('scope')==SCOPE
    assert a.get('windows')==['2022','2024'] and a.get('authorization_evidence')
    assert a.get('protocol_sha256')==sha(O/'PROTOCOL.md')
    audit=O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json';assert a.get('implementation_audit_sha256')==sha(audit)
    review=read(audit);assert review.get('pre_economic_checks_passed') is True
    assert review.get('reviewed_code_sha256')==a.get('code_sha256')==read(O/'FREEZE_CODE_SHA256.json')
    assert review.get('reviewed_input_sha256')==a.get('input_sha256')==read(O/'FREEZE_INPUT_SHA256.json')
    assert REQUIRED_CODE<=set(a['code_sha256'])
    for name,h in a['code_sha256'].items():assert sha(O/name)==h,('NEW_CODE_DRIFT',name)
    for path,h in a['input_sha256'].items():assert sha(path)==h,('NEW_INPUT_DRIFT',path)
    original=read(SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json')
    assert all(a['input_sha256'].get(p)==h for p,h in original['input_sha256'].items()),'ORIGINAL_INPUTS_NOT_SEALED'
    for name,h in read(O/'market_tape/SEAL.json').items():assert sha(O/'market_tape'/name)==h,('TAPE_SEAL_DRIFT',name)
    assert review.get('market_tape_seal_sha256')==sha(O/'market_tape/SEAL.json')
    assert read(O/'TEST_QA.json')['passed'] is True
    verify_original()
    return dict(a,authorization_sha256=sha(p))

def claim_once(window,a):
    p=O/('ENTRY_GATE_RUN_ONCE_'+window+'.json');fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:json.dump(dict(window=window,scope=SCOPE,authorization_sha256=a['authorization_sha256'],protocol_sha256=a['protocol_sha256'],retry=False),f,indent=2)
    return p
