"""Freeze reviewed scope only. Never grants release or executes economics."""
from pathlib import Path
from runtime import O,R,SOURCE,sha,read,save
CODE=['runtime.py','generation.py','build_market_tape.py','entry_gate.py','release.py','run_gate.py','test_gate.py','freeze.py','report_saved.py','cases_saved.py']
def main():
    assert read(O/'TEST_QA.json')['passed']
    assert read(O/'market_tape/QA.json')['receipts']==37456
    inputs=dict(read(SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json')['input_sha256'])
    for p in [SOURCE/'ROOT_ECONOMIC_AUTHORIZATION.json',SOURCE/'FINAL_RUN_SEAL.json',R/'price_entry_generation_gate_preflight_v1/PROTOCOL.md',R/'price_entry_generation_gate_preflight_v1/FREEZE.json',R/'price_entry_generation_gate_preflight_v1/diagnose.py',R/'old_result_association_v1/COMMON_167_DENY_BUYS.csv',O/'PROTOCOL.md',O/'TEST_QA.json',O/'ORIGINAL_INTEGRITY_AFTER_INTERRUPTED_TEST.json',O/'TEST_SETUP_RECOVERY.md',O/'SETUP_FAILURE_REPRESENTATION_QA.json',O/'REUSED_REPORT_RIGHTS_QA.json',O/'REPORT_PREFLIGHT_QA.json',O/'SETUP_153_EXACT_QA.json']:
        inputs[str(p)]=sha(p)
    for d in [O/'market_tape',O/'setup_attempt01',O/'test_setup_attempt01',O/'audit_contract_attempt01',O/'report_wording_attempt01',O/'independent_audit']:
        for p in d.rglob('*'):
            if p.is_file():inputs[str(p)]=sha(p)
    for w in ['2022','2024']:
        d=R/'price_dmi_priority_dynamic_v1'/('baseline_exact_'+w)
        for p in d.rglob('*'):
            if p.is_file():inputs[str(p)]=sha(p)
    save(O/'FREEZE_CODE_SHA256.json',{n:sha(O/n) for n in CODE});save(O/'FREEZE_INPUT_SHA256.json',inputs)
    save(O/'FREEZE.json',dict(protocol_sha256=sha(O/'PROTOCOL.md'),code_manifest_sha256=sha(O/'FREEZE_CODE_SHA256.json'),input_manifest_sha256=sha(O/'FREEZE_INPUT_SHA256.json'),economic_authorized=False,economic_runs=0,code_files=len(CODE),input_files=len(inputs)))
    print('FROZEN_AWAITING_INDEPENDENT_REVIEW_AND_PARENT_RELEASE',flush=True)
if __name__=='__main__':main()
