"""Export-only repair driver. All frozen trading sources remain unchanged.

The previous first CLOSE completed and checkpointed before a report hash failed.
Use the native audited dataclass encoder. Never replay that completed prefix.
"""
from pathlib import Path
import sys,json,subprocess,traceback,hashlib
HERE=Path(__file__).resolve().parent;PARENT=HERE.parent;sys.path.insert(0,str(PARENT))
from historical_binding import *
from run_prefixes import summary

def normalize(value):return json.loads(json.dumps(value,default=N.encode,sort_keys=True,allow_nan=False))
def state_hash(value):return hashlib.sha256(json.dumps(normalize(value),sort_keys=True,separators=(',',':')).encode()).hexdigest()
def save(p,x):IO.write_json(p,normalize(x))
def snapshot(r,out,label):
 out=Path(out);cp=out/(label+'.pkl');r.checkpoint(cp);state=r.observable(r.last_completed_event)
 save(out/(label+'.json'),state)
 save(cp.with_suffix('.export-driver.json'),dict(driver_path=str(Path(__file__)),driver_sha256=sha(__file__),trading_binding=r.binding(),scope='serialization only; no overridden trading function'))
 return state_hash(state)
def execute(r,out,days):
 out=Path(out);out.mkdir(parents=True,exist_ok=True)
 for day in days:
  for phase in (['ACTION'] if r.inputs.actions(day) else [])+['OPEN','CLOSE']:
   at=iso(day+('T00:00:00+08:00' if phase=='ACTION' else ('T09:30:00+08:00' if phase=='OPEN' else 'T15:10:00+08:00')))
   IO.write_pickle(out/'BEFORE_EVENT.pkl',r);save(out/'CURSOR.json',dict(at=at,phase=phase,last_completed=r.last_completed_event))
   try:
    if phase=='ACTION':r.corporate_actions(day)
    else:r.step(day,phase)
    h=snapshot(r,out,day+'-'+phase);print('COMPLETED',r.window,day,phase,h[:12],len(r.account.fills),flush=True)
   except BaseException as e:
    IO.write_pickle(out/'FAILED_WORKING_STATE.pkl',r);save(out/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),target_at=at,last_completed=r.last_completed_event,no_auto_retry=True));raise
 return r

def resume(cp,out,second):
 r=HistoricalRunner.restore(cp);out=Path(out);out.mkdir(parents=True,exist_ok=True)
 save(out/'RESTORED.json',dict(at=r.last_completed_event,state_sha256=state_hash(r.observable(r.last_completed_event)),binding=r.binding(),export_driver_sha256=sha(__file__)))
 if second<=r.last_completed_event.date().isoformat():raise ValueError('completed prefix replay forbidden')
 r=execute(r,out,[second]);save(out/'DONE.json',dict(completed=True,actual_completed_at=datetime.now().astimezone().isoformat(),state_sha256=state_hash(r.observable(r.last_completed_event))))

def main():
 root=PARENT/'runs';outmeta=HERE/'completion';outmeta.mkdir(exist_ok=False)
 auth=LD.read(PARENT/'FULL_PREFIX_AUTHORIZATION.json')
 assert auth['financial_scope']=={'2022':['2022-01-04','2022-01-05'],'2025_26':['2025-07-01','2025-07-02']}
 assert auth['sources']=={str(p):sha(p) for p in PARENT.glob('*.py')},'frozen financial source changed'
 save(HERE/'EXPORT_FIX_MANIFEST.json',dict(reason='LD JSON hash lacked HistoricalReceipt encoder after completed Jan4 CLOSE',
  prior_error=str(root/'2022/primary/ERROR.json'),financial_sources_unchanged=auth['sources'],repair_driver_sha256=sha(__file__),
  output_encoder='native_capital.encode: explicit dataclasses, dates, Decimal',no_financial_prefix_replay=True,
  authorized_economic_dates=auth['financial_scope']))
 save(outmeta/'STARTED.json',dict(at=datetime.now().astimezone().isoformat(),driver_sha256=sha(__file__)))
 results=[]
 try:
  for window in ('2022','2025_26'):
   out=root/window;first,second=auth['financial_scope'][window]
   pdir=out/'primary'
   if window=='2022':
    cp=pdir/(first+'-CLOSE.pkl');r=HistoricalRunner.restore(cp)
    assert r.last_completed_event==iso(first+'T15:10:00+08:00')
    assert LD.read(pdir/(first+'-CLOSE.json'))==normalize(r.observable(r.last_completed_event))
    save(outmeta/'2022-validated-export-import.json',dict(checkpoint=str(cp),sha256=sha(cp),last_completed=r.last_completed_event,
      existing_json_equals_complete_state=True,state_hash=state_hash(r.observable(r.last_completed_event)),
      input_source_binding_preserved=True,Jan4_not_rerun=True))
   else:
    r=HistoricalRunner(window);r=execute(r,pdir,[first]);cp=pdir/(first+'-CLOSE.pkl')
   before=state_hash(r.observable(r.last_completed_event))
   subprocess.run([sys.executable,'-B',str(Path(__file__)),'resume',str(cp),str(out/'primary-resume'),second],check=True)
   assert LD.read(out/'primary-resume/RESTORED.json')['state_sha256']==before
   r=HistoricalRunner.restore(out/'primary-resume'/(second+'-CLOSE.pkl'))
   assert len(r.account.fills)>0,'all-zero prefix cannot be a financial admission gate'
   bad=out/'wrong-binding.pkl';IO.write_bytes(bad,cp.read_bytes());side=json.loads(cp.with_suffix('.provenance.json').read_text());side['binding']['frozen']['R4']='0'*64;IO.write_json(bad.with_suffix('.provenance.json'),side)
   try:HistoricalRunner.restore(bad)
   except ValueError:pass
   else:raise AssertionError('wrong-source checkpoint accepted')
   q=HistoricalRunner(window,PARENT/'full-input-fixtures'/window/'MANIFEST.json');q=execute(q,out/'full-input-technical',[first,second])
   for day in (first,second):
    for phase in ('OPEN','CLOSE'):
     orig=out/('primary' if day==first else 'primary-resume')
     assert LD.read(orig/(day+'-'+phase+'.json'))==LD.read(out/'full-input-technical'/(day+'-'+phase+'.json')),(window,day,phase,'physical truncation differs')
   assert normalize(r.observable(r.last_completed_event))==normalize(q.observable(q.last_completed_event))
   record=summary(r);record.update(physical_prefix_all_four_events_exact=True,crossprocess_restore_full_state_exact=True,wrong_source_rejected=True)
   save(out/'SUMMARY.json',record);results.append(record)
  assert auth['sources']=={str(p):sha(p) for p in PARENT.glob('*.py')}
  save(outmeta/'DONE.json',dict(completed=True,actual_completed_at=datetime.now().astimezone().isoformat(),results=results,
    authoritative_prefixes=2,technical_replicas='same policy/dates only',financial_sources_unchanged=True,export_only_repair=True))
 except BaseException as e:
  save(outmeta/'ERROR.json',dict(error=repr(e),traceback=traceback.format_exc(),no_automatic_rerun=True,at=datetime.now().astimezone().isoformat()));raise
if __name__=='__main__':
 if len(sys.argv)>1 and sys.argv[1]=='resume':resume(sys.argv[2],sys.argv[3],sys.argv[4])
 else:main()
