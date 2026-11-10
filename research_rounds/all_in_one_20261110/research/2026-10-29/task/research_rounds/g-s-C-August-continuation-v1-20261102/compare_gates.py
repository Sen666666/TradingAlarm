"""Guarded complete Aug1 full/physical prefix and true restart equivalence."""
from pathlib import Path
import argparse,json,subprocess,sys
import august_runtime as A
E=A.E
def load(p):
 s=A.read(p.with_suffix('.provenance.json'));cls=A.R0Runner if s['binding']['cell'].endswith('_R0') else A.BaselineRunner;return cls.restore(p)
def normalize(r):
 x=A.economic(r)
 # Only actual input storage identity is branch-specific. Policy source,
 # every receipt/certificate/projection hash and risk state must match raw.
 return json.loads(json.dumps(x,default=E.encode))
def main():
 p=argparse.ArgumentParser();p.add_argument('--cell',required=True);a=p.parse_args();root=A.HERE/'gates'/a.cell;root.mkdir(parents=True,exist_ok=True);records=[]
 for phase in ['OPEN','CLOSE']:
  full=A.HERE/'runs'/a.cell/('2025-08-01-'+phase+'.pkl');physical=A.HERE/'physical-runs'/a.cell/full.name
  f,g=load(full),load(physical);x,y=normalize(f),normalize(g)
  if x!=y:A.save(root/('DIFF-'+phase+'.json'),dict(full=x,physical=y));raise AssertionError('Aug1 complete physical prefix differs '+phase)
  records.append(dict(phase=phase,complete_economic_state_equal=True,raw_certificates_and_risk_ids_equal=True,hash=E.digest(x)))
 cp=A.HERE/'runs'/a.cell/'2025-08-01-CLOSE.pkl'
 subprocess.run([sys.executable,'-B',str(A.HERE/'run_august.py'),'--cell',a.cell,'--restore-only',str(cp)],check=True)
 E.require(A.read(cp.parent/'RESTORE_GATE.json')['passed'],'cross-process gate')
 for branch in ['runs','physical-runs']:E.require(A.read(A.HERE/branch/a.cell/'import/IMPORT.json')['passed'],'source import gate')
 A.save(root/'GATE.json',dict(passed=True,cell=a.cell,source_restore_no_finance_exact=True,physical_all_channels=True,records=records,restore_checkpoint_sha256=A.sha(cp),formal_full_prefix_reused=True,authorization_sha256=A.sha(A.AUTH)))
 print('AUG1_GATES_PASS',a.cell,flush=True)
if __name__=='__main__':main()
