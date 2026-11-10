"""Fixed engineering revalidation list; no new economic policy variant."""
from pathlib import Path
import subprocess,sys,json,time
O=Path(__file__).resolve().parent
for sector,stage in [('TECH','postgate'),('TECH','repair-prefix'),('DRUG','repair-prefix'),('TECH','repair-full'),('DRUG','repair-full')]:
 print('START',sector,stage,flush=True)
 with (O/f'{sector}-{stage}.log').open('w') as f:
  r=subprocess.run([sys.executable,'-B',str(O/'run_stage.py'),sector,stage],stdout=f,stderr=subprocess.STDOUT)
 if r.returncode:print('FAILED',sector,stage,r.returncode,flush=True);sys.exit(r.returncode)
 print('COMPLETE',sector,stage,json.loads((O/'COMPUTE_TIME.json').read_text())['seconds'],flush=True)
