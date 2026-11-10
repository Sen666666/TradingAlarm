"""Verify inherited immutable input seal and freeze new code before independent review."""
from pathlib import Path
import hashlib,json,time
HERE=Path(__file__).resolve().parent;P=HERE.parent/'tech407_admission_mask_ablation_v1'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        while c:=f.read(1024*1024):h.update(c)
    return h.hexdigest()
def main():
    started=time.monotonic();old=read(P/'FROZEN_INPUTS_V2.json')
    result={k:dict(old[k]) for k in ('code_hashes','fixed_file_hashes','potential_input_hashes')}
    result['engineering_QA_hashes']={str(HERE/'SYNTHETIC_QA.json'):sha(HERE/'SYNTHETIC_QA.json')}
    assert read(HERE/'SYNTHETIC_QA.json')['status']=='PASS'
    for p in list(HERE.glob('*.py'))+[HERE/'RUN_CONTRACT.json']:
        result['code_hashes'][str(p)]=sha(p)
    for p in [P/'FROZEN_INPUTS_V2.json',P/'TOTAL_OUTPUT_SEAL.json',P/'BASELINE_EXACT_EQUIVALENCE.json',P/'RUN_CONTRACT.json']+list((P/'run_all1709_once').glob('*')):
        if p.is_file():result['fixed_file_hashes'][str(p)]=sha(p)
    allhash={}
    for k in ('code_hashes','fixed_file_hashes','potential_input_hashes','engineering_QA_hashes'):
        for p,h in result[k].items():
            assert p not in allhash or allhash[p]==h,('CONFLICT',p)
            allhash[p]=h
    for i,(p,h) in enumerate(allhash.items()):
        assert sha(p)==h,('FROZEN_INPUT_DRIFT',p)
        if i%2000==0:print('HASH',i,'/',len(allhash),flush=True)
    result['absent_action_files']=old['absent_action_files']
    for p in result['absent_action_files']:assert not Path(p).exists(),('NEW_EVIDENCE_NOT_ALLOWED',p)
    result.update(verified_files=len(allhash),seconds=time.monotonic()-started,economic_replay=False,baseline=str(P/'run_all1709_once'),original_freeze_sha256=sha(P/'FROZEN_INPUTS_V2.json'))
    with (HERE/'FROZEN_INPUTS_V2.json').open('x') as f:json.dump(result,f,ensure_ascii=False,indent=2)
    print('FROZEN',len(allhash),'seconds',result['seconds'],'hash',sha(HERE/'FROZEN_INPUTS_V2.json'),flush=True)
if __name__=='__main__':main()
