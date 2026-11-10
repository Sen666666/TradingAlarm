"""Explicit same-account C horizon import. No reset or old-class substitution."""
from pathlib import Path
from dataclasses import asdict
import json,copy,pickle,sys,hashlib
HERE=Path(__file__).resolve().parent;W=HERE.parent;OLD=W/'g-s-C-two-day-finance-20261102'
sys.path.insert(0,str(OLD));import provider_fix1 as F
P=F.P;E=F.E;H=P.H
sys.path.insert(0,str(W/'g-s-historical-native-nextsession-20261101'));import gs_next_session as X
DATES={'2022':'2022-01-06','2025_26':'2025-07-03'}
def read(p):return json.loads(Path(p).read_text())
def guard():
 a=read(HERE/'AUTHORIZATION.json')
 E.require(a['parent_approved'] and a['scope']=='C_FOUR_NEXT_SESSIONS_ONLY','explicit next-session authorization required')
 E.require(P.sha(HERE/'INPUT_FREEZE.json')==a['input_freeze_sha256'],'input freeze body changed')
 for path,h in a['sources'].items():E.require(P.sha(path)==h,'next-session source changed '+path)
 for k in DATES:E.require(a['sessions'][k]==DATES[k],'authorized day changed')
 return a
def prefix_view(r):
 x=copy.deepcopy(r.observable(r.last_completed_event))
 # These two fields explicitly describe the new input storage identity.
 x.pop('input_manifest',None);x.pop('input_sha256',None)
 return dict(observable=x,lifecycle=r.lifecycle,last_stock_state=r.last_stock_state,cursor=r.cursor,goal_intents=r.goal_intents,busy=r._busy_goals,active_intents=getattr(r,'active_intents',None),rank_bindings=r.rank_bindings)
class HorizonAccount(P.HistoricalAccount):
 def receipt_verified(self,c):
  if c is None:return False
  bank=self.canonical_generations.get(c.source_binding)
  if bank is None:return False
  # Same original checker, with the exact generation selected by that record.
  view=object.__new__(P.HistoricalAccount);view.__dict__.update(self.__dict__)
  view.canonical_registry=bank;view.canonical_binding=c.source_binding
  return P.HistoricalAccount.receipt_verified(view,c)
 def select_generation(self,at):
  key=self.next_canonical_binding if at.date().isoformat()>self.canonical_old_end else self.old_canonical_binding
  self.canonical_binding=key;self.canonical_registry=self.canonical_generations[key]
class HorizonRunner(F.FixedRunner):
 def __init__(self,*a,**kw):raise RuntimeError('explicit verified same-account import only')
 def source_binding(self):
  x=super().source_binding()
  x.update({str(p):P.sha(p) for p in [HERE/'c_horizon.py',HERE/'day_driver.py',HERE/'AUTHORIZATION.json',HERE/'INPUT_FREEZE.json',self.inputs.path]})
  return x
 def binding(self):
  x=super().binding();x.update(days=P.EXPECTED[self.window]+[DATES[self.window]],original_prefix_days=P.EXPECTED[self.window],allowed_next_session=DATES[self.window],branch=self.horizon_branch,
    extension_files=self.inputs.m['extensions'],horizon_import=self.horizon_import,account_class=E.IO._class_identity(type(self.account)),input_loader=E.IO._class_identity(type(self.inputs)))
  return x
 def verify_native(self,cert):
  if cert['certificate_id'] in self.horizon_old_certificates:
   E.require(cert==self.horizon_old_certificates[cert['certificate_id']],'old certificate body changed')
   view=object.__new__(F.FixedRunner);view.__dict__.update(self.__dict__);view.inputs=self.horizon_old_inputs
   return F.FixedRunner.verify_native(view,cert)
  return super().verify_native(cert)
 def stock_packet(self,at):
  self.account.select_generation(at);return super().stock_packet(at)
 def industry_input(self,at):
  x=super().industry_input(at)
  # Attribute to the frozen ORIGINAL H1 source rather than branch-local
  # storage: both branches read the identical as-of row, not the future row.
  source='/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/h1.npz'
  x['source_path']=source;x['source_sha256']=read(X.O/'inputs/SOURCE_BINDINGS.json')[source]
  return x
 def step(self,day,phase):
  guard();E.require(day==DATES[self.window],'only one additional authorized financial session')
  return H.HistoricalRunner.step(self,day,phase)
 def corporate_actions(self,day):
  guard();E.require(day==DATES[self.window],'only authorized next action day')
  return super().corporate_actions(day)

def import_account(window,mode,branch,out):
 auth=guard();cell=auth['cells'][window+'-'+mode];cp=Path(cell['checkpoint']);E.require(P.sha(cp)==cell['checkpoint_sha256'],'old terminal checkpoint changed')
 r=F.FixedRunner.restore(cp);before=prefix_view(r);old_inputs=r.inputs
 E.require(r.window==window and r.mode==mode and str(r.last_completed_event)==cell['cursor'],'wrong account or cursor')
 source=next(z for z in read(HERE/'INPUT_FREEZE.json')['rows'] if z['window']==window);manifest=Path(source['full' if branch=='full' else 'physical'])
 E.require(P.sha(manifest)==source['full_sha256' if branch=='full' else 'physical_sha256'],'unapproved horizon manifest')
 inputs=X.ExtendedInputs(manifest);E.require(inputs.m['files']==old_inputs.m['files'],'old input file prefix changed')
 oldbank=copy.deepcopy(r.account.canonical_registry);oldbinding=r.account.canonical_binding
 # Future control receipts never enter a current canonical generation.
 newbank={z['receipt_id']:H.payload_json(z) for z in inputs.obj('receipts') if z['confirmed_day']<=DATES[window]};newbinding=E.digest(newbank)
 E.require(all(newbank.get(k)==v for k,v in oldbank.items()),'old canonical payload changed')
 r.horizon_old_inputs=old_inputs;r.horizon_old_certificates=copy.deepcopy(r.authority.certificates)
 a=r.account;provider=H.HistoricalMarket(inputs)
 a.market.inputs=inputs;a.market.native.raw=provider.native.raw;a.market.native.actions=provider.native.actions;a.market.native.bundle.manifest_path=inputs.path;a.facts.inputs=inputs;r.inputs=inputs
 a.__class__=HorizonAccount;a.canonical_generations={oldbinding:oldbank,newbinding:newbank};a.old_canonical_binding=oldbinding;a.next_canonical_binding=newbinding;a.canonical_old_end=P.EXPECTED[window][-1]
 a.canonical_registry=oldbank;a.canonical_binding=oldbinding
 r.__class__=HorizonRunner;r.horizon_branch=branch;r.horizon_import=dict(checkpoint=str(cp),checkpoint_sha256=P.sha(cp),old_cursor=cell['cursor'],old_manifest_sha256=P.sha(old_inputs.path),new_manifest_sha256=P.sha(manifest),old_canonical_binding=oldbinding,new_canonical_binding=newbinding,no_account_reset=True,old_certificates_not_rewritten=True)
 a.owner=r;E.require(prefix_view(r)==before,'horizon import changed original complete economic/strategy prefix')
 r.assert_observers()
 for c in r.authority.certificates.values():r.verify_native(c)
 out=Path(out);out.mkdir(parents=True,exist_ok=False);r.checkpoint(out/'IMPORT.pkl')
 E.IO.write_json(out/'IMPORT.json',dict(prefix_full_state_exact=True,before_sha256=E.digest(before),after_sha256=E.digest(prefix_view(r)),import_evidence=r.horizon_import,binding=r.binding()),encoder=E.encode)
 return r
