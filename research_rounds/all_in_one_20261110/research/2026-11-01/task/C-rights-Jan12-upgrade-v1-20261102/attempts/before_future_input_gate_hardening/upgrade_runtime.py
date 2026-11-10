"""Explicit 2022 Jan12 source-preserving upgrade. No new history event entry."""
from pathlib import Path
import copy,hashlib,json,pickle,sys
HERE=Path(__file__).resolve().parent
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
OLD=W/'g-s-C-month-continuation-20261102'
RIGHTS=HERE.parent/'C-rights-no-subscription-wiring-v1-20261102'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def require(v,message):
 if not v:raise ValueError(message)
def guard():
 f=read(HERE/'SOURCE_FREEZE.json')
 for p,h in f['sources'].items():require(sha(p)==h,'upgrade dependency changed '+p)
 return f
guard()
sys.path.insert(0,str(RIGHTS));from rights_wiring import NoSubscriptionInputsMixin,NoSubscriptionRunnerMixin
sys.path.insert(0,str(OLD));import month_runtime as M
E=M.E
def identity():
 guard();x=read(HERE/'IDENTITY.json');f=read(HERE/'SOURCE_FREEZE.json')
 require(sha(HERE/'IDENTITY.json')==f['identity_sha256'],'upgrade identity changed')
 return x
def prefix(r):return M.C.prefix_view(r)
def prefix_hashes(r):
 p=prefix(r);return dict(whole=E.digest(p),fields={k:E.digest(v) for k,v in p.items()})
def arm_entry(arm):
 x=identity();require(arm in x['arms'] and arm.startswith('2022-'),'only selected 2022 arms')
 return x['arms'][arm]
class RightsMonthInputs(NoSubscriptionInputsMixin,M.MonthInputs):pass

class UpgradedRunner(NoSubscriptionRunnerMixin,M.MonthRunner):
 def __init__(self,*a,**k):raise RuntimeError('explicit verified Jan12 import only')
 def source_binding(self):
  out=super().source_binding()
  for n in ['upgrade_runtime.py','IDENTITY.json','SOURCE_FREEZE.json','CONTRACT.txt','jan13_action.py']:
   p=HERE/n;out[str(p)]=sha(p)
  return out
 def binding(self):
  x=super().binding();x['no_subscription_upgrade']=copy.deepcopy(self.rights_upgrade_record)
  x['future_action_grant']=copy.deepcopy(getattr(self,'rights_future_grant',None));return x
 def verify_native(self,cert):
  rec=self.rights_upgrade_record;entry=arm_entry(rec['arm'])
  require(self.window=='2022' and self.mode==entry['mode'],'upgraded mode/window changed')
  cid=cert.get('certificate_id');bank={r['id']:r for r in entry['certificates']}
  if cid not in bank:return super().verify_native(cert)
  original=bank[cid]
  require(E.digest(cert)==original['certificate_sha'],'legacy certificate changed')
  require(E.digest(cert['source_binding'])==original['source_sha'],'legacy source changed')
  require(cert['trusted_id'] in self.trusted and E.digest(self.trusted[cert['trusted_id']])==original['trusted_sha'],'legacy trusted snapshot changed')
  require(type(self.rights_legacy_inputs) is M.MonthInputs,'legacy input class changed')
  require(str(self.rights_legacy_inputs.path)==entry['input_manifest'] and sha(self.rights_legacy_inputs.path)==entry['input_manifest_sha256'],'legacy input identity changed')
  # A genuine old class method with old source and old input generation. No
  # new source is substituted into certificates; Jan7–12 take this route too.
  view=object.__new__(M.MonthRunner);view.__dict__.update(self.__dict__);view.inputs=self.rights_legacy_inputs
  view.account=copy.copy(self.account);view.account.owner=view
  view.account.market=copy.copy(self.account.market);view.account.market.inputs=view.inputs
  view.account.facts=copy.copy(self.account.facts);view.account.facts.inputs=view.inputs;view.account.facts.market=view.account.market
  before=prefix_hashes(self)
  result=M.MonthRunner.verify_native(view,cert)
  require(prefix_hashes(self)==before,'legacy verification mutated financial prefix')
  return result
 def verify_upgrade(self):
  rec=self.rights_upgrade_record;entry=arm_entry(rec['arm'])
  require(rec['identity_sha256']==sha(HERE/'IDENTITY.json') and rec['original_checkpoint_sha256']==entry['checkpoint_sha256'],'upgrade origin changed')
  require(self.mode==entry['mode'] and self.window=='2022' and str(self.last_completed_event)==entry['cursor'],'wrong upgraded mode/cursor')
  require(type(self.account) is M.MonthAccount and type(self.inputs) is RightsMonthInputs,'upgraded class identity changed')
  require(set(self.authority.certificates)=={r['id'] for r in entry['certificates']},'legacy certificate set changed')
  require(prefix_hashes(self)['whole']==entry['prefix_sha256'],'upgraded financial/strategy/flow prefix changed')
  self.assert_observers()
  for c in self.authority.certificates.values():self.verify_native(c)
  require(prefix_hashes(self)['whole']==entry['prefix_sha256'],'verification changed prefix')
  return True
 def execution_guard(self,day):
  g=getattr(self,'rights_future_grant',None)
  require(g is not None,'Jan12 upgrade has no new history execution grant')
  validate_action_grant(self,g['path'],g['sha256'],g['base_checkpoint_sha256'])
  require(day=='2022-01-13','future grant is Jan13 ACTION only')
 def step(self,*a,**k):raise ValueError('OPEN/CLOSE not authorized by no-event upgrade')
 def event(self,*a,**k):raise ValueError('native financial event not authorized by no-event upgrade')
 def _rights_ordinary_dispatch(self,day):raise ValueError('future grant supports no-subscription rights only')
 @classmethod
 def restore(cls,path):
  identity();p=Path(path).resolve();registry=read(HERE/'UPGRADED_CHECKPOINTS.json')
  candidates=[r for r in registry if Path(r['checkpoint']).resolve()==p];require(len(candidates)==1,'unregistered upgraded checkpoint')
  rec=candidates[0];require(sha(p)==rec['sha256'] and sha(p.with_suffix('.provenance.json'))==rec['provenance_sha256'],'upgraded checkpoint bytes changed')
  side=read(p.with_suffix('.provenance.json'));require(side['checkpoint_sha256']==rec['sha256'],'upgraded provenance mismatch')
  with p.open('rb') as f:r=pickle.load(f)
  require(type(r) is cls and r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'exact upgraded native/source/input/mode identity required')
  r.account.owner=r;r.verify_upgrade();return r

def load_original(arm,*,source_path=None,source_sha=None):
 entry=arm_entry(arm);p=Path(entry['checkpoint'])
 require(source_path is None or Path(source_path).resolve()==p.resolve(),'wrong original checkpoint source')
 require(source_sha is None or source_sha==entry['checkpoint_sha256'],'wrong requested checkpoint hash')
 require(sha(p)==entry['checkpoint_sha256'] and sha(p.with_suffix('.provenance.json'))==entry['provenance_sha256'],'original checkpoint/provenance changed')
 r=M.MonthRunner.restore(p)
 require(type(r) is M.MonthRunner and type(r.inputs) is M.MonthInputs,'not genuine original class/input')
 require(r.window=='2022' and r.mode==entry['mode'] and str(r.last_completed_event)==entry['cursor'],'original mode/window/cursor mismatch')
 require(prefix_hashes(r)['whole']==entry['prefix_sha256'],'original prefix differs from verified baseline')
 return r
def upgrade_runner(r,arm):
 entry=arm_entry(arm)
 if type(r) is UpgradedRunner:
  require(r.rights_upgrade_record['arm']==arm,'wrong duplicate upgrade arm');r.verify_upgrade();return r,'already_upgraded'
 require(type(r) is M.MonthRunner and r.window=='2022' and r.mode==entry['mode'],'wrong original upgrade class/mode')
 before=prefix_hashes(r);require(before['whole']==entry['prefix_sha256'],'wrong original upgrade prefix')
 # Reverify the original fully, before changing a class or input pointer.
 r.assert_observers()
 for c in r.authority.certificates.values():M.MonthRunner.verify_native(r,c)
 old_inputs=r.inputs;new_inputs=copy.deepcopy(old_inputs);new_inputs.__class__=RightsMonthInputs
 r.inputs=new_inputs;r.account.market.inputs=new_inputs;r.account.facts.inputs=new_inputs
 r.__class__=UpgradedRunner;r.rights_legacy_inputs=old_inputs
 r.rights_upgrade_record=dict(version='JAN12-NSR-UPGRADE-1',arm=arm,identity_sha256=sha(HERE/'IDENTITY.json'),original_checkpoint=entry['checkpoint'],original_checkpoint_sha256=entry['checkpoint_sha256'],original_class='month_runtime.MonthRunner',original_input_class='month_runtime.MonthInputs',original_prefix_sha256=before['whole'],no_financial_event=True)
 r.rights_future_grant=None
 require(prefix_hashes(r)==before,'no-event class/input upgrade changed prefix');r.verify_upgrade()
 return r,'upgraded_no_event'

def validate_action_grant(r,path,expected_sha,base_checkpoint_sha):
 require(expected_sha and sha(path)==expected_sha,'future action grant hash mismatch');g=read(path)
 require(g.get('parent_approved') is True and g.get('scope')=='2022_JAN13_NO_SUBSCRIPTION_ACTION_ONLY','no explicit future ACTION authority')
 require(g.get('identity_sha256')==sha(HERE/'IDENTITY.json') and g.get('arm')==r.rights_upgrade_record['arm'],'future action identity/arm mismatch')
 require(g.get('day')=='2022-01-13' and g.get('phase')=='ACTION' and g.get('no_OPEN_CLOSE') is True,'future action scope mismatch')
 require(g.get('input_checkpoint_sha256')==base_checkpoint_sha,'future action checkpoint mismatch')
 return g
