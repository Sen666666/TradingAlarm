"""Sequential cells per worker; two workers maximum, no new financial logic."""
from pathlib import Path
import argparse,json,subprocess,sys,shutil
P=Path(__file__).resolve().parent
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--cells',nargs='+',required=True);a=ap.parse_args()
 for c in a.cells:
  assert c in ['C10','C20','C10_R0','C20_R0']
  gate=P/'gates'/c/'GATE.json';assert json.loads(gate.read_text())['passed']
  root=P/'runs'/c;assert not (root/'COMPLETED.json').exists(),'completed month must not rerun'
  if not (root/'AUG1_STARTED.json').exists():shutil.copy2(root/'STARTED.json',root/'AUG1_STARTED.json')
  with (P/(c+'-August.out')).open('x') as so,(P/(c+'-August.err')).open('x') as se:
   subprocess.run([sys.executable,'-B',str(P/'run_august.py'),'--cell',c,'--until','2025-08-29'],stdout=so,stderr=se,check=True)
  print('AUGUST_CELL_COMPLETED',c,flush=True)
if __name__=='__main__':main()
