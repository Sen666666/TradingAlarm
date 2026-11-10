"""Explicit input-horizon import. No old account reset, order rewrite or policy change."""
from common_next import *
import pandas as pd
from dataclasses import replace

class ExtendedInputs(LD.HistoricalInputs):
 def __init__(self,path):
  self.merged_objects={};self.merged_frames={};self.extra_verified=set();super().__init__(path)
  assert self.m['horizon_extension']['old_end']==SPECS[self.key]['old_end']
  assert self.m['horizon_extension']['authorized_next_session']==SPECS[self.key]['next_day']
 def extra(self,key):
  r=self.m['extensions'][key];p=self.root/r['path']
  if key not in self.extra_verified:
   if sha(p)!=r['sha256']:raise ValueError('extension hash changed '+key)
   self.extra_verified.add(key)
  return p
 def obj(self,key):
  if key=='payments':
   if key not in self.merged_objects:self.merged_objects[key]=LD.read(self.extra(key))
   return self.merged_objects[key]
  base=super().obj(key)
  if key not in self.m['extensions']:return base
  if key not in self.merged_objects:
   extra=LD.read(self.extra(key))
   if key=='metadata':
    out=copy.deepcopy(base)
    for sid,rows in extra.items():
     assert all(r['observed_day']>self.m['horizon_extension']['old_end'] for r in rows)
     out[sid]['structure_observations']+=rows
   else:
    out=copy.deepcopy(base)+extra
   self.merged_objects[key]=out
  return self.merged_objects[key]
 def table(self,key):
  base=super().table(key)
  if key not in self.m['extensions']:return base
  if key not in self.merged_frames:
   extra=pd.read_parquet(self.extra(key));assert extra.empty or extra.day.gt(self.m['horizon_extension']['old_end']).all()
   self.merged_frames[key]=pd.concat([base,extra],ignore_index=True)
  return self.merged_frames[key]
 def payments_due(self,at):
  at=iso(at) if isinstance(at,str) else at
  if at.tzinfo is None:raise ValueError('aware payment cursor required')
  seen={};rows=super().payments_due(at)+[r for r in self.obj('payments') if r.get('paid_at') and iso(r['paid_at'])<=at]
  for r in rows:seen[(r['sid'],r['source_id'],r['effective_date'],r['paid_at'])]=r
  return list(seen.values())

class GenerationAccount(H.HistoricalAccount):
 def receipt_verified(self,c):
  bank=self.canonical_generations.get(getattr(c,'source_binding',None))
  if bank is None or not isinstance(c,HistoricalReceipt) or c.source!='original_canonical_CP1_trace':return False
  if not c.payload_json or hashlib.sha256(c.payload_json.encode()).hexdigest()!=c.payload_sha256:return False
  if bank.get(c.event_id)!=c.payload_json:return False
  r=json.loads(c.payload_json)
  return r['canonical_series']==c.sid and r['receipt_id']==c.event_id and r['confirmed_day']==c.confirmed.date().isoformat() and r['formation_start_exclusive']==c.start.date().isoformat() and r['formation_end_inclusive']==c.end.date().isoformat() and not r['trace_unknown'] and c.scale=='21'
 def select_generation(self,at):
  key=self.new_canonical_binding if at.date().isoformat()>self.canonical_old_end else self.old_canonical_binding
  self.canonical_binding=key;self.canonical_registry=self.canonical_generations[key]

class NextSessionRunner(H.HistoricalRunner):
 def __init__(self,*args,**kwargs):raise RuntimeError("explicit verified horizon import required; no new account constructor")
 def stock_packet(self,at):
  self.account.select_generation(at)
  return super().stock_packet(at)
 def step(self,day,phase):
  if not self.finance_import_authorized or self.inputs.m['horizon_extension'].get('diagnostic'):raise ValueError('read-only diagnostic import cannot execute finance')
  if day!=self.authorized_next_session:raise ValueError('only the one explicitly authorized additional session may execute')
  return super().step(day,phase)
 def corporate_actions(self,day):
  if not self.finance_import_authorized or self.inputs.m['horizon_extension'].get('diagnostic'):raise ValueError('read-only diagnostic import cannot execute finance')
  if day!=self.authorized_next_session:raise ValueError('only authorized additional action cursor')
  return super().corporate_actions(day)
 def binding(self):
  result=super().binding();paths=list(O.glob('*.py'))+[self.inputs.path,O/'inputs/SOURCE_BINDINGS.json']
  result.update(policy='G_S_V2_R4_UNCHANGED_ECONOMICS_EXPLICIT_NEXT_SESSION_INPUT_IMPORT',authorized_next_session=self.authorized_next_session,
    extension_source_files={str(p):sha(p) for p in paths},extension_files=self.inputs.m['extensions'],input_loader_class=IO._class_identity(type(self.inputs)),
    actual_account_class=IO._class_identity(type(self.account)),actual_receipt_guard=IO._code_fingerprint(type(self.account).receipt_verified.__code__),
    import_evidence=self.horizon_import)
  return result


def economic_view(r):
 # This is the entire saved financial/decision/F1 view, not only cash/NAV.
 return normalize(r.observable(r.last_completed_event))

def install_inputs(r,inputs,*,finance):
 old_end=SPECS[r.window]['old_end'];newday=SPECS[r.window]['next_day']
 if finance and inputs.m['horizon_extension'].get('diagnostic'):raise ValueError('diagnostic future perturbation may not execute finance')
 oldbank=r.account.canonical_registry;oldbinding=r.account.canonical_binding;assert digest(oldbank)==oldbinding
 newbank=H.registry(inputs);newbinding=digest(newbank)
 assert all(newbank.get(k)==v for k,v in oldbank.items()),'old canonical prefix changed'
 # Replace immutable input views only. Runtime marks, counters, cash, inventory,
 # deadlines, ACT, all pending intents and accounting remain as restored.
 provider=H.HistoricalMarket(inputs);a=r.account
 a.market.inputs=inputs;a.market.native.raw=provider.native.raw;a.market.native.actions=provider.native.actions
 a.market.native.bundle.manifest_path=inputs.path;a.facts.inputs=inputs;r.inputs=inputs
 a.__class__=GenerationAccount
 a.canonical_generations={oldbinding:oldbank,newbinding:newbank};a.old_canonical_binding=oldbinding;a.new_canonical_binding=newbinding;a.canonical_old_end=old_end
 a.canonical_registry=oldbank;a.canonical_binding=oldbinding
 r.__class__=NextSessionRunner;r.authorized_next_session=newday;r.finance_import_authorized=finance
 r.horizon_import=dict(old_end=old_end,newday=newday,parent_checkpoint_sha256=sha(old_checkpoint(r.window)),
   parent_manifest_sha256=sha(H.INPUT/r.window/'MANIFEST.json'),extended_manifest_sha256=sha(inputs.path),
   old_canonical_binding=oldbinding,new_canonical_binding=newbinding,all_old_receipt_payloads_preserved=True,
   no_account_constructor_or_reset=True,original_trading_sources_sha256=sha(OLD/'SOURCE_FREEZE.json'))
 return r

def import_checkpoint(k,manifest,*,finance=True):
 original_guard()
 if finance:
  auth=LD.read(O/'NEXT_SESSION_AUTHORIZATION.json');expected=auth['inputs'][k]
  if Path(manifest).resolve()!=Path(expected['manifest']).resolve() or sha(manifest)!=expected['manifest_sha256']:raise ValueError('unapproved finance input horizon')
  for path,h in auth['sources'].items():
   if sha(path)!=h:raise ValueError('frozen next-session execution source changed')
 r=H.HistoricalRunner.restore(old_checkpoint(k));before=economic_view(r)
 assert r.last_completed_event==iso(SPECS[k]['old_end']+'T15:10:00+08:00')
 inputs=ExtendedInputs(manifest)
 parent=LD.read(H.INPUT/k/'MANIFEST.json')
 assert inputs.m['files']==parent['files'],'immutable first-two-day input file binding changed'
 for n,rec in parent['files'].items():assert sha(inputs.ref(n))==rec['sha256']
 r=install_inputs(r,inputs,finance=finance)
 assert economic_view(r)==before,'financial or original market state changed at horizon import'
 return r
