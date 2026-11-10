"""I/O-only recovery supervisor; exact frozen August financial entry reused."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,subprocess,sys,fcntl,os,json
P=Path(__file__).resolve().parent
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cells',nargs='+',required=True);ap.add_argument('--attempt',required=True);a=ap.parse_args()
 for c in a.cells:
  assert c in ['C10','C20','C10_R0','C20_R0'];root=P/'runs'/c
  with (root/'OWN_SUPERVISOR.lock').open('a+') as lease:
   fcntl.flock(lease,fcntl.LOCK_EX|fcntl.LOCK_NB)
   if (root/'COMPLETED.json').exists():print('ALREADY_COMPLETE_NO_REPLAY',c,flush=True);continue
   assert json.loads((P/'gates'/c/'GATE.json').read_text())['passed']
   with (P/(c+'-August-'+a.attempt+'.out')).open('x') as so,(P/(c+'-August-'+a.attempt+'.err')).open('x') as se:
    cmd=[sys.executable,'-B',str(P/'run_august.py'),'--cell',c,'--until','2025-08-29'];child=subprocess.Popen(cmd,stdout=so,stderr=se)
    marker=root/('OWN_JOB-'+a.attempt+'.json');record=dict(at=datetime.now(timezone.utc).isoformat(),supervisor_pid=os.getpid(),child_pid=child.pid,command=cmd,start_progress=json.loads((root/'PROGRESS.json').read_text()),scope='owned task supervisor only, no process inventory',status='running');marker.write_text(json.dumps(record,indent=2)+'\n')
    rc=child.wait();record.update(status='completed' if rc==0 else 'failed',returncode=rc,ended=datetime.now(timezone.utc).isoformat());marker.write_text(json.dumps(record,indent=2)+'\n');assert rc==0,(c,rc)
   print('AUGUST_CELL_COMPLETED',c,flush=True)
if __name__=='__main__':main()
