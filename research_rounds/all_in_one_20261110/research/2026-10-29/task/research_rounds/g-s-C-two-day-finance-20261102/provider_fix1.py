"""Minimal real-input provider repair, not an economic-policy change.

Frozen solver cleanup requires a tuple rank even for fixed non-donor core.
Supply that layer's actual frozen creation key; never admit it as a donor.
Original entry, checkpoints, grants and native engine stay immutable.
"""
from pathlib import Path
import sys,json,hashlib,pickle,copy,argparse,datetime,importlib
import prefix_entry as P
E=P.E;HERE=Path(__file__).resolve().parent

def guard():
 a=P.read(HERE/'PROVIDER_REPAIR_AUTHORIZATION.json')
 E.require(a['source_sha256']==P.sha(__file__) and a['original_entry_sha256']==P.sha(HERE/'prefix_entry.py'),'repair source binding')
 E.require(a['engine_sha256']==P.sha(P.ENGINE/'native_c.py') and a['root_authorized_same_four_prefixes'],'repair economic scope')
 return a

class FixedRunner(P.HistoricalRunner):
 def __init__(self,mode,window):
  guard();self.legacy_cert_sources={};self.repair_import=None;self.core_rank_metadata=[]
  super().__init__(mode,window)
 def source_binding(self):
  out=super().source_binding();out.update({str(p):P.sha(p) for p in [Path(__file__),HERE/'PROVIDER_REPAIR_AUTHORIZATION.json']});return out
 def industry_input(self,at):
  e=super().industry_input(at)
  e['software_interface_repair']=dict(source_sha256=P.sha(__file__),numeric_input_unchanged=True,kind='non_donor_core_creation_rank_metadata')
  return e
 def provider(self,at,intents,evidence):
  s,ds,w=super().provider(at,intents,evidence);notes=[]
  for z in s['lots']:
   if z['rank_key'] is not None:continue
   E.require(z['role']=='core' and not z['B_donor_eligible'],'UNKNOWN real mobile ranking remains blocked')
   meta=self.account.capital_meta[z['id']];origin=self.account.supports[meta['order']]
   E.require(origin['role']=='core' and origin['use']=='T' and tuple(origin['priority'])==tuple(origin['dispatch']['original_priority']),'missing/changed actual core origin priority')
   from dispatch_order import freeze_priority
   freeze_priority(origin['priority'])
   z['rank_key']=list(origin['priority'])
   notes.append(dict(layer=z['id'],sid=z['sid'],origin_order=meta['order'],origin_at=origin['created_at'],rank_key=z['rank_key'],B_donor_eligible=False,role='core'))
  self.core_rank_metadata=notes
  return s,ds,w
 def verify_native(self,cert):
  old=self.legacy_cert_sources.get(cert['certificate_id'])
  if old is None:return super().verify_native(cert)
  E.require(cert['source_binding']==old,'legacy original authority source changed')
  # Pure original verifier view, no Account construction and no financial
  # event. Old grants are verified under their REAL old source, not rewritten.
  view=object.__new__(P.HistoricalRunner);view.__dict__.update(self.__dict__)
  return P.HistoricalRunner.verify_native(view,cert)
 def observable(self,at):
  x=super().observable(at);x.update(provider_repair=dict(source_sha256=P.sha(__file__),import_origin=self.repair_import,core_rank_metadata=self.core_rank_metadata));return x

def import_original(path,out):
 guard();r=P.HistoricalRunner.restore(path);at=r.last_completed_event
 before=E.digest(r.account.exported(at));old_binding=r.binding();oldclass=type(r).__module__+'.'+type(r).__qualname__
 legacy={cid:copy.deepcopy(c['source_binding']) for cid,c in r.authority.certificates.items()}
 r.__class__=FixedRunner;r.legacy_cert_sources=legacy;r.repair_import=dict(original_checkpoint=str(Path(path).resolve()),original_sha256=P.sha(path),original_class=oldclass,original_binding=old_binding,finance_before_sha256=before,financial_cursor=str(at),kind='explicit same-account provider-only identity import')
 r.core_rank_metadata=[];r.account.owner=r
 E.require(E.digest(r.account.exported(at))==before,'provider import changed account state')
 r.assert_observers()
 for c in r.authority.certificates.values():r.verify_native(c)
 out=Path(out);out.mkdir(parents=True,exist_ok=False);r.checkpoint(out/'IMPORTED.pkl');E.IO.write_json(out/'IMPORT_MANIFEST.json',r.repair_import,encoder=E.encode)
 return r

def main():
 p=argparse.ArgumentParser();p.add_argument('--window',choices=P.EXPECTED,required=True);p.add_argument('--mode',choices=['C10','C_BATCH20'],required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--import-checkpoint',type=Path);a=p.parse_args();grant=guard()
 original=P.read(HERE/f'AUTH_{a.window}_{a.mode}.json');E.require(original['parent_approved'] and original['historical_financial_events_authorized'],'original four-cell authorization')
 started=datetime.datetime.now(datetime.timezone.utc).isoformat()
 r=None
 try:
  if a.import_checkpoint:
   r=import_original(a.import_checkpoint,a.out)
   E.require(r.window==a.window and r.mode==a.mode,'wrong account import')
   at=r.last_completed_event;stage=r.close_stages[at.isoformat()]
   E.require(stage['necessary_done'] and stage['optional_status']=='failed_exception','resume only saved failed optional stage')
   evidence=r.industry_input(at);old=stage['evidence']
   E.require({k:v for k,v in evidence.items() if k!='software_interface_repair'}==old,'numeric/asof industry inputs changed')
   r.retry_optional(at,evidence,correction=dict(old_input=E.digest(old),new_input=E.digest(evidence),reason='explicit code-interface repair only; original industry values identical'))
   r.checkpoint(a.out/(at.date().isoformat()+'-CLOSE.pkl'));E.IO.write_json(a.out/(at.date().isoformat()+'-CLOSE.json'),r.observable(at),encoder=E.encode)
  else:
   a.out.mkdir(parents=True,exist_ok=False);r=FixedRunner(a.mode,a.window)
  for day in P.EXPECTED[a.window]:
   action_at=E.iso(day+'T00:00:00+08:00')
   if r.inputs.actions(day) and (r.last_completed_event is None or action_at>r.last_completed_event):r.corporate_actions(day);r.checkpoint(a.out/(day+'-ACTION.pkl'));E.IO.write_json(a.out/(day+'-ACTION.json'),r.observable(action_at),encoder=E.encode)
   for phase in ('OPEN','CLOSE'):
    at=E.iso(day+('T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00'))
    if r.last_completed_event is not None and at<=r.last_completed_event:continue
    r.step(day,phase);r.checkpoint(a.out/(day+'-'+phase+'.pkl'));E.IO.write_json(a.out/(day+'-'+phase+'.json'),r.observable(at),encoder=E.encode)
    if phase=='CLOSE':E.require(r.close_stages[at.isoformat()]['optional_status']=='succeeded','optional stage blocked')
  E.IO.write_json(a.out/'COMPLETED.json',dict(window=a.window,mode=a.mode,cursor=r.last_completed_event,started_at=started,completed_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),binding=r.binding(),original_authorization_sha256=P.sha(HERE/f'AUTH_{a.window}_{a.mode}.json'),repair_authorization_sha256=P.sha(HERE/'PROVIDER_REPAIR_AUTHORIZATION.json')),encoder=E.encode)
 except Exception as exc:
  a.out.mkdir(parents=True,exist_ok=True);E.IO.write_json(a.out/'ERROR.json',dict(cursor=r.last_completed_event if r else None,error=type(exc).__name__+': '+str(exc),account_created=r is not None),encoder=E.encode)
  if r:r.checkpoint(a.out/'failure-state.pkl')
  raise
if __name__=='__main__':importlib.import_module(Path(__file__).stem).main()
