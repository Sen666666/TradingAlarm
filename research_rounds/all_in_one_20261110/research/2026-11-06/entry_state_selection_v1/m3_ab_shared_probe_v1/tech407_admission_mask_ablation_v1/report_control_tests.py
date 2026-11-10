"""Pure report and single-run gate fixtures; no source/account engine loading."""
from pathlib import Path
import copy,json
import analyze_outputs_v2 as A
from runner import save
HERE=Path(__file__).resolve().parent;out=HERE/'qa_report_controls_attempt_01';out.mkdir(exist_ok=False)
checks=[]
for label,rows,expect in [('none',[{'type':'CLOSE_SNAPSHOT'}],0),('zero_liability',[{'type':'UNKNOWN','liability_free_initial':True}],1),('owned_missing_key',[{'type':'UNKNOWN','reason':'OWNED_SOURCE_UNKNOWN'}],0),('owned_false',[{'type':'UNKNOWN','liability_free_initial':False}],0)]:
    assert A.liability_free_unknown_count(rows)==expect;checks.append(label)

def fixture(name):
    root=out/'gate_fixtures'/name;sub=root/'run_all1709_once';sub.mkdir(parents=True)
    save(sub/'ACTIONS.json',[]);save(sub/'OUTPUT_SEAL.json',{'ACTIONS.json':A.M.E.bridge.sha(sub/'ACTIONS.json')})
    qa=dict(resource_pass=True,elapsed_seconds=2,peak_rss_bytes=1000)
    save(sub/'FINAL_RESOURCE_QA.json',qa)
    save(sub/'RUN_STATUS.json',dict(status='COMPLETED_RESOURCE_PASS',elapsed_seconds=2,peak_rss_bytes=1000,output_seal_sha256=A.M.E.bridge.sha(sub/'OUTPUT_SEAL.json'),final_resource_sha256=A.M.E.bridge.sha(sub/'FINAL_RESOURCE_QA.json')))
    exact=dict(all_match=True,baseline_output_seal_sha256=A.M.E.bridge.sha(sub/'OUTPUT_SEAL.json'),baseline_final_resource_sha256=A.M.E.bridge.sha(sub/'FINAL_RESOURCE_QA.json'),baseline_run_status_sha256=A.M.E.bridge.sha(sub/'RUN_STATUS.json'))
    return root,sub,exact
root,sub,e=fixture('valid');save(root/'BASELINE_EXACT_EQUIVALENCE.json',e);A.require_baseline_gate(root);checks.append('BOUND_VALID_BASELINE_PASS')
for name in ('FAILURE','POST_STATUS_FAILURE','STALE_EXACT_SEAL','MUTATED_PAYLOAD'):
    root,sub,e=fixture(name)
    if name in ('FAILURE','POST_STATUS_FAILURE'):save(sub/(name+'.json'),{'status':'FAILED_NO_RETRY'})
    elif name=='STALE_EXACT_SEAL':e['baseline_output_seal_sha256']='0'*64
    else:(sub/'ACTIONS.json').write_text('["TAMPERED_SYNTHETIC_FIXTURE"]\n')
    save(root/'BASELINE_EXACT_EQUIVALENCE.json',e)
    try:A.require_baseline_gate(root)
    except AssertionError:checks.append(name+'_BLOCKED')
    else:raise AssertionError(name+' incorrectly allowed tech arm')
save(out/'RESULT.json',dict(status='PASS',domain='PURE_REPORT_AND_GATE_SYNTHETIC',tests=checks))
print('PASS_REPORT_CONTROLS',len(checks))
