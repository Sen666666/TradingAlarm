"""Postprocess the one economic run; no accounts or model search are started."""
from pathlib import Path
import subprocess,sys,time
HERE=Path(__file__).resolve().parents[1]
def main():
 while not (HERE/'accounts/summary.json').exists():time.sleep(3)
 time.sleep(3)  # Atomic completion of the already-finished runner's gzip close.
 for script,name in [(HERE/'code/analyze_ix.py','account-analysis'),(HERE/'code/diagnose_misses.py','miss-analysis')]:
  print('postprocess',name,flush=True)
  with (HERE/'post'/f'{name}.log').open('x') as f:
   r=subprocess.run([sys.executable,str(script)],stdout=f,stderr=subprocess.STDOUT)
  if r.returncode:
   print((HERE/'post'/f'{name}.log').read_text()[-5000:],flush=True);raise SystemExit(r.returncode)
 print('independent audit and diagnostics finished',flush=True)
 while not (HERE/'technical/multi-prefix-2023-12-29/comparison.json').exists():time.sleep(3)
 with (HERE/'post/report-build.log').open('x') as f:
  r=subprocess.run([sys.executable,str(HERE/'post/build_report.py')],stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:
  print((HERE/'post/report-build.log').read_text()[-5000:],flush=True);raise SystemExit(r.returncode)
 print('report build finished',flush=True)
if __name__=='__main__':main()
