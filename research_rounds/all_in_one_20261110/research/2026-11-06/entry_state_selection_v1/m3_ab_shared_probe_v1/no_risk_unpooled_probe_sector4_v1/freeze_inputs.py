from pathlib import Path
import hashlib,json,time
HERE=Path(__file__).resolve().parent;PREV=HERE.parent/'no_risk_ceilings_python_retry_v1'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while c:=f.read(1024*1024):h.update(c)
 return h.hexdigest()
def main():
 started=time.monotonic();old=json.loads((PREV/'FROZEN_INPUTS_V2.json').read_text());f={k:dict(old[k]) for k in ('code_hashes','fixed_file_hashes','potential_input_hashes','engineering_QA_hashes')}
 for p in list(HERE.glob('*.py'))+[HERE/'launch.sh',HERE/'RUN_CONTRACT.json']:
  f['code_hashes'][str(p)]=sha(p)
 for p in [PREV/'FROZEN_INPUTS_V2.json',PREV/'RUN_CONTRACT.json',PREV/'INDEPENDENT_REVIEW_RELEASE.json']+list((PREV/'run_no_risk_ceilings_once').iterdir()):
  if p.is_file():f['fixed_file_hashes'][str(p)]=sha(p)
 assert json.loads((HERE/'SYNTHETIC_QA.json').read_text())['status']=='PASS'
 f['engineering_QA_hashes'][str(HERE/'SYNTHETIC_QA.json')]=sha(HERE/'SYNTHETIC_QA.json')
 allhash={}
 for k in ('code_hashes','fixed_file_hashes','potential_input_hashes','engineering_QA_hashes'):
  for p,h in f[k].items():
   assert p not in allhash or allhash[p]==h,('HASH_CONFLICT',p)
   allhash[p]=h
 for i,(p,h) in enumerate(allhash.items()):
  assert sha(p)==h,('DRIFT',p)
  if i%2000==0:print('HASH',i,'/',len(allhash),flush=True)
 f['absent_action_files']=old['absent_action_files']
 for p in f['absent_action_files']:assert not Path(p).exists()
 f.update(verified_files=len(allhash),seconds=time.monotonic()-started,economic_replay=False,baseline=str(PREV/'run_no_risk_ceilings_once'))
 with (HERE/'FROZEN_INPUTS_V2.json').open('x') as o:json.dump(f,o,indent=2)
 print('FROZEN',sha(HERE/'FROZEN_INPUTS_V2.json'),'CONTRACT',sha(HERE/'RUN_CONTRACT.json'),flush=True)
if __name__=='__main__':main()
