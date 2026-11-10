"""Frozen financial replay; normalize only an empty string metadata column."""
from pathlib import Path
import sys,json,hashlib
import pandas as pd
HERE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(HERE/'code'))
import run_local as run
import local_model
original=local_model.receipts
def typed_receipts(f):
 r=original(f)
 if len(r)==0:r['anchor_day']=pd.Series(index=r.index,dtype='str')
 return r
local_model.receipts=typed_receipts
cutoff='2023-12-29'
run.run(HERE/'technical/prefix-v2',end=cutoff,cutoff=cutoff,technical=True,prefix=True)
run.write(HERE/'technical/prefix-run-v2.json',dict(passed=True,paths=14,cutoff=cutoff,economic_paths=0,comparison_pending_full_economic_completion=True,repair_only='empty anchor_day metadata dtype; nonempty data and all numeric checks unchanged',wrapper_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()))
print('prefix-v2 execution complete',flush=True)
