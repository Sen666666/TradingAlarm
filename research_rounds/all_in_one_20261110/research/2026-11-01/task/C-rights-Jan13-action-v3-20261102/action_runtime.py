"""Exactly registered Jan13 ACTION outputs; original Jan12 registry untouched."""
from pathlib import Path
from datetime import datetime
import copy,hashlib,json,pickle,sys
HERE=Path(__file__).resolve().parent;UP=HERE.parent/'C-rights-Jan12-upgrade-v1-20261102';NS=HERE.parent/'C-rights-no-subscription-wiring-v1-20261102'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(v,m):
 if not v:raise ValueError(m)
def guard():
 f=read(HERE/'SOURCE_FREEZE.json')
 for p,h in f['sources'].items():require(sha(p)==h,'ACTION source changed '+p)
 require(sha(HERE/'ACTION_IDENTITY.json')==f['identity_sha256'],'ACTION identity changed')
 return read(HERE/'ACTION_IDENTITY.json')
guard();sys.path.insert(0,str(UP));import upgrade_runtime as U
import rights_wiring_v3 as R
from fingerprint import snapshot,compare,digest,ALLOWED
E=U.E;AT=datetime.fromisoformat('2022-01-13T00:00:00+08:00')
def conservation_sha(r):return hashlib.sha256(R.conservation_bytes(r)).hexdigest()
def original_entry(arm):
 i=guard();require(arm in i['arms'] and arm.startswith('2022-'),'only two selected2022 arms');return i['arms'][arm]
def authority(arm):
 e=read(HERE/'EXECUTION_AUTHORITY.json');require(e['action_identity_sha256']==sha(HERE/'ACTION_IDENTITY.json'),'authority identity mismatch')
 return e['arms'][arm]
def validate_grant(r):
 arm=r.action_activation['arm'];known=authority(arm);g=r.rights_future_grant
 require(g['path']==known['path'] and g['sha256']==known['sha256'],'grant not in exact trusted authority')
 entry=original_entry(arm);require(g['base_checkpoint_sha256']==entry['sha256'],'wrong bound Jan12 checkpoint')
 grant=U.validate_action_grant(r,g['path'],g['sha256'],entry['sha256'])
 require(grant['action_identity_sha256']==sha(HERE/'ACTION_IDENTITY.json'),'wrong ACTION identity grant')
 return grant
class ActionRunner(R.NoSubscriptionRunnerMixin,U.UpgradedRunner):
 def __init__(self,*a,**k):raise RuntimeError('registered Jan12 activation only')
 def source_binding(self):
  out=super().source_binding()
  for n in ['action_runtime.py','fingerprint.py','ACTION_IDENTITY.json','SOURCE_FREEZE.json','EXECUTION_AUTHORITY.json','CONTRACT.txt','run_actions.py']:
   p=HERE/n;out[str(p)]=sha(p)
  return out
 def binding(self):
  x=super().binding();x['Jan13_ACTION_activation']=copy.deepcopy(self.action_activation)
  x['Jan13_ACTION_evidence_hash']=digest(getattr(self,'action_evidence',None));return x
 def execution_guard(self,day):
  guard();require(day=='2022-01-13','ACTION only Jan13');validate_grant(self)
 def verify_action_state(self,rec):
  arm=self.action_activation['arm'];e=original_entry(arm)
  require(self.window=='2022' and self.mode==e['mode'] and self.last_completed_event==AT,'wrong ACTION state/mode/cursor')
  require(type(self.account) is U.M.MonthAccount and type(self.inputs) is U.RightsMonthInputs,'wrong ACTION account/input class')
  require(self.action_activation['Jan12_checkpoint_sha256']==e['sha256'] and self.action_activation['identity_sha256']==sha(HERE/'ACTION_IDENTITY.json'),'activation identity changed')
  validate_grant(self)
  require(conservation_sha(self)==e['conservation_sha256'],'financial/strategy state differs from trusted Jan12')
  require(U.prefix_hashes(self)['whole']==rec['prefix_sha256'],'post-ACTION prefix differs from trusted output')
  expected=read(rec['state_file']);require(sha(rec['state_file'])==rec['state_file_sha256'],'post-state evidence file changed')
  require(snapshot(self)==expected,'complete post-ACTION state differs from trusted output')
  self.assert_observers()
  for c in self.authority.certificates.values():self.verify_native(c)
  require(conservation_sha(self)==e['conservation_sha256'],'certificate verification changed state')
  require(snapshot(self)==expected,'certificate verification changed post-ACTION fields')
  return True
 @classmethod
 def restore(cls,path,*,registry_sha):
  identity=guard();registry_file=HERE/'OUTPUT_REGISTRY.json';require(registry_sha and sha(registry_file)==registry_sha,'explicit trusted output-registry SHA required')
  bank=read(registry_file);require(bank['identity_sha256']==sha(HERE/'ACTION_IDENTITY.json'),'output registry identity mismatch')
  p=Path(path).resolve();matches=[x for x in bank['outputs'] if Path(x['checkpoint']).resolve()==p];require(len(matches)==1,'unregistered ACTION checkpoint')
  rec=matches[0];e=original_entry(rec['arm']);require(p==(HERE/'outputs'/rec['arm']/'JAN13_ACTION.pkl').resolve(),'wrong ACTION output path')
  require(Path(rec['state_file']).resolve()==(p.parent/'POST_STATE_FIELDS.json').resolve() and Path(rec['evidence_file']).resolve()==(p.parent/'ACTION_EVIDENCE.json').resolve(),'wrong registered evidence path')
  require(sha(rec['evidence_file'])==rec['evidence_file_sha256'],'ACTION evidence bytes changed')
  require(rec['input_checkpoint_sha256']==e['sha256'] and rec['phase']=='ACTION' and rec['cursor']==AT.isoformat(),'wrong registered event/input')
  require(sha(p)==rec['sha256'] and sha(p.with_suffix('.provenance.json'))==rec['provenance_sha256'],'ACTION checkpoint/provenance bytes changed')
  side=read(p.with_suffix('.provenance.json'));require(side['checkpoint_sha256']==rec['sha256'],'ACTION provenance mismatch')
  with p.open('rb') as f:r=pickle.load(f)
  require(type(r) is cls and r.action_activation['arm']==rec['arm'],'wrong registered ACTION class/arm')
  r.account.owner=r
  require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'exact ACTION engine/source/input/mode identity required')
  r.verify_action_state(rec);return r

def activate(arm,trusted_grant_sha):
 e=original_entry(arm);a=authority(arm);require(trusted_grant_sha==a['sha256'],'wrong caller trusted grant SHA')
 require(U.sha(UP/'UPGRADED_CHECKPOINTS.json')==guard()['Jan12_registry_sha256'],'original Jan12 registry changed')
 r=U.UpgradedRunner.restore(e['checkpoint']);before=U.prefix_hashes(r)
 require(before['whole']==e['prefix_sha256'] and conservation_sha(r)==e['conservation_sha256'],'Jan12 input state differs from frozen identity')
 r.__class__=ActionRunner;r.action_activation=dict(version='JAN13-ACTION-3',arm=arm,Jan12_checkpoint=e['checkpoint'],Jan12_checkpoint_sha256=e['sha256'],identity_sha256=sha(HERE/'ACTION_IDENTITY.json'),activation_no_financial_event=True)
 r.rights_future_grant=dict(path=a['path'],sha256=a['sha256'],base_checkpoint_sha256=e['sha256'])
 validate_grant(r);require(U.prefix_hashes(r)==before,'ACTION activation changed financial prefix')
 return r
def coordinate_image(r):
 a=r.account;sid='002948.SZ';rows=[]
 for z in a.layers:
  if not z['qty']:continue
  signal=a.facts.floor(z['sid'],a.last_cursor,'I') if z['kind']=='core' else z['floor'];factor=a.facts.factor(z['sid'],a.last_cursor);raw=a.raw_floor(z)
  require(raw==signal/factor,'effective raw protection coordinate mismatch')
  rows.append(dict(layer=str(z['id']),sid=z['sid'],qty=z['qty'],stored_signal_floor=str(signal),factor=str(factor),raw_floor=str(raw),actual_share_ratio=str(a.share_ratio[z['sid']])))
 return dict(owned_shares=a.quantity(sid),raw_price=str(a.market.prices[sid]),factor=str(a.market.factors[sid]),known_at=str(a.market.known[sid]),actual_share_ratio=str(a.share_ratio[sid]),layers=rows)
def run_one(arm,trusted_grant_sha):
 r=activate(arm,trusted_grant_sha);out=HERE/'outputs'/arm;require(not out.exists(),'ACTION output already exists; restore registered result, never silently replay input')
 out.mkdir(parents=True,exist_ok=False);e=original_entry(arm)
 actions=r.inputs.actions('2022-01-13');require(digest(actions)==guard()['actions_sha256'],'exact original ACTION terms changed')
 before_prefix=U.prefix_hashes(r);before_coord=coordinate_image(r);before=snapshot(r);before_cons=conservation_sha(r)
 before_events=len(r.events);before_action_logs=len(r.action_log);before_audit=len(r.account.audit_log);before_callbacks=len(r.account.native_callbacks)
 checkpoint_backup=pickle.dumps(r,pickle.HIGHEST_PROTOCOL)
 try:
  result=r.corporate_actions('2022-01-13')
  require(result['status']=='observed_no_subscription','ACTION did not commit expected no-subscription observation')
  after=snapshot(r);delta=compare(before,after);require(not delta['unexpected'],'undeclared ACTION state differences '+str(delta['unexpected']))
  require(before_cons==conservation_sha(r)==e['conservation_sha256'],'ACTION changed financial/strategy/budget state')
  require(len(r.events)==before_events+1 and len(r.action_log)==before_action_logs+1 and len(r.account.audit_log)==before_audit+1 and len(r.account.native_callbacks)==before_callbacks+1,'ACTION audit/callback count mismatch')
  require(r.events[-1]['phase']=='ACTION' and r.events[-1]['at']==AT,'wrong legal event advancement')
  after_coord=coordinate_image(r);term=actions[0];expected=(E.D(before_coord['raw_price'])-E.D(term['signal_cash_per_old_share']))/E.D(term['signal_split_ratio'])
  require(E.D(after_coord['raw_price'])==expected,'original theoretical ex-reference mismatch')
  require(after_coord['owned_shares']==before_coord['owned_shares'] and after_coord['actual_share_ratio']==before_coord['actual_share_ratio'],'rights changed actual shares/ratio')
  oldlayers={x['layer']:x for x in before_coord['layers']}
  for z in after_coord['layers']:
   old=oldlayers[z['layer']];require(z['qty']==old['qty'] and z['stored_signal_floor']==old['stored_signal_floor'] and z['actual_share_ratio']==old['actual_share_ratio'],'layer protection storage/quantity changed')
  cert_audits=[]
  for c in r.authority.certificates.values():
   solved=r.verify_native(c);require(E.digest(solved)==c['projection_hash'],'old certificate projection changed')
   cert_audits.append(dict(id=c['certificate_id'],known_at=c['known_at'],projection_hash=E.digest(solved),genuine_old_source=True))
  certificate_fields=snapshot(r);certificate_diff=compare(after,certificate_fields)
  require(not certificate_diff['changed'],'post-ACTION certificate verification changed fields '+str(certificate_diff['changed']))
  evidence=dict(arm=arm,input_checkpoint_sha256=e['sha256'],grant_sha256=trusted_grant_sha,before_prefix=before_prefix,after_prefix=U.prefix_hashes(r),conservation_before=before_cons,conservation_after=conservation_sha(r),diff=delta,before_coordinate=before_coord,after_coordinate=after_coord,certificates=cert_audits,events_added=1,OPEN_CLOSE_executed=0)
  r.action_evidence=evidence
  statefile=out/'POST_STATE_FIELDS.json';statefile.write_text(json.dumps(after,ensure_ascii=False,indent=2)+'\n')
  (out/'ACTION_EVIDENCE.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2,default=str)+'\n')
  cp=out/'JAN13_ACTION.pkl';r.checkpoint(cp)
  return dict(arm=arm,checkpoint=str(cp),sha256=sha(cp),provenance_sha256=sha(cp.with_suffix('.provenance.json')),input_checkpoint_sha256=e['sha256'],grant_sha256=trusted_grant_sha,identity_sha256=sha(HERE/'ACTION_IDENTITY.json'),phase='ACTION',cursor=AT.isoformat(),prefix_sha256=U.prefix_hashes(r)['whole'],state_file=str(statefile),state_file_sha256=sha(statefile),evidence_file=str(out/'ACTION_EVIDENCE.json'),evidence_file_sha256=sha(out/'ACTION_EVIDENCE.json'))
 except Exception as exc:
  prior=pickle.loads(checkpoint_backup);r.__dict__.clear();r.__dict__.update(prior.__dict__);r.account.owner=r
  rollback_financial_exact=conservation_sha(r)==before_cons
  rollback_field_diff=compare(before,snapshot(r))
  stop=dict(error=type(exc).__name__+': '+str(exc),cursor=str(r.last_completed_event),atomic_financial_rollback=rollback_financial_exact,rollback_field_diff=rollback_field_diff,certificate_diff=locals().get('certificate_diff'),output_registered=False)
  (out/'STOP.json').write_text(json.dumps(stop,ensure_ascii=False,indent=2)+'\n')
  require(rollback_financial_exact and not rollback_field_diff['changed'],'failed ACTION did not roll back; STOP evidence saved')
  raise
