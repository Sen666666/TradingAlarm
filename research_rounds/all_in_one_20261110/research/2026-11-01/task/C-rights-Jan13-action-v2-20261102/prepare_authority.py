"""No-event preflight and exact scoped grants from the current parent approval."""
from pathlib import Path
import argparse,hashlib,json,sys,time
O=Path(__file__).resolve().parent;UP=O.parent/'C-rights-Jan12-upgrade-v1-20261102';NS=O.parent/'C-rights-no-subscription-wiring-v1-20261102'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
sys.path.insert(0,str(UP));import upgrade_runtime as U
import rights_wiring_v2 as R
from fingerprint import snapshot,digest
def save(n,x):
 p=O/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2,default=str)+'\n')
def main():
 assert not (O/'SOURCE_FREEZE.json').exists(),'authority already frozen'
 p=argparse.ArgumentParser();p.add_argument('--preflight-only',action='store_true');p.add_argument('--independent-audit',type=Path);p.add_argument('--trusted-audit-sha');p.add_argument('--reviewed-code-sha');args=p.parse_args()
 code=U.read(O/'CODE_FREEZE.json');assert all(sha(path)==h for path,h in code['sources'].items()),'prepared code changed'
 if not args.preflight_only:
  assert args.independent_audit and args.trusted_audit_sha and args.reviewed_code_sha==sha(O/'CODE_FREEZE.json'),'independent PASS bound to exact prepared code required'
  assert sha(args.independent_audit)==args.trusted_audit_sha and U.read(args.independent_audit).get('passed') is True,'trusted independent PASS required'
 begun=time.monotonic();reg=U.read(UP/'UPGRADED_CHECKPOINTS.json');review=Path('/tmp/rights-upgrade-independent-1spc01pv/FINAL_AUDIT.json');(O/'UPGRADE_INDEPENDENT_AUDIT.json').write_bytes(review.read_bytes())
 assert U.read(review)['passed'];assert sha(UP/'IDENTITY.json')=='6c3e8631cdd645d752542dcd7ff086b11223769cb5680dcb5477e348d2652ca1'
 assert sha(UP/'PACKAGE_SHA256.json')=='c8c6df304e3ef7cbc972431635a2af199c9c7f1b7485110739789a042bcada55'
 arms={};actions=None
 for rec in reg:
  arm=rec['arm'];assert arm in ['2022-C10','2022-C_BATCH20'];r=U.UpgradedRunner.restore(rec['checkpoint'])
  pfx=U.prefix_hashes(r);terms=r.inputs.actions('2022-01-13');assert len(terms)==1 and terms[0]['sid']=='002948.SZ';R.validate_rights(terms[0],'2022-01-13')
  if actions is None:actions=terms
  assert actions==terms
  f=r.inputs.rows('facts','002948.SZ','2022-01-13',True);assert R.number(f['factor'],'original Jan13 factor')>0
  armdata=dict(rec,mode=r.mode,conservation_sha256=hashlib.sha256(R.conservation_bytes(r)).hexdigest(),before_fields=snapshot(r),before_prefix=pfx,
   available=str(r.account.available),New=str(r.budget.batch['new']),Carry=str(r.budget.batch['carry']),pending=len(r.account.pending),buys=len(r.account.buys),exits=len(r.account.exits),rights_shares=r.account.quantity('002948.SZ'))
  assert U.prefix_hashes(r)==pfx;arms[arm]=armdata;print('NO_EVENT_PREFLIGHT',arm,len(armdata['before_fields']),flush=True)
 save('NO_EVENT_PREFLIGHT.json',dict(passed=True,no_event=True,arms=arms,actions_sha256=digest(actions),fingerprint_sha256=sha(O/'fingerprint.py'),prepared_code_sha256=sha(O/'CODE_FREEZE.json')))
 if args.preflight_only:
  print('PREFLIGHT_ONLY_NO_AUTHORITY_CREATED',flush=True);return
 identity=dict(version='JAN13-ACTION-2',day='2022-01-13',phase='ACTION',arms=arms,actions=actions,actions_sha256=digest(actions),Jan12_registry_sha256=sha(UP/'UPGRADED_CHECKPOINTS.json'),Jan12_identity_sha256=sha(UP/'IDENTITY.json'),original_upgrade_package_sha256=sha(UP/'PACKAGE_SHA256.json'),no_OPEN_CLOSE=True,fingerprint_sha256=sha(O/'fingerprint.py'),prepared_code_sha256=sha(O/'CODE_FREEZE.json'),independent_audit=dict(path=str(args.independent_audit.resolve()),sha256=args.trusted_audit_sha))
 save('ACTION_IDENTITY.json',identity)
 authority={}
 for arm,e in arms.items():
  grant=dict(parent_approved=True,scope='2022_JAN13_NO_SUBSCRIPTION_ACTION_ONLY',identity_sha256=sha(UP/'IDENTITY.json'),action_identity_sha256=sha(O/'ACTION_IDENTITY.json'),arm=arm,input_checkpoint_sha256=e['sha256'],day='2022-01-13',phase='ACTION',no_OPEN_CLOSE=True,approval_source='explicit parent delegation 01a1869e-bab0-73ad-a5ca-8b65eb61f01b: two2022 Jan13 ACTION only; no original writes/no2025')
  path='grants/'+arm+'-JAN13-ACTION.json';save(path,grant);authority[arm]=dict(path=str(O/path),sha256=sha(O/path))
 save('EXECUTION_AUTHORITY.json',dict(action_identity_sha256=sha(O/'ACTION_IDENTITY.json'),arms=authority,scope='exact two Jan13 ACTION only; independent PASS required and bound'))
 sources={}
 fixed=[O/'CODE_FREEZE.json',args.independent_audit,UP/'upgrade_runtime.py',UP/'SOURCE_FREEZE.json',UP/'IDENTITY.json',UP/'UPGRADED_CHECKPOINTS.json',UP/'PACKAGE_SHA256.json',NS/'rights_wiring.py',NS/'CONTRACT.txt',NS/'PACKAGE_SHA256.json']
 own=list(O.glob('*.py'))+[O/'CONTRACT.txt',O/'EXECUTION_AUTHORITY.json',O/'UPGRADE_INDEPENDENT_AUDIT.json']+[Path(v['path']) for v in authority.values()]
 for p in fixed+own:sources[str(p)]=sha(p)
 save('SOURCE_FREEZE.json',dict(sources=sources,identity_sha256=sha(O/'ACTION_IDENTITY.json'),scope='Jan13 ACTION only; existing old sources guarded transitively unchanged'))
 save('AUTHORITY_PREFLIGHT.json',dict(passed=True,arms=2,no_event=True,seconds=time.monotonic()-begun,grants=authority));print('TRUSTED_GRANTS_FROZEN',json.dumps(authority),flush=True)
if __name__=='__main__':main()
