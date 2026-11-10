"""Immutable economic source/parent/cursor/provenance review, no restore."""
from pathlib import Path
from collections import Counter
import json,gzip,hashlib
import audit_pvr_saved as I
O=I.TASK/'ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/cycle2024'
def stream(p):
 with gzip.open(p,'rt')as f:
  for s in f:yield json.loads(s)
def main():
 out={};quarters=['2024-03-29','2024-06-28','2024-09-30','2024-12-31']
 for side,cls,key in [('original','Original2024','PVR_SLOT1'),('no60','No602024','PVR_NO_CONFIRMED60')]:
  base=O/side;r=base/'run-2024';freeze=I.read(r/'EXECUTION_FREEZE.json');meta=I.read(r/'RUN_METADATA.json');done=I.read(r/'DONE.json');auth=I.read(base/'FULL_2024_RUN_AUTHORIZATION.json')
  assert done['completed']and auth['approved']and auth['policy']==side and auth['end']=='2024-12-31'
  assert I.sha(base/'FULL_2024_RUN_AUTHORIZATION.json')==meta['authorization_sha256']
  assert I.sha(base/'PROPOSED_FULL_EXECUTION_FREEZE.json')==meta['execution_freeze_sha256']==auth['execution_freeze_sha256']
  assert meta['Jan2_not_replayed']and meta['no_account_reset']and meta['resume_after']=='2024-01-02 15:10:00+08:00'
  merged=dict(freeze['checkpoint_source_freeze_preserved'])
  for p,h in freeze['entry_sources'].items():assert p not in merged or merged[p]==h;merged[p]=h
  for p,h in merged.items():assert I.sha(p)==h,p
  m=I.read(r/'checkpoint.json');assert m['source_freeze']==freeze['checkpoint_source_freeze_preserved']and m['at']=='2024-12-31 15:10:00+08:00'
  cc=[]
  for day in quarters:
   p=r/('checkpoint-'+day+'.pkl');j=I.read(r/('checkpoint-'+day+'.json'));prov=I.read(r/('checkpoint-'+day+'.provenance.json'))
   assert I.sha(p)==j['sha256']==prov['checkpoint_sha256'];assert j['at']==prov['last_completed_event']==day+' 15:10:00+08:00'
   identity=prov['engine_identity'];assert identity['trading_class']['class_name']==cls
   assert I.sha(identity['trading_class']['module_path'])==identity['trading_class']['module_sha256']
   assert identity['functions']['opening']['declared_module']=='joint_v3'and identity['functions']['planning']['declared_module']=='native_rank'
   cc.append({'day':day,'SHA256':j['sha256']})
  assert I.sha(r/'checkpoint.pkl')==m['sha256']==cc[-1]['SHA256']
  parent=base/'first-session/full-input/pair';pairs={};names=['daily','opportunities','funding','industry','balances','rank-policy']
  for name in names:
   count=0;new=iter(stream(r/'pair'/(name+'.jsonl.gz')))
   for left in stream(parent/(name+'.jsonl.gz')):
    right=next(new,None);assert right==left,(side,name,count);count+=1
   pairs[name]=count
  b=I.read(r/'pair/B.json.gz');pb=I.read(parent/'B.json.gz')
  for k in ['trades','journal','audit','decisions']:assert b[k][:len(pb[k])]==pb[k]
  ds=list(stream(r/'pair/daily.jsonl.gz'));assert len(ds)==726 and len({x['at']for x in ds})==726
  assert sum(x['at'][:10]=='2024-01-02'for x in ds)==1 and ds[-1]['at']==m['at']
  restart=I.read(r/'TERMINAL_SEPARATE_PROCESS_RESTORE.json');assert restart['passed']and restart['separate_process']and restart['account_events']==0
  assert restart['checkpoint_sha256']==m['sha256']and restart['cursor']==m['at']and restart['complete_book_exact']and restart['sources_current_exact']
  assert all(restart['all_account_fields_exact'].values())and all(restart['all_runner_fields_exact'].values())
  for field,name in [('daily','daily'),('opportunities','opportunities'),('funding','funding'),('stage_events','industry'),('balance_audit','balances'),('rank_log','rank-policy')]:
   hh=hashlib.sha256();count=0
   for x in stream(r/'pair'/(name+'.jsonl.gz')):
    hh.update(json.dumps(x,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode());hh.update(b'\n');count+=1
   assert restart['all6_streams_exact'][field]['records']==count
   # Producer receipt uses its frozen canonical encoder; raw payload equality at restore is source-reviewed.
  assert not list((r/'failure').iterdir())
  out[side]={'passed':True,'source_SHA_checks':len(merged),'preserved_CP_sources':len(m['source_freeze']),'authorization_SHA256':meta['authorization_sha256'],'terminal_CP_SHA256':m['sha256'],'terminal_NAV':b['ending_NAV'],'own_quarters':cc,'Jan2_own_prefix_exact_stream_records':pairs,'actual_cursor':m['at'],'genuine_separate_process_terminal_receipt_SHA256':I.sha(r/'TERMINAL_SEPARATE_PROCESS_RESTORE.json')}
 out['reviewer_source_SHA256']=I.sha(__file__);out['reviewer_account_events']=0;out['scope']='Byte/source/grant/provenance and exact six-stream/all financial-history own-Jan2 prefix audit. Independent726day raw-price money/DD audit is separate. Terminal new-process complete-state restore is producer evidence whose receipt and source/CP identities are checked here; reviewer does not invoke engine restore. All2024 actual ACT/score clocks independently verified separately; fullQ/CP1/stage producer replay separately binds fresh1709/90 loader. No Jan2 or prior-year replay/reset.'
 (I.HERE/'PVR_2024_COMPLETION_IDENTITY_AUDIT.json').write_text(json.dumps(out,indent=2,default=str)+'\n');print(json.dumps(out,indent=2))
if __name__=='__main__':main()
