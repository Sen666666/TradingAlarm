"""Freeze code, references and potential inputs before review. No account replay."""
from pathlib import Path
import json,time,re,hashlib
import mask_bridge as M
from runner import save,read
HERE=Path(__file__).resolve().parent;E=M.E
U=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
AS=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v1/actions')

def hash_stream(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        while chunk:=f.read(1024*1024):h.update(chunk)
    return h.hexdigest()
def main():
    start=time.monotonic();source_seal=read(E.bridge.HERE/'SOURCE_MANIFEST.json')
    potential=M.merge_hashes(source_seal['sha256'],read(M.BASE/'cohort_2024_924/SOURCE_HASHES.json'))
    manifests=read(U);assert len(manifests)==1709
    for m in manifests:potential=M.merge_hashes(potential,m['source_sha256'],m['output_sha256'])
    absent=[]
    for m in manifests:
        p=AS/(m['symbol']+'.json')
        if not p.exists():absent.append(str(p));continue
        potential=M.merge_hashes(potential,{str(p):hash_stream(p)})
        data=read(p)
        for e in data.get('coverage_evidence',[]):
            if Path(e['path']).exists():potential=M.merge_hashes(potential,{e['path']:e['sha256']})
    fixed={str(p):hash_stream(p) for p in [U,M.OLD_MANIFEST,E.bridge.HERE/'SOURCE_MANIFEST.json',M.BASE/'COHORT_EXECUTION_CONTRACT_V3.json',E.bridge.EVENT_ROOT/'relative_priority_equity_rebuild_v1/FIRST_ACTION_ROUND_MAP_2024.csv']}
    fixed[str(HERE/'REPORT_ADDENDUM.json')]=hash_stream(HERE/'REPORT_ADDENDUM.json')
    for p in (M.BASE/'cohort_2024_924').iterdir():
        if p.is_file():fixed[str(p)]=hash_stream(p)
    code=M.merge_hashes(read(M.BASE/'COHORT_EXECUTION_CONTRACT_V3.json')['code_hashes'],{str(p):hash_stream(p) for p in HERE.glob('*.py')})
    code[str(E.bridge.EVENT_ROOT/'cash_equity_baseline_2024_v1/engine.py')]=hash_stream(E.bridge.EVENT_ROOT/'cash_equity_baseline_2024_v1/engine.py')
    code[str(HERE/'RUN_CONTRACT.json')]=hash_stream(HERE/'RUN_CONTRACT.json')
    checked=M.merge_hashes(potential,fixed,code)
    for n,(p,h) in enumerate(checked.items()):
        assert hash_stream(p)==h,('PREFLIGHT_INPUT_DRIFT',p)
        if n%2000==0:print('INPUT_HASH',n,'/',len(checked),flush=True)
    for p in absent:assert not Path(p).exists()
    overlap=set(read(M.BASE/'cohort_2024_924/SOURCE_HASHES.json'))&set(code)
    assert overlap
    qa_paths=[HERE/n/'RESULT.json' for n in ('qa_synthetic_attempt_01','qa_financial_synthetic_attempt_01','qa_prefix_all1709_attempt_01','qa_prefix_tech407_attempt_01','qa_report_controls_attempt_01')]
    for p in qa_paths:assert read(p)['status']=='PASS'
    qa={str(f):hash_stream(f) for result in qa_paths for f in result.parent.rglob('*') if f.is_file()}
    save(HERE/'FROZEN_INPUTS_V2.json',dict(created_utc=time.time(),code_hashes=code,fixed_file_hashes=fixed,potential_input_hashes=potential,absent_action_files=absent,engineering_QA_hashes=qa,
        preflight_verified_files=len(checked),preflight_seconds=time.monotonic()-start,real_source_code_overlap=sorted(overlap),
        input_verification_policy='All potential expected inputs physically verified before release; runtime consumed sources rehashed and checked against this freeze; missing action paths remain absent.'))
    print('FROZEN',len(checked),time.monotonic()-start)
if __name__=='__main__':main()
