"""Final independent pre-economic signoff. Never runs a consumer."""
from pathlib import Path
import csv,hashlib,itertools,json,math,os,sys,time
from decimal import Decimal
O=Path(__file__).resolve().parents[1];A=Path(__file__).resolve().parent
sys.dont_write_bytecode=True;sys.path.insert(0,str(O))
from runtime import SOURCE,verify_original
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def exact_cell(x,y):
    if x==y:return True
    if x=='' or y=='':return False
    try:a,b=Decimal(x),Decimal(y);return a.is_finite() and b.is_finite() and a==b
    except Exception:return False
def compare_csv(a,b):
    ah,bh=sha(a),sha(b)
    with a.open(newline='') as af,b.open(newline='') as bf:
        ar,br=csv.reader(af),csv.reader(bf);ac,bc=next(ar),next(br)
        assert ac==bc,('SCHEMA',str(a))
        count=0
        for i,(x,y) in enumerate(itertools.zip_longest(ar,br)):
            assert x is not None and y is not None,('ROWCOUNT',str(a),i)
            assert len(x)==len(y)==len(ac)
            if x!=y:
                for j,(u,v) in enumerate(zip(x,y)):assert exact_cell(u,v),('VALUE_OR_NAN',str(a),i,ac[j],u,v)
            count+=1
    return dict(rows=count,columns=len(ac),ordered_schema_and_rows_exact=True,nan_masks_exact=True,numeric_equality_no_tolerance=True,actual_sha256=ah,reference_sha256=bh,byte_identical=ah==bh)
def compare_json(a,b):
    x,y=read(a),read(b);assert x==y,('NESTED_JSON',str(a))
    return dict(rows=len(x),nested_exact=True,actual_sha256=sha(a),reference_sha256=sha(b))
def save_exclusive_atomic(p,obj):
    temp=Path(str(p)+'.tmp')
    with temp.open('x') as f:
        json.dump(obj,f,indent=2,ensure_ascii=False,allow_nan=False,default=str);f.write('\n');f.flush();os.fsync(f.fileno())
    os.link(temp,p) # Atomic no-overwrite publication; original files untouched.
    temp.unlink()
def main():
    # Do not make a technical PASS available before both completed exact replays.
    for w in ['2022','2024']:
        assert read(O/('baseline_exact_'+w)/'EXACT_QA.json')['result']=='PASS_ORIGINAL_JOINT_EXACT',('BASELINE_NOT_READY',w)
    assert not (O/'ROOT_DMI_AUTHORIZATION.json').exists(),'SIGNOFF_MUST_PRECEDE_PARENT_RELEASE'
    assert not any((O/('DMI_RUN_ONCE_'+w+'.json')).exists() for w in ['2022','2024'])
    code=read(O/'REVIEW_CODE_SHA256_v3.json');inputs=read(O/'REVIEW_INPUT_SHA256.json')
    recovery=O/'recover_baseline_qa.py'
    assert sha(recovery)=='04bcee626a8bd860b2f6cd401d0362b0c50c788aa5639b48388aeb869ded2ed3'
    normalized_inputs={str(Path(p).resolve()):h for p,h in inputs.items()}
    assert all(normalized_inputs[str(Path(p).resolve())]==h for p,h in inputs.items())
    for n,h in code.items():assert sha(O/n)==h,('REVIEWED_CODE_DRIFT',n)
    for p,h in inputs.items():assert sha(p)==h,('REVIEWED_INPUT_DRIFT',p)
    original=verify_original()
    component=read(A/'COMPONENT_CHECKS.json');gate=read(A/'GATE_MATRIX.json')
    for n,h in component['reviewed_components'].items():assert sha(O/n)==h
    assert gate['gate_sha256']==sha(O/'dmi_gates.py')
    selftest=read(O/'POSTERIOR_JOINT_SELF_COMPARISON_QA.json')
    assert selftest['report_code_sha256']==sha(O/'report_saved.py')
    assert selftest['result']=='PASS_ORIGINAL_JOINT_SELF_COMPARISON'
    checks={};qa={}
    tables=['ROUNDS','ACTIONS','DECISIONS','RANKING_AUDIT','END_STATES','REGISTRATIONS','CLAIM_LEDGER','PROFIT_GATES']
    for w in ['2022','2024']:
        dest=O/('baseline_exact_'+w);ref=SOURCE/('economic_'+w)
        c={n:compare_csv(dest/'joint'/(n+'.csv'),ref/'joint'/(n+'.csv')) for n in tables}
        for n in ['CLAIMS','BRIDGES','LEDGER_QA','SOURCE_HASHES']:c[n]=compare_json(dest/'joint'/(n+'.json'),ref/'joint'/(n+'.json'))
        for n in ['PRICE_AUDIT','OFFER_AUDIT','AB_DECISION_AUDIT','FROZEN_RESPONSIBILITIES','EXECUTION_BOOKS']:c[n]=compare_json(dest/(n+'.json'),ref/(n+'.json'))
        for n,h in read(dest/'joint/OUTPUT_HASHES.json').items():assert sha(dest/'joint'/n)==h
        for p,h in read(dest/'joint/SOURCE_HASHES.json').items():assert normalized_inputs[str(Path(p).resolve())]==h and sha(p)==h
        qa[w]=sha(dest/'EXACT_QA.json');checks[w]=c
        print('INDEPENDENT_FULL_JOINT_EXACT',w,{n:x['rows'] for n,x in c.items()},flush=True)
    # Verify no protected code changed during review.
    for n,h in code.items():assert sha(O/n)==h
    protocol=sha(O/'DYNAMIC_PROTOCOL.json')
    out=dict(status='PASS_INDEPENDENT_PRE_ECONOMIC_AUDIT',pre_economic_checks_passed=True,economic_run_permitted=False,release_owner='Explicit parent authorization only, then two separately locked once runs',protocol_sha256=protocol,reviewed_code_sha256=code,reviewed_input_sha256=inputs,baseline_qa_sha256=qa,feature_seal_sha256=sha(O/'features/SEAL.json'),component_checks=component,release_gate_checks=gate,independent_baseline_checks=checks,post_report_selfcheck_sha256=sha(O/'POSTERIOR_JOINT_SELF_COMPARISON_QA.json'),audit_script_sha256=sha(__file__),recovery_qa_driver_sha256=sha(recovery),saved_baseline_independent_evidence={w:sha(A/('SAVED_BASELINE_'+w+'.json')) for w in ['2022','2024']},economic_runs_by_auditor=0,original_code_inputs_outputs_unchanged=True,known_limitations=['Previously seen development data; not untouched out-of-sample validation.','Conditional next-common-OPEN full-fill per-stock proxy, not actual tradability or shared-cash account return.','DMI slot protection is within each current dynamic queue. PRICE state changes can indirectly change later AB entry identities and UNKNOWN chains.','All 1709 fixed stocks, known participants, financially covered closed rounds and common comparable stocks are distinct denominators.','Post-run release requires sealed snapshot integrity, independent rank reconstruction, AB retained-event exactness, UNKNOWN reconciliation and review of every adapter blocker.','2026 birth economics prohibited; 2026 holdings/equity tail remains original through June 30.'],resolved_findings=[dict(severity='HIGH',finding='New code/input drift was not reverified after loop and rank audit followed legacy completion marker',resolution='run_dmi requires identical release after loop and before final seal; rank audit precedes ledger dump; complete snapshot marker binds full output seal'),dict(severity='HIGH',finding='Dynamic domain could exceed 6528 static rows',resolution='37456 receipt keys exact; 1633 source hashes, 1628 source-identity/prefix checks and 48 independent scalar samples'),dict(severity='MEDIUM',finding='Status-only UNKNOWN and absent retained AB path check could understate liabilities or mask economic drift',resolution='v3 report uses stock liability, reconciles round/book status, excludes unresolved books from closed denominators, adds retained AB exact check; exceptions remain report blockers')])
    save_exclusive_atomic(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json',out)
    save_exclusive_atomic(A/'FINAL_AUDIT_BRIEF.json',dict(status=out['status'],audit_sha256=sha(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json'),pre_economic_checks_passed=True,economic_run_permitted=False,baseline_qa_sha256=qa,code_manifest_sha256=sha(O/'REVIEW_CODE_SHA256_v3.json'),input_manifest_sha256=sha(O/'REVIEW_INPUT_SHA256.json'),economic_runs_by_auditor=0))
    print('INDEPENDENT_AUDIT_PASS_AWAITING_PARENT_RELEASE',sha(O/'INDEPENDENT_PRE_ECONOMIC_AUDIT.json'),flush=True)
if __name__=='__main__':main()
