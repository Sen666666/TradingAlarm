"""Current approval: two exact Jan13 ACTIONs, immediate persistence, then stop."""
from pathlib import Path
import json,time
import action_runtime as A
O=Path(__file__).resolve().parent
def save(n,x):(O/n).write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 A.require(not (O/'OUTPUT_REGISTRY.json').exists(),'output registry already exists; restore exact trusted output, no replay')
 begun=time.monotonic();outputs=[]
 for arm in ['2022-C10','2022-C_BATCH20']:
  auth=A.authority(arm);print('EXECUTING_ACTION_ONLY',arm,'grant_sha',auth['sha256'],flush=True)
  rec=A.run_one(arm,auth['sha256']);outputs.append(rec)
  bank=dict(identity_sha256=A.sha(O/'ACTION_IDENTITY.json'),source_freeze_sha256=A.sha(O/'SOURCE_FREEZE.json'),outputs=outputs)
  save('OUTPUT_REGISTRY.json',bank);save('PROGRESS.json',dict(completed=[r['arm'] for r in outputs],registry_sha256=A.sha(O/'OUTPUT_REGISTRY.json'),cursor=A.AT.isoformat(),OPEN_CLOSE_events=0))
  print('COMMITTED_REGISTERED_ACTION',arm,rec['sha256'],'registry_sha',A.sha(O/'OUTPUT_REGISTRY.json'),flush=True)
 save('ACTION_COMPLETION.json',dict(passed=True,committed_ACTIONs=len(outputs),OPEN_CLOSE_events=0,accounts_2025_opened=0,original_writes=0,registry_sha256=A.sha(O/'OUTPUT_REGISTRY.json'),seconds=time.monotonic()-begun))
 print('ACTION_PREFIX_STOPPED',len(outputs),round(time.monotonic()-begun,2),flush=True)
if __name__=='__main__':main()
