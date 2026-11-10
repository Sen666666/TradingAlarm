"""Separate, fail-closed new-cohort authorization. Never edits or calls old gates."""
from pathlib import Path
import hashlib,json,os
from cohort_config import O,CONFIG
PROTOCOL_SHA256=hashlib.sha256((O/'PROTOCOL.md').read_bytes()).hexdigest()
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def require_economic_authorization(window,authorization=None):
    if window not in CONFIG:raise ValueError('ONLY_NEW_FROZEN_WINDOWS')
    path=O/'ROOT_EXTENSION_AUTHORIZATION.json'
    if authorization is not None and Path(authorization).resolve()!=path:raise PermissionError('ONLY_NEW_PARENT_AUTHORIZATION')
    if not path.exists():raise PermissionError('NEW_COHORT_PARENT_AUTHORIZATION_REQUIRED')
    a=json.loads(path.read_text());assert a['explicit_root_authorized'] is True
    assert a['scope']=='TWO_INDEPENDENT_NEW_COHORTS_ORIGINAL_2024_TEMPLATE_165_ONLY'
    assert a['windows']==['2023','2024JanAug'] and a['authorization_evidence']
    assert a['protocol_sha256']==sha(O/'PROTOCOL.md')==PROTOCOL_SHA256
    rp=O/'INDEPENDENT_EXTENSION_REVIEW.json';assert a['independent_review_sha256']==sha(rp)
    review=json.loads(rp.read_text());assert review['pre_economic_checks_passed'] is True
    assert review['protocol_sha256']==PROTOCOL_SHA256
    assert review['reviewed_code_sha256']==a['code_sha256']
    assert review['reviewed_input_sha256']==a['input_sha256']
    for n,h in a['code_sha256'].items():assert sha(O/n)==h,('CODE_DRIFT',n)
    for p,h in a['input_sha256'].items():assert sha(p)==h,('INPUT_DRIFT',p)
    old=json.loads((O.parent/'OLD_TREE_SHA256_BEFORE.json').read_text())
    for p,h in old.items():assert sha(p)==h,('OLD_TREE_DRIFT',p)
    return dict(a,authorization_sha256=sha(path))
def claim_run_once(window,authorization):
    p=O/('ECONOMIC_RUN_ONCE_'+window+'.json');fd=os.open(p,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as f:json.dump(dict(window=window,authorization_sha256=authorization['authorization_sha256'],protocol_sha256=PROTOCOL_SHA256),f,indent=2)
    return p
