"""Exactly one source-backed next session per old account; no first-day replay."""
from pathlib import Path
import sys,json,subprocess,traceback,time
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE.parent))
from gs_next_session import *
from dataclasses import replace
from datetime import datetime

def snapshot(r,out,name):
 out=Path(out);p=out/(name+'.pkl');r.checkpoint(p);save(out/(name+'.json'),r.observable(r.last_completed_event))
 save(p.with_suffix('.driver.json'),dict(driver=str(Path(__file__)),driver_sha256=sha(__file__),trading_binding=r.binding()))
 return state_hash(r.observable(r.last_completed_event))
def event(r,out,day,phase):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 at=iso(day+('T00:00:00+08:00' if phase=='ACTION' else ('T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00')))
 r.checkpoint(out/'BEFORE_EVENT.pkl');save(out/'CURSOR.json',dict(phase=phase,at=at,last_completed=r.last_completed_event))
 try:
  if phase=='ACTION':r.corporate_actions(day)
  else:r.step(day,phase)
  h=snapshot(r,out,day+'-'+phase);print('COMPLETED_NEXT',r.window,day,phase,h[:12],len(r.account.fills),flush=True)
 except BaseException as e:
  IO.write_pickle(out/'FAILED_WORKING_STATE.pkl',r)
  save(out/'ERROR.json',dict(target_at=at,phase=phase,last_completed=r.last_completed_event,error=repr(e),traceback=traceback.format_exc(),partial_event_state_preserved=True,no_auto_retry=True))
  raise
 return r

def close_worker(cp,out,day):
 r=NextSessionRunner.restore(cp);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 save(out/'RESTORED.json',dict(at=r.last_completed_event,complete_economic_state_hash=state_hash(r.observable(r.last_completed_event)),binding=r.binding()))
 r=event(r,out,day,'CLOSE');save(out/'DONE.json',dict(completed=True,at=r.last_completed_event,actual_completed_at=datetime.now().astimezone().isoformat()))

def preflight():
 rows=[]
 for k,s in SPECS.items():
  r=import_checkpoint(k,O/'inputs'/k/'MANIFEST.json',finance=False)
  assert len(r.account.pending)==(245 if k=='2025_26' else 136)
  old_receipts=[i['receipt'] for i in r.account.pending if i.get('receipt')]
  assert all(r.account.receipt_verified(c) and c.source_binding==r.account.old_canonical_binding for c in old_receipts)
  at=iso(s['next_day']+'T15:10:00+08:00');r.account.market.refresh(at);packet=r.stock_packet(at)
  new_receipts=[x['receipt'] for x in packet.values() if x.get('receipt')]
  assert new_receipts and all(r.account.receipt_verified(c) and c.source_binding==r.account.new_canonical_binding for c in new_receipts)
  assert all(not r.account.receipt_verified(replace(c,source_binding=r.account.old_canonical_binding)) for c in new_receipts)
  rows.append(dict(window=k,pending_old=len(r.account.pending),valid_old_receipt_objects=len(old_receipts),valid_new_receipt_objects=len(new_receipts),wrong_generation_rejected=True,financial_events=0))
 save(HERE/'MAPPING_GATE.json',dict(passed=True,rows=rows,financial_events=0))

def main():
 original_guard();assert LD.read(O/'coverage-003/GATE.json')['passed']
 targets={n:HERE/n for n in ('failure','2025_26','2022')};IO.prepare_targets(targets,directory_keys=tuple(targets))
 sources={str(p):sha(p) for p in list(O.glob('*.py'))+[Path(__file__)]}
 inputs={k:dict(manifest=str((O/'inputs'/k/'MANIFEST.json').resolve()),manifest_sha256=sha(O/'inputs'/k/'MANIFEST.json')) for k in SPECS}
 save(O/'NEXT_SESSION_AUTHORIZATION.json',dict(parent_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',financial_scope={k:s['next_day'] for k,s in SPECS.items()},sources=sources,inputs=inputs,
   original_source_only=True,not_technical_fixture_calendar=True,no_old_financial_events=True,unchanged_policy_contract=H.COMPOSITE,stop_on_unsupported=True))
 preflight();save(HERE/'STARTED.json',dict(actual_started_at=datetime.now().astimezone().isoformat(),sources=sources))
 done=[]
 try:
  for k,s in SPECS.items():
   out=HERE/k
   if (out/'IMPORT.pkl').exists():raise ValueError('existing financial import; no silent rerun')
   r=import_checkpoint(k,O/'inputs'/k/'MANIFEST.json',finance=True)
   save(out/'IMPORT.json',dict(parent_checkpoint=str(old_checkpoint(k)),parent_sha256=sha(old_checkpoint(k)),cursor=r.last_completed_event,
      available=r.account.available,positions=len(r.account.positions),pending=len(r.account.pending),exits=len(r.account.exits),import_evidence=r.horizon_import,
      complete_economic_state_unchanged=True,binding=r.binding()))
   snapshot(r,out,'IMPORT')
   day=s['next_day']
   if r.inputs.actions(day):r=event(r,out,day,'ACTION')
   r=event(r,out,day,'OPEN');cp=out/(day+'-OPEN.pkl');before=state_hash(r.observable(r.last_completed_event))
   # Only CLOSE executes in this child; OPEN/actions and old sessions are not replayed.
   result=subprocess.run([sys.executable,'-B',str(Path(__file__)),'close',str(cp),str(out/'close'),day],check=False)
   if result.returncode:
    child=LD.read(out/'close/ERROR.json') if (out/'close/ERROR.json').exists() else dict(error='child failed before event export')
    save(HERE/'STOPPED.json',dict(window=k,earliest_new_block=child,completed_windows=done,other_window_financial_events_not_started=True))
    raise RuntimeError('authorized next session stopped; see child failure state')
   assert LD.read(out/'close/RESTORED.json')['complete_economic_state_hash']==before
   r=NextSessionRunner.restore(out/'close'/(day+'-CLOSE.pkl'))
   save(out/'DONE.json',dict(completed=True,at=r.last_completed_event,NAV=r.account.nav(r.last_completed_event),available=r.account.available,
      total_fills=len(r.account.fills),positions=len(r.account.positions),pending=len(r.account.pending),pending_exits=len(r.account.exits),crossprocess_close_restore_exact=True))
   done.append(k)
  assert sources=={str(p):sha(p) for p in list(O.glob('*.py'))+[Path(__file__)]}
  save(HERE/'DONE.json',dict(completed=True,windows=done,actual_completed_at=datetime.now().astimezone().isoformat(),no_previous_financial_sessions_replayed=True))
 except BaseException as e:
  save(HERE/'failure/ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),no_automatic_rerun=True));raise
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='close':close_worker(sys.argv[2],sys.argv[3],sys.argv[4])
 else:main()
