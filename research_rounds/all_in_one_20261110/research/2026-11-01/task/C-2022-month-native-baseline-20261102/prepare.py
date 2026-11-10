from pathlib import Path
import hashlib,json
O=Path(__file__).resolve().parent;CORE=O.parent/'C-rights-month-resume-v2-20261102'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda p:json.loads(Path(p).read_text())
def save(p,x):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n')
def main():
 assert not(O/'AUTHORIZATION.json').exists()
 audit=Path('/var/folders/sj/6vknnkzj0_q6yp4myjk4mtt00000gn/T/rights-Jan13-day-independent-oa3c8i9o/FINAL_AUDIT_RECOVERED.json');assert read(audit)['passed']
 idx=CORE/'CONTINUATION_CHECKPOINTS.json';assert sha(idx)=='1a20e420b468101250211881539145b54c1135614653bfa8d574e7f45cea9483'
 index=read(idx);arms={v['arm']:v for v in index['formal']};root=read(CORE/'IDENTITY.json');m=read(root['inputs']['full']['path']);days=[d for d in m['days'] if '2022-01-13'<d<='2022-01-31'];assert days[-1]=='2022-01-28'
 grants={}
 for arm,v in arms.items():
  assert sha(v['checkpoint'])==v['checkpoint_sha256'] and sha(v['registry'])==v['trusted_registry_sha256']
  p=O/'grants'/(arm+'-JAN-END.json');g=dict(parent_approved=True,scope='C_EXISTING_ACCOUNT_MONTH_CONTINUATION',runtime_identity_sha256=sha(CORE/'IDENTITY.json'),arm=arm,window='2022',mode=arm[5:],branch='full',base_ACTION_checkpoint_sha256=root['arms'][arm]['sha256'],start_checkpoint_sha256=v['checkpoint_sha256'],input_manifest_sha256=root['inputs']['full']['sha256'],days=days,phases=['ACTION','OPEN','CLOSE'],no_account_reset=True,no_R0_overlay=True,no_2025=True,no_February=True,approval_source='parent explicit 2022 original two continuous accounts Jan13 trusted CLOSE to January final session CLOSE; unchanged ContinuationRunner/native policy')
  save(p,g);grants[arm]=dict(path=str(p),sha256=sha(p))
 sources={str(p):sha(p) for p in [O/'month_worker.py',O/'prepare.py',CORE/'resume_runtime_v2.py',CORE/'SOURCE_FREEZE.json',CORE/'IDENTITY.json',idx,audit]}
 save(O/'AUTHORIZATION.json',dict(parent_approved=True,cutoff='2022-01-28',days=days,arms=arms,grants=grants,sources=sources,no_R0=True,baseline='original C10 and C_BATCH20; original 2022-Jan04 1m start, no reset',registry_policy='append records, archive each prior registry byte-for-byte before atomic replacement'))
 print('MONTH_AUTHORIZED',days,grants)
if __name__=='__main__':main()
