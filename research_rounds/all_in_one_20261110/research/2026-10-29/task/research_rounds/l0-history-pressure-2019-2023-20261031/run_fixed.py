"""Frozen six-cell validation, no parameter/date selection."""
from pathlib import Path
import subprocess,sys,json
O=Path(__file__).resolve().parent
for sec,stage in [('TECH','gate'),('DRUG','gate'),('TECH','prefix'),('DRUG','prefix'),('TECH','full'),('DRUG','full')]:
 print('START',sec,stage,flush=True)
 with (O/f'{sec}-{stage}.log').open('w') as f:r=subprocess.run([sys.executable,'-B',str(O/'run_stage.py'),sec,stage],stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:print('FAILED',sec,stage,r.returncode,flush=True);sys.exit(r.returncode)
 print('COMPLETE',sec,stage,json.loads((O/'COMPUTE_TIME.json').read_text())['seconds'],flush=True)
