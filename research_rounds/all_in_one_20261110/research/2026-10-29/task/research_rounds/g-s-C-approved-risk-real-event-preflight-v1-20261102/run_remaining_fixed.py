"""Bounded orchestrator of explicitly authorized next-OPEN pairs, no new rule."""
from pathlib import Path
import argparse,json,hashlib,subprocess,sys,time
R=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
read=lambda p:json.loads(Path(p).read_text())
DAYS=['2025-07-23','2025-07-04','2025-07-30']
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',choices=['C10','C_BATCH20'],required=True);a=p.parse_args()
 # First actual ON integration must have succeeded before more batches.
 first=read(R/'runs/C_BATCH20-2025-07-22-on/COMPLETED.json');assert first['risk']=='on'
 progress=[];t=time.monotonic()
 for day in DAYS:
  case=a.mode+'|'+day;cp=R/'imports'/(a.mode+'-'+day)/'import/IMPORT.pkl';assert cp.exists()
  for flag in ['off','on']:
   name=a.mode+'-'+day+'-'+flag;out=R/'runs'/name
   if out.exists():raise RuntimeError('Existing branch must be inspected, never auto-rerun '+str(out))
   for err in (R/'runs').glob('*/ERROR.json'):
    x=read(err)
    if 'name \'asdict\' is not defined' not in x['error']:raise RuntimeError('Other engineering failure remains '+str(err))
   g=read(R/'AUTHORIZATION_PROPOSAL.json');key=case+'|'+flag;cell=g['cells'][key]
   g.update(parent_approved=True,financial_events_authorized=True,cells={key:cell},resume_driver_sha256=sha(R/'run_prepared_fixed.py'),analysis_helper_sha256=sha(R/'event_comparison.py'),execution_gate_sha256=sha(R/'EXECUTION_GATE.json'),analysis_fix_gate_sha256=sha(R/'ANALYSIS_FIX_GATE.json'),orchestrator_sha256=sha(__file__),root_thread='01a1869e-bab0-73ad-a5ca-8b65eb61f01b',root_instruction='R0 native audit PASS; only Jul22/Jul23 and predeclared Pingan/Guangsheng next OPEN diagnostic branches after gates; no formal old account/source changes; no full month.')
   cmd=[sys.executable,'-B',str(R/'run_prepared_fixed.py'),'--import-checkpoint',str(cp),'--risk',flag,'--out',str(out)]
   if flag=='on':
    off=R/'runs'/(a.mode+'-'+day+'-off')/'ACTUAL_OPEN_COMPARISON.json';proof=read(off);assert proof['off_complete_original_state_identity']
    g['own_OFF_proof']=dict(path=str(off),sha256=sha(off));cmd+=['--off-result',str(off)]
   grant=R/'grants'/(name+'.json');grant.write_text(json.dumps(g,ensure_ascii=False,indent=2)+'\n');cmd+=['--authorization',str(grant)]
   with (R/(name+'.out')).open('w') as stdout,(R/(name+'.err')).open('w') as stderr:subprocess.run(cmd,stdout=stdout,stderr=stderr,check=True)
   c=read(out/'COMPLETED.json');assert c['no_CLOSE_no_later_day']
   progress.append(dict(case=case,risk=flag,cursor=c['cursor'],seconds=c['seconds']));(R/('PAIR_PROGRESS_'+a.mode+'.json')).write_text(json.dumps(dict(completed=progress,seconds=time.monotonic()-t),ensure_ascii=False,indent=2)+'\n')
   print('PAIR_EVENT_COMPLETED',case,flag,'seconds',round(c['seconds'],3),flush=True)
if __name__=='__main__':main()
