"""Separate technical review from explicit root economic authorization."""
from pathlib import Path
import hashlib
import json
import os

O = Path(__file__).resolve().parent
PROTOCOL_SHA256 = '94965590a1d5ba5fd28e88a6cf6c09188f747663590d2ffa0e3f7858e2265687'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require_specification():
    assert sha(O / 'PROTOCOL_DRAFT.md') == PROTOCOL_SHA256, 'PROTOCOL_DRIFT'
    a = json.loads((O / 'INDEPENDENT_CONTRACT_AUDIT.json').read_text())
    assert a['contract_specification_passed'] is True and a['protocol_sha256'] == PROTOCOL_SHA256
    return a


def require_economic_authorization(window, authorization=None):
    """No default approval, environment switch, CLI flag or SPEC_ONLY bypass."""
    require_specification()
    if window not in ('2022', '2024'):
        raise ValueError('ONLY_FIXED_TWO_WINDOWS')
    path = O / 'ROOT_ECONOMIC_AUTHORIZATION.json'
    if authorization is not None and Path(authorization).resolve() != path.resolve():
        raise PermissionError('ONLY_ROOT_AUTHORIZATION_RECORD_ALLOWED')
    if not path.exists():
        raise PermissionError('NEW_PRICE_ECONOMICS_LOCKED_NO_ROOT_AUTHORIZATION')
    a = json.loads(path.read_text())
    assert a.get('explicit_root_authorized') is True and a.get('scope') == 'ONE_FIXED_2022_2024_JOINT_STOCK_COMPARISON'
    assert a.get('protocol_sha256') == PROTOCOL_SHA256
    assert a.get('windows') == ['2022', '2024'] and a.get('authorization_evidence'), 'ROOT_EVIDENCE_REQUIRED'
    audit = O / 'INDEPENDENT_PRE_ECONOMIC_AUDIT.json'
    assert a.get('implementation_audit_sha256') == sha(audit)
    review = json.loads(audit.read_text())
    assert review.get('pre_economic_checks_passed') is True, 'IMPLEMENTATION_AUDIT_NOT_PASS'
    assert review.get('protocol_sha256') == PROTOCOL_SHA256
    assert review.get('reviewed_code_sha256') == a.get('code_sha256'), 'CODE_MUST_MATCH_INDEPENDENTLY_REVIEWED_HASHES'
    assert review.get('reviewed_input_sha256') == a.get('input_sha256'), 'INPUTS_MUST_MATCH_INDEPENDENTLY_REVIEWED_HASHES'
    required = {'joint_engine.py', 'joint_policy.py', 'execution_book.py', 'market_adapter.py',
                'baseline_regression.py', 'reporting.py', 'gates.py'}
    assert required <= set(a.get('code_sha256', {})), 'ALL_IMPLEMENTATION_HASHES_REQUIRED'
    for name, digest in a['code_sha256'].items():
        assert sha(O / name) == digest, ('CODE_DRIFT', name)
    assert a.get('input_sha256'), 'FROZEN_INPUT_MANIFEST_REQUIRED'
    for name, digest in a['input_sha256'].items():
        p = Path(name)
        assert sha(p if p.is_absolute() else O / p) == digest, ('INPUT_DRIFT', name)
    return dict(a, authorization_sha256=sha(path))


def claim_run_once(window, authorization):
    """Must execute before any PRICE lifecycle, never overwrite a failed attempt."""
    p = O / ('ECONOMIC_RUN_ONCE_' + window + '.json')
    fd = os.open(p, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(dict(window=window, authorization_sha256=authorization['authorization_sha256'],
                       protocol_sha256=PROTOCOL_SHA256, economic_proxy='CONDITIONAL_NEXT_COMMON_OPEN_FULL_FILL_V1'), f, indent=2)
        f.write('\n')
    return p
