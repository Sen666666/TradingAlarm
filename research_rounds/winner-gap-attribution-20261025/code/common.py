from pathlib import Path
import json,hashlib,math
from datetime import datetime,timezone
import numpy as np
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
SRC=ROOT/'research_rounds/ix-a-share-entry-20261025';OLD=ROOT/'research_rounds/rs-h1-execution-20261025'
IDS=['688256.SH','300308.SZ','300502.SZ'];START='2023-01-01';END='2026-10-22';MODES=['IX','W23','W2H','C3'];ALLOCS=['T0','T1','S0','S1']
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(bool,np.bool_)):return bool(x)
 if isinstance(x,(int,np.integer)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,Path):return str(x)
 return x
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def now():return datetime.now(timezone.utc).isoformat()
def verify_source(p):
 p=Path(p);expected=read(SRC/'complete.json')['artifacts'][str(p.relative_to(ROOT))];assert sha(p)==expected,str(p)
