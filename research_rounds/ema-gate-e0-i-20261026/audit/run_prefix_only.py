from pathlib import Path
import sys,json,hashlib
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'code'))
from run_gate import run
if __name__=='__main__':
 run(HERE/'technical/prefix',end='2023-12-29',cutoff='2023-12-29',technical=True,prefix=True)
 with (HERE/'technical/prefix-prepared.json').open('x') as f:json.dump(dict(passed=True,technical_paths=16,economic_paths=0,cutoff='2023-12-29',full_comparison_pending=True,wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),f,indent=2)
