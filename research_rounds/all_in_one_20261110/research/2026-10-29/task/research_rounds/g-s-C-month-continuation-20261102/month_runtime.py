"""Reusable same-account month data; append-only execution grants, no reset."""
from pathlib import Path
import sys,json,copy,pickle
import pandas as pd
HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-C-nextsession-native-20261102'));import c_horizon as C
P=C.P;E=C.E;X=C.X;H=C.H
def read(p):return json.loads(Path(p).read_text())
def guard():
 i=read(HERE/'POLICY_INPUT_IDENTITY.json')
 for p,h in i['sources'].items():E.require(P.sha(p)==h,'month source changed '+p)
 E.require(P.sha(HERE/'MONTH_INPUT_FREEZE.json')==i['input_freeze_sha256'],'month input freeze changed')
 C.guard();return i
class MonthInputs(X.ExtendedInputs):
 def __init__(self,path):self.month_objects={};self.month_frames={};self.month_verified=set();super().__init__(path)
 def month_ref(self,key):
  rec=self.m['month_extension'][key];p=self.root/rec['path']
  if key not in self.month_verified:E.require(P.sha(p)==rec['sha256'],'month input changed '+key);self.month_verified.add(key)
  return p
 def obj(self,key):
  base=super().obj(key)
  if key not in self.m['month_extension']:return base
  if key not in self.month_objects:
   more=read(self.month_ref(key))
   if key=='metadata':
    result=copy.deepcopy(base)
    for sid,rows in more.items():result[sid]['structure_observations']+=rows
   else:result=copy.deepcopy(base)+more
   self.month_objects[key]=result
  return self.month_objects[key]
 def table(self,key):
  base=super().table(key)
  if key not in self.m['month_extension']:return base
  if key not in self.month_frames:self.month_frames[key]=pd.concat([base,pd.read_parquet(self.month_ref(key))],ignore_index=True)
  return self.month_frames[key]
class MonthAccount(C.HorizonAccount):
 def select_generation(self,at):
  day=at.date().isoformat();key=self.month_generations.get(day)
  if key is None:
   bank={r['receipt_id']:H.payload_json(r) for r in self.market.inputs.obj('receipts') if r['confirmed_day']<=day};key=E.digest(bank);self.canonical_generations[key]=bank;self.month_generations[day]=key
  self.canonical_binding=key;self.canonical_registry=self.canonical_generations[key]
class MonthRunner(C.HorizonRunner):
 def __init__(self,*a,**kw):raise RuntimeError('only explicit same-account month horizon import')
 def source_binding(self):
  x=super().source_binding();x.update({str(p):P.sha(p) for p in [HERE/'month_runtime.py',HERE/'run_month.py',HERE/'POLICY_INPUT_IDENTITY.json',HERE/'MONTH_INPUT_FREEZE.json']});return x
 def binding(self):
  x=super().binding();x['previous_single_session_scope']=x.pop('allowed_next_session');x.update(scope='same-account month-input horizon, execution ONLY within explicit current grant',days=self.inputs.days,month_data=self.inputs.m['month_data_scope'],month_extension=self.inputs.m['month_extension'],month_import=self.month_import,execution_grant=self.execution_grant_record,grant_history=self.execution_grant_history)
  self.validate_grant(self.execution_grant_record['path'],expected_sha=self.execution_grant_record['sha256']);return x
 def validate_grant(self,path,expected_sha=None):
  identity=guard();g=read(path)
  E.require(expected_sha is None or P.sha(path)==expected_sha,'historical execution grant file changed')
  E.require(g['parent_approved'] and g['policy_input_identity_sha256']==P.sha(HERE/'POLICY_INPUT_IDENTITY.json'),'unapproved policy/input grant')
  E.require(g['scope']=='C_EXISTING_FOUR_ACCOUNTS_ONLY' and g['no_account_reset'] and self.window in g['cutoff'],'wrong execution scope')
  m=self.inputs.m['month_data_scope'];E.require(m['start']<=g['cutoff'][self.window]<=m['end'],'grant beyond frozen month data')
  return g
 def accept_grant(self,path):
  before=E.digest(C.prefix_view(self));g=self.validate_grant(path);rec=dict(path=str(Path(path).resolve()),sha256=P.sha(path),cutoff=g['cutoff'][self.window])
  if getattr(self,'execution_grant_record',None)!=rec:
   old=getattr(self,'execution_grant_record',None)
   E.require(old is None or rec['cutoff']>=old['cutoff'],'cannot silently shorten/replace completed execution grant')
   self.execution_grant_record=rec;self.execution_grant_history.append(dict(old=old,new=rec,at=str(self.last_completed_event)))
  E.require(E.digest(C.prefix_view(self))==before,'grant changed economic/strategy state')
 def execution_guard(self,day):
  gate=read(HERE/'READ_ONLY_GATE.json');E.require(gate['passed'] and gate['policy_input_identity_sha256']==P.sha(HERE/'POLICY_INPUT_IDENTITY.json'),'month mapping preflight required')
  g=self.validate_grant(self.execution_grant_record['path'],expected_sha=self.execution_grant_record['sha256']);m=self.inputs.m['month_data_scope']
  E.require(m['start']<=day<=g['cutoff'][self.window],'outside explicit execution cutoff')
 def verify_native(self,cert):
  if cert['certificate_id'] in self.month_old_certificates:
   E.require(cert==self.month_old_certificates[cert['certificate_id']],'old certificate changed')
   view=object.__new__(C.HorizonRunner);view.__dict__.update(self.__dict__);view.inputs=self.month_old_inputs
   return C.HorizonRunner.verify_native(view,cert)
  return super().verify_native(cert)
 def step(self,day,phase):self.execution_guard(day);return H.HistoricalRunner.step(self,day,phase)
 def corporate_actions(self,day):
  self.execution_guard(day);E.require(E.iso(day+'T00:00:00+08:00')>self.last_completed_event,'completed action cannot replay')
  return C.F.FixedRunner.corporate_actions(self,day)
def import_account(window,mode,grant,out):
 identity=guard();rec=identity['accounts'][window+'-'+mode];p=Path(rec['path']);E.require(P.sha(p)==rec['sha256'],'parent financial checkpoint changed')
 r=C.HorizonRunner.restore(p);E.require(r.window==window and r.mode==mode,'wrong parent account identity');before=C.prefix_view(r);original=r.inputs
 m=identity['inputs'][window];E.require(P.sha(m['path'])==m['sha256'],'month manifest changed');inputs=MonthInputs(m['path'])
 E.require(inputs.m['files']==original.m['files'] and inputs.m['extensions']==original.m['extensions'],'old complete input prefix changed')
 r.month_old_inputs=original;r.month_old_certificates=copy.deepcopy(r.authority.certificates)
 a=r.account;market=H.HistoricalMarket(inputs);a.market.inputs=inputs;a.market.native.raw=market.native.raw;a.market.native.actions=market.native.actions;a.market.native.bundle.manifest_path=inputs.path;a.facts.inputs=inputs;r.inputs=inputs
 a.__class__=MonthAccount;a.month_generations={r.last_completed_event.date().isoformat():a.canonical_binding}
 r.__class__=MonthRunner;a.owner=r;r.month_import=dict(parent=str(p),parent_sha256=rec['sha256'],parent_cursor=str(r.last_completed_event),old_manifest_sha256=P.sha(original.path),month_manifest_sha256=P.sha(inputs.path),no_reset=True)
 r.execution_grant_history=[];r.execution_grant_record=None
 E.require(C.prefix_view(r)==before,'month horizon changed complete old prefix')
 r.accept_grant(grant);r.assert_observers()
 for c in r.authority.certificates.values():r.verify_native(c)
 out=Path(out);out.mkdir(parents=True,exist_ok=False);r.checkpoint(out/'IMPORT.pkl');E.IO.write_json(out/'IMPORT.json',dict(prefix_exact=True,prefix_hash=E.digest(before),month_import=r.month_import,binding=r.binding()),encoder=E.encode)
 return r
