"""Explicit same-account August horizon. Original C/R0 economics unchanged."""
from pathlib import Path
import sys,json,copy,pickle,hashlib
import pandas as pd
HERE=Path(__file__).resolve().parent;W=HERE.parent
sys.path.insert(0,str(W/'g-s-C-R0-C20-budget250-v2-20261102'));import budget250 as B
J=B.X;M=J.M;E=J.E;R=J.R;sha=J.sha;read=J.read;save=J.save
CAP=250000;AUTH=HERE/'AUTHORIZATION.json';IDENTITY=HERE/'INPUT_IDENTITY.json'

class Inputs(M.MonthInputs):
 def __init__(self,path):self.aug_objects={};self.aug_frames={};self.aug_verified=set();super().__init__(path)
 def aug_ref(self,key):
  rec=self.m['continuation_extension'][key];p=self.root/rec['path']
  if key not in self.aug_verified:E.require(sha(p)==rec['sha256'],'August input changed '+key);self.aug_verified.add(key)
  return p
 def obj(self,key):
  base=super().obj(key)
  if key not in self.m['continuation_extension']:return base
  if key not in self.aug_objects:
   more=read(self.aug_ref(key))
   if key=='metadata':
    result=copy.deepcopy(base)
    for sid,rs in more.items():result[sid]['structure_observations']+=rs
   else:result=copy.deepcopy(base)+more
   self.aug_objects[key]=result
  return self.aug_objects[key]
 def table(self,key):
  base=super().table(key)
  if key not in self.m['continuation_extension']:return base
  if key not in self.aug_frames:self.aug_frames[key]=pd.concat([base,pd.read_parquet(self.aug_ref(key))],ignore_index=True)
  return self.aug_frames[key]

def guard():
 a=read(AUTH);i=read(IDENTITY)
 E.require(a['parent_approved'] and a['financial_events_authorized'] and a['scope']=='FOUR_OWN_JUL31_ACCOUNTS_AUGUST_ONLY','explicit root grant required')
 E.require(a['end']=='2025-08-29' and a['start']=='2025-08-01' and a['technical_ceiling']==CAP,'wrong horizon/technical ceiling')
 E.require(a['input_identity_sha256']==sha(IDENTITY),'new horizon identity changed')
 for p,h in a['sources'].items():E.require(sha(p)==h,'August frozen source changed '+p)
 return a,i

def economic(r):
 x=copy.deepcopy(r.observable(r.last_completed_event))
 for k in ['input_manifest','input_sha256','august_horizon','pure_projection_cache']:x.pop(k,None)
 return dict(observable=x,lifecycle=r.lifecycle,last_stock_state=r.last_stock_state,cursor=r.cursor,goal_intents=r.goal_intents,busy=r._busy_goals,active_intents=r.active_intents,rank_bindings=r.rank_bindings,native_audit=r.account.audit_log,native_decisions=r.account.decisions,mapping=r.mapping,events=r.events,action_log=r.action_log)

def read_json_view(r):return json.loads(json.dumps(r.observable(r.last_completed_event),default=E.encode))

def legacy_view(r):
 v=object.__new__(r.aug_old_class);v.__dict__.update(r.__dict__);v.inputs=r.aug_old_inputs
 E.require(v.source_binding()==r.aug_old_source,'old source view changed')
 return v

_PREVIOUS_APPROVED=R.approved_payload
def approved_payload(r,cid,sid,*,full_verify=True):
 if hasattr(r,'aug_old_certificates') and cid in r.aug_old_certificates:
  return _PREVIOUS_APPROVED(legacy_view(r),cid,sid,full_verify=full_verify)
 return _PREVIOUS_APPROVED(r,cid,sid,full_verify=full_verify)
R.approved_payload=approved_payload

def legacy_proof(r,c):
 cid=c['certificate_id'];E.require(c==r.aug_old_certificates[cid],'imported certificate changed')
 E.require(cid==E.digest({k:v for k,v in c.items() if k!='certificate_id'}),'old certificate body hash')
 v=r.trusted[c['trusted_id']];s,ds,e,bb=v['snapshot'],v['demands'],v['evidence'],v['budget_before']
 E.require(c['trusted_id']==E.digest(dict(s=s,ds=ds,e=e,bb=bb)) and c['snapshot_hash']==E.digest(s),'old trusted input changed')
 E.require(c['known_at']==s['at'] and c['deadline']==s['deadline'] and c['target_id']==s['target_id'],'old authorization clock changed')
 E.require(c['receipt_bindings']=={d['sid']:d['receipt_binding'] for d in ds},'old receipt bindings changed')
 result=r.aug_old_projections[cid]
 E.require(E.digest(result)==c['projection_hash'] and c['Q']==result['Q'] and c['D']==result['D'],'old audited projection changed')
 E.require(result['analysis_only'] and not result['submit_allowed'],'old result classification changed')
 return result

def exact250(r,s,ds,e,bb):
 cls=R.M.BatchBook if r.mode=='C_BATCH20' else R.M.OffBook
 book=cls.loads(bb,trusted_sha256=hashlib.sha256(bb.encode()).hexdigest(),account_id=s['account_id'],source_binding=E.digest(s),actual_commitments=json.loads(bb)['body']['lines'])
 if r.mode=='C_BATCH20':return R.M.BC.solve_C20(s,ds,e,book=book,max_native_checks=CAP)
 result=R.M.C.solve_C(s,ds,e,max_native_checks=CAP);working=copy.deepcopy(book)
 working.approve(book.batch['id']+'|complete_target_plan',{str(p['layer']):p['q'] for p in result['donors']['rows']},target_binding=E.digest(dict(Q=result['Q'],receipts=[d['receipt_id'] for d in ds])))
 return dict(result,budget_before=bb,budget_after=working.dumps())

class AugustMixin:
 def __init__(self,*a,**kw):raise RuntimeError('explicit same-account verified July31 import only')
 def source_binding(self):
  # Canonical full publication is policy source; actual full/truncated storage
  # and every byte hash are separately mandatory in binding()/guard().
  x=dict(self.aug_old_source);x.update({str(p):sha(p) for p in [HERE/'august_runtime.py',HERE/'run_august.py',IDENTITY,AUTH]})
  x[self.aug_full_manifest]=self.aug_full_sha
  return x
 def binding(self):
  guard();return dict(scope='SAME_ACCOUNT_AUGUST_ONLY',cell=self.aug_cell,branch=self.aug_branch,mode=self.mode,window=self.window,source=self.source_binding(),engine=E.IO.runner_identity(self),input_loader=E.IO._class_identity(type(self.inputs)),account_class=E.IO._class_identity(type(self.account)),input_manifest=str(self.inputs.path),input_sha256=sha(self.inputs.path),canonical_input_manifest=self.aug_full_manifest,canonical_input_sha256=self.aug_full_sha,old_import=self.aug_import,old_certificate_ids=sorted(self.aug_old_certificates),technical_ceiling=CAP,authorization_sha256=sha(AUTH),start='2025-08-01',end='2025-08-29')
 def execution_guard(self,day):
  guard();E.require(day in self.inputs.days and '2025-08-01'<=day<='2025-08-29','outside August grant')
  if day>'2025-08-01':
   p=HERE/'gates'/self.aug_cell/'GATE.json';E.require(self.aug_branch=='full' and p.exists() and read(p)['passed'],'this account Aug1 physical/restart gate required')
 def _solve(self,s,ds,e,bb):return J.memo_solve(self,lambda *x:exact250(self,*x),s,ds,e,bb)
 def verify_native(self,c):
  if c['certificate_id'] in self.aug_old_certificates:return legacy_proof(self,c)
  return R.M.Runner.verify_native(self,c)
 def step(self,day,phase):
  self.execution_guard(day);E.require(E.iso(day+('T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'))>self.last_completed_event,'completed event replay forbidden')
  return M.H.HistoricalRunner.step(self,day,phase)
 def corporate_actions(self,day):
  self.execution_guard(day);E.require(E.iso(day+'T00:00:00+08:00')>self.last_completed_event,'completed ACTION replay forbidden')
  return M.P.HistoricalRunner.corporate_actions(self,day)
 def observable(self,at):
  x=super().observable(at);x['august_horizon']=dict(cell=self.aug_cell,branch=self.aug_branch,imported_from=self.aug_import,authorization_sha256=sha(AUTH));return x
 @classmethod
 def restore(cls,path):
  guard();p=Path(path);s=read(p.with_suffix('.provenance.json'));E.require(sha(p)==s['checkpoint_sha256'],'new checkpoint byte hash')
  r=pickle.loads(p.read_bytes());r.account.owner=r
  E.require(type(r) is cls and r.binding()==s['binding'] and E.IO.runner_identity(r)==s['engine_identity'],'August actual source/engine/input mismatch')
  r.assert_observers()
  for c in r.authority.certificates.values():
   if c['certificate_id'] in r.aug_old_certificates:legacy_proof(r,c)
   else:
    v=r.trusted[c['trusted_id']];saved=next(z['projection'] for z in r.results if z['certificate']['certificate_id']==c['certificate_id'])
    E.require(c['certificate_id']==E.digest({k:x for k,x in c.items() if k!='certificate_id'}) and c['trusted_id']==E.digest(dict(s=v['snapshot'],ds=v['demands'],e=v['evidence'],bb=v['budget_before'])),'new saved trusted hash changed')
    E.require(c['source_binding']==r.source_binding() and c['projection_hash']==E.digest(saved) and c['Q']==saved['Q'] and c['D']==saved['D'],'new source/saved result changed')
  return r

class BaselineRunner(AugustMixin,M.MonthRunner):pass
class R0Runner(AugustMixin,J.Runner):pass

def import_account(cell,branch,out):
 a,i=guard();rec=i['accounts'][cell];cp=Path(rec['checkpoint']);side=read(cp.with_suffix('.provenance.json'))
 E.require(sha(cp)==rec['checkpoint_sha256']==side['checkpoint_sha256'],'original own July31 checkpoint changed')
 r=pickle.loads(cp.read_bytes());r.account.owner=r
 E.require(r.binding()==side['binding'] and E.IO.runner_identity(r)==side['engine_identity'],'original actual source/class binding mismatch')
 r.assert_observers();before=E.digest(economic(r));oldclass=type(r);oldsource=r.source_binding();oldinputs=r.inputs
 E.require(str(r.last_completed_event)=='2025-07-31 15:10:00+08:00' and r.window=='2025_26','wrong own-account prefix')
 # Audit-frozen old outputs are reused: validate full immutable bodies and all
 # original source files. Never rewrite old cert/source or recompute finance.
 certs=copy.deepcopy(r.authority.certificates);projections={z['certificate']['certificate_id']:copy.deepcopy(z['projection']) for z in r.results}
 checked={}
 for c in certs.values():
  for p,h in c['source_binding'].items():
   if p.startswith('/') and p not in checked:E.require(sha(p)==h,'old certificate source changed '+p);checked[p]=h
 E.require(set(certs)==set(projections),'old certificates/results mismatch')
 desc=i['inputs'][branch];E.require(sha(desc['path'])==desc['sha256'],'new branch input changed');inputs=Inputs(desc['path'])
 for g in ['files','extensions','month_extension']:E.require(inputs.m[g]==oldinputs.m[g],'original input group prefix changed '+g)
 r.aug_cell=cell;r.aug_branch=branch;r.aug_old_class=oldclass;r.aug_old_source=oldsource;r.aug_old_inputs=oldinputs;r.aug_old_certificates=certs;r.aug_old_projections=projections
 r.aug_full_manifest=i['inputs']['full']['path'];r.aug_full_sha=i['inputs']['full']['sha256']
 r.aug_import=dict(checkpoint=str(cp),checkpoint_sha256=sha(cp),old_engine=side['engine_identity'],old_binding=side['binding'],old_cursor=str(r.last_completed_event),old_economic_sha256=before,old_certificates_immutable=True,no_reset=True)
 provider=M.H.HistoricalMarket(inputs);acc=r.account
 acc.market.inputs=inputs;acc.market.native.raw=provider.native.raw;acc.market.native.actions=provider.native.actions;acc.market.native.bundle.manifest_path=inputs.path;acc.facts.inputs=inputs;r.inputs=inputs
 r.__class__=R0Runner if cell.endswith('_R0') else BaselineRunner;acc.owner=r
 r._pure_projection_memo=None;r._memo_hits=0;r._memo_misses=0
 E.require(E.digest(economic(r))==before,'horizon changed complete prior economic/strategy prefix')
 for c in certs.values():legacy_proof(r,c)
 r.assert_observers();out=Path(out);out.mkdir(parents=True,exist_ok=False);r.checkpoint(out/'IMPORT.pkl');save(out/'IMPORT.json',dict(passed=True,before=before,after=E.digest(economic(r)),source_restore=True,source_files=checked,original_certificates_reused_not_rewritten=True,old_class=str(oldclass),new_class=str(type(r)),account_class_unchanged=True,input_prefix_exact=True,financial_events=0))
 return r
