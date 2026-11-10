"""Persisted ACTION metadata verification and registered crossprocess restores."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
O=Path(__file__).resolve().parent;UP=O.parent/'C-rights-Jan12-upgrade-v1-20261102'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
def main():
 tests=[]
 def check(n,v,d=None):tests.append(dict(check=n,passed=bool(v),detail=d));assert v,(n,d)
 begun=time.monotonic();identity=read(O/'ACTION_IDENTITY.json');f=read(O/'SOURCE_FREEZE.json');bank=read(O/'OUTPUT_REGISTRY.json');done=read(O/'ACTION_COMPLETION.json');authority=read(O/'EXECUTION_AUTHORITY.json');regsha=sha(O/'OUTPUT_REGISTRY.json')
 check('all frozen sources unchanged',all(sha(p)==h for p,h in f['sources'].items()),len(f['sources']))
 check('Jan12 original registry unchanged',sha(UP/'UPGRADED_CHECKPOINTS.json')==identity['Jan12_registry_sha256'])
 check('Jan12 whole original package index unchanged',sha(UP/'PACKAGE_SHA256.json')==identity['original_upgrade_package_sha256'])
 check('exact two ACTION outputs and zero other execution',done['committed_ACTIONs']==2 and done['OPEN_CLOSE_events']==done['accounts_2025_opened']==done['original_writes']==0 and len(bank['outputs'])==2)
 check('output registry trusted identity',bank['identity_sha256']==sha(O/'ACTION_IDENTITY.json') and done['registry_sha256']==regsha)
 cases=[]
 for rec in bank['outputs']:
  arm=rec['arm'];entry=identity['arms'][arm];ev=read(rec['evidence_file']);grant=authority['arms'][arm];g=read(grant['path'])
  check(arm+' exact immutable Jan12 input',rec['input_checkpoint_sha256']==entry['sha256'] and sha(entry['checkpoint'])==entry['sha256'])
  check(arm+' exact trusted approved grant',g['parent_approved'] and sha(grant['path'])==grant['sha256']==rec['grant_sha256'] and g['input_checkpoint_sha256']==entry['sha256'])
  check(arm+' checkpoint/provenance/evidence bytes',all(sha(p)==h for p,h in [(rec['checkpoint'],rec['sha256']),(str(Path(rec['checkpoint']).with_suffix('.provenance.json')),rec['provenance_sha256']),(rec['state_file'],rec['state_file_sha256']),(rec['evidence_file'],rec['evidence_file_sha256'])]))
  check(arm+' legal ACTION cursor only',rec['phase']=='ACTION' and rec['cursor']=='2022-01-13T00:00:00+08:00' and ev['events_added']==1 and ev['OPEN_CLOSE_executed']==0)
  check(arm+' all financial strategy budget obligations exact',ev['conservation_before']==ev['conservation_after']==entry['conservation_sha256'])
  check(arm+' complete field diff contains no undeclared changes',not ev['diff']['unexpected'] and ev['diff']['all_other_fields_exact'],ev['diff'])
  check(arm+' old14 certificate share recomputed',len(ev['certificates'])==7 and {x['known_at'][:10] for x in ev['certificates']}=={'2022-01-04','2022-01-05','2022-01-06','2022-01-07','2022-01-10','2022-01-11','2022-01-12'})
  check(arm+' actual rights inventory/share ratio unchanged',ev['before_coordinate']['owned_shares']==ev['after_coordinate']['owned_shares'] and ev['before_coordinate']['actual_share_ratio']==ev['after_coordinate']['actual_share_ratio'])
  command=[sys.executable,'-B',str(O/'restore_action.py'),'--checkpoint',rec['checkpoint'],'--registry-sha',regsha]
  result=subprocess.run(command,cwd=O,capture_output=True,text=True);(O/(arm+'-RESTORE.stderr.txt')).write_text(result.stderr)
  check(arm+' independent-process registered restore passed',result.returncode==0,result.stderr[-1200:] if result.returncode else None)
  data=json.loads(result.stdout);(O/(arm+'-RESTORE.json')).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
  check(arm+' duplicate ACTION is exact no-op',data['duplicate_ACTION']=='already_applied' and data['all_post_fields_exact'] and data['extra_historical_events']==0)
  check(arm+' strict output/Jan12 registries and phases reject',len(data['rejected'])==8,data['rejected'])
  cases.append(dict(arm=arm,before_rights_shares=ev['before_coordinate']['owned_shares'],after_rights_shares=ev['after_coordinate']['owned_shares'],changed_fields=ev['diff']['changed'],old_certificates=7,crossprocess=True))
  print('REGISTERED_RESTORE_EXACT',arm,flush=True)
 check('sources unchanged after crossprocess verification',all(sha(p)==h for p,h in f['sources'].items()))
 (O/'VERIFICATION.json').write_text(json.dumps(dict(passed=True,checks=len(tests),tests=tests,cases=cases,registry_sha256=regsha,seconds=time.monotonic()-begun,additional_historical_events=0),ensure_ascii=False,indent=2)+'\n')
 print('ACTION_VERIFIED',len(tests),'checks',round(time.monotonic()-begun,2),flush=True)
if __name__=='__main__':main()
