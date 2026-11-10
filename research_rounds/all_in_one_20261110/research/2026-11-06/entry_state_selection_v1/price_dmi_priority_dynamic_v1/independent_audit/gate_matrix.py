"""Synthetic release-gate matrix. All authorization/filesystem reads are mocked."""
from pathlib import Path
import copy,io,json,os,sys
from unittest.mock import patch
O=Path(__file__).resolve().parents[1];A=Path(__file__).resolve().parent
sys.dont_write_bytecode=True;sys.path.insert(0,str(O))
import dmi_gates as g
N=Path('/SYNTHETIC_NO_REAL_RELEASE/new');S=Path('/SYNTHETIC_NO_REAL_RELEASE/old')
root=N/'ROOT_DMI_AUTHORIZATION.json';audit=N/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json'
H={};F={}
def digest(p):
    p=str(p);H.setdefault(p,'hash:'+p);return H[p]
def put(p,v):F[str(p)]=v;digest(p)
code={n:digest(N/n) for n in sorted(g.REQUIRED_CODE)}
inputs={'/SYNTHETIC/source':digest('/SYNTHETIC/source')}
put(S/'ROOT_ECONOMIC_AUTHORIZATION.json',{'input_sha256':inputs.copy()})
put(N/'features/INPUT_SHA256.json',{'/SYNTHETIC/feature_source':digest('/SYNTHETIC/feature_source')})
inputs.update(F[str(N/'features/INPUT_SHA256.json')])
for p in [N/'DYNAMIC_PROTOCOL.json',N/'features/SEAL.json',N/'features/INPUT_SHA256.json',N/'features/QA.json',N/'features/ALL_PRICE_RECEIPT_FEATURES.parquet',S/'ROOT_ECONOMIC_AUTHORIZATION.json',S/'FINAL_RUN_SEAL.json',N.parent/'price_dmi_priority_preflight_v1/PROTOCOL.json']:
    inputs[str(p)]=digest(p)
put(N/'features/SEAL.json',{'ALL_PRICE_RECEIPT_FEATURES.parquet':digest(N/'features/ALL_PRICE_RECEIPT_FEATURES.parquet')})
base={}
for w in ['2022','2024']:
    p=N/('baseline_exact_'+w)/'EXACT_QA.json';put(p,{'result':'PASS_ORIGINAL_JOINT_EXACT'});base[w]=digest(p)
auth=dict(explicit_root_authorized=True,scope=g.SCOPE,windows=['2022','2024'],authorization_evidence='SYNTHETIC_FIXTURE_ONLY',protocol_sha256=digest(N/'DYNAMIC_PROTOCOL.json'),implementation_audit_sha256=digest(audit),code_sha256=code,input_sha256=inputs)
review=dict(pre_economic_checks_passed=True,reviewed_code_sha256=copy.deepcopy(code),reviewed_input_sha256=copy.deepcopy(inputs),baseline_qa_sha256=base,feature_seal_sha256=digest(N/'features/SEAL.json'))
put(root,auth);put(audit,review)
originalF=copy.deepcopy(F);originalH=copy.deepcopy(H)
results=[]
def run(name,mutation=None,expected=True,exists=True,original_ok=True,window='2022'):
    f=copy.deepcopy(originalF);h=copy.deepcopy(originalH)
    if mutation:mutation(f,h)
    def read(p):return copy.deepcopy(f[str(p)])
    def sha(p):return h[str(p)]
    def orig():
        if not original_ok:raise AssertionError('FROZEN_ORIGINAL_CHANGED')
    with patch.object(g,'O',N),patch.object(g,'SOURCE',S),patch.object(g,'read',side_effect=read),patch.object(g,'sha',side_effect=sha),patch.object(g,'verify_original',side_effect=orig),patch.object(Path,'exists',return_value=exists):
        try:
            x=g.require_release(window)
            if not expected:raise RuntimeError('ACCEPTED_BAD_FIXTURE:'+name)
            assert x['authorization_sha256']==h[str(root)]
            result='VALID_SYNTHETIC_ACCEPTED'
        except (AssertionError,PermissionError,KeyError) as e:
            if expected:raise
            result=type(e).__name__+':'+str(e)
    results.append(dict(name=name,result=result))
def aa(f):return f[str(root)]
def rr(f):return f[str(audit)]
run('valid_complete_fixture')
run('missing_root',expected=False,exists=False)
run('unsupported_window',expected=False,window='2026')
for key,value in [('explicit_root_authorized',False),('scope','OLD_SCOPE'),('windows',['2022']),('authorization_evidence',''),('protocol_sha256','drift'),('implementation_audit_sha256','drift')]:
    run('bad_'+key,lambda f,h,k=key,v=value:aa(f).__setitem__(k,v),False)
run('audit_not_pass',lambda f,h:rr(f).__setitem__('pre_economic_checks_passed',False),False)
run('audit_code_disagrees',lambda f,h:rr(f)['reviewed_code_sha256'].__setitem__('priority.py','drift'),False)
run('audit_inputs_disagree',lambda f,h:rr(f)['reviewed_input_sha256'].__setitem__('/SYNTHETIC/source','drift'),False)
def omitcode(f,h):
    aa(f)['code_sha256'].pop('priority.py');rr(f)['reviewed_code_sha256'].pop('priority.py')
run('required_code_missing_on_both_sides',omitcode,False)
def omitinput(f,h):
    aa(f)['input_sha256'].pop('/SYNTHETIC/source');rr(f)['reviewed_input_sha256'].pop('/SYNTHETIC/source')
run('original_input_missing_on_both_sides',omitinput,False)
run('current_code_drift',lambda f,h:h.__setitem__(str(N/'priority.py'),'drift'),False)
run('current_input_drift',lambda f,h:h.__setitem__('/SYNTHETIC/source','drift'),False)
run('feature_seal_artifact_drift',lambda f,h:f[str(N/'features/SEAL.json')].__setitem__('ALL_PRICE_RECEIPT_FEATURES.parquet','drift'),False)
run('feature_path_escape',lambda f,h:f[str(N/'features/SEAL.json')].__setitem__('../escape','drift'),False)
run('baseline_not_exact',lambda f,h:f[str(N/'baseline_exact_2024/EXACT_QA.json')].__setitem__('result','FAIL'),False)
run('unreviewed_baseline_qa',lambda f,h:rr(f)['baseline_qa_sha256'].__setitem__('2024','drift'),False)
run('feature_seal_not_reviewed',lambda f,h:rr(f).__setitem__('feature_seal_sha256','drift'),False)
run('frozen_original_drift',expected=False,original_ok=False)
# Exercise actual locking function with mocked descriptors only. No real lock created.
class Buffer(io.StringIO):
    def close(self):pass
b=Buffer()
with patch.object(g,'O',N),patch.object(g.os,'open',side_effect=[999,FileExistsError('synthetic already claimed')]) as op,patch.object(g.os,'fdopen',return_value=b):
    p=g.claim_once('2022',dict(authorization_sha256='SYNTHETIC',protocol_sha256='SYNTHETIC'))
    assert op.call_args.args==(N/'DMI_RUN_ONCE_2022.json',os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    assert json.loads(b.getvalue())['retry'] is False
    try:g.claim_once('2022',dict(authorization_sha256='SYNTHETIC',protocol_sha256='SYNTHETIC'))
    except FileExistsError:pass
    else:raise AssertionError('SECOND_CLAIM_NOT_BLOCKED')
results.append(dict(name='atomic_claim_no_retry',result='O_EXCL_MODE_0600_AND_SECOND_CLAIM_REJECTED_NO_REAL_WRITE'))
out=dict(status='PASS_SYNTHETIC_RELEASE_GATES',cases=len(results),results=results,real_authorization_created=False,real_locks_created=False,economic_runs=0,gate_sha256=__import__('hashlib').sha256((O/'dmi_gates.py').read_bytes()).hexdigest())
with (A/'GATE_MATRIX.json').open('x') as f:json.dump(out,f,indent=2)
print(json.dumps(out,indent=2))
