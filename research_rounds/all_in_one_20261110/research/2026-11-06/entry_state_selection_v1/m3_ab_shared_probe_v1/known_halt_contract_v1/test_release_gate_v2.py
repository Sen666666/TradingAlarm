"""Synthetic gate files only; never grants admission to the actual research directory."""
from pathlib import Path
import json,sys
from release_gate_v2 import digest,load_reviewed_contract
import cohort_runner_known_halt_v2 as runner
ROOT=Path(__file__).resolve().parent
out=ROOT/'gate_v2_targeted_qa';out.mkdir(exist_ok=False)
mock=out/'SYNTHETIC_GATE_FIXTURE_NOT_REAL_APPROVAL';mock.mkdir()
def save(path,v):path.write_text(json.dumps(v,indent=2)+'\n')
contract=mock/'RECOVERY_COHORT_CONTRACT_V2.json';save(contract,dict(seed='1200000',cohorts={'2022':{}},code_hashes={}))
payload=mock/'payload.txt';payload.write_text('SYNTHETIC')
seal=mock/'PRE_RUN_STAGE_SEAL_V2.json';save(seal,{p.name:digest(p.read_bytes()) for p in [contract,payload]})
release=mock/'INDEPENDENT_REVIEW_RELEASE.json';save(release,dict(status='PASS',scope='RUN_2022_COHORT_ONCE',reviewed_stage_sha256=digest(seal.read_bytes()),synthetic_test_only=True))
assert load_reviewed_contract(mock)['seed']=='1200000'
runner.HERE=mock;sys.argv=['SYNTHETIC_GATE_TEST','2022']
results=[]
def rejects(name,phrase):
    try:runner.run()
    except (ValueError,FileNotFoundError) as e:assert phrase in str(e),(name,str(e))
    else:raise AssertionError('Admission gate unexpectedly allowed execution')
    assert not (mock/'cohort_2022_recovery_v2').exists()
    results.append(dict(name=name,status='PASS',no_output_directory=True))
original=contract.read_bytes();contract.write_bytes(original.replace(b'1200000',b'9999999'))
rejects('changed_contract_bytes_rejected_before_output_creation','Reviewed stage dependency changed')
contract.write_bytes(original);payload.write_text('CHANGED_SYNTHETIC')
rejects('changed_sealed_dependency_rejected_before_output_creation','Reviewed stage dependency changed')
payload.write_text('SYNTHETIC');release.rename(mock/'SYNTHETIC_RELEASE_RETAINED_NOT_ACTIVE.json')
rejects('missing_release_rejected_before_output_creation','INDEPENDENT_REVIEW_RELEASE.json')
save(out/'RESULT.json',dict(status='AUTHOR_PASS_PURE_GATE_TESTS',tests=results,full_cohort_executed=False,actual_release_created=False))
save(out/'OUTPUT_SEAL.json',{str(p.relative_to(out)):digest(p.read_bytes()) for p in out.rglob('*') if p.is_file()})
print(results)
