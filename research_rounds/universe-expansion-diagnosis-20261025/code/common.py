from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys,math
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1];G1=ROOT/'research_rounds/b5-g1-20261025';IX=ROOT/'research_rounds/ix-a-share-entry-20261025';OLD=ROOT/'research_rounds/rs-h1-execution-20261025';ABCD=ROOT/'research_rounds/selection-rotation-abcd-20261025'
START='2021-01-01';END='2026-10-16'
def read(p):return json.loads(Path(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,(bool,np.bool_)):return bool(x)
 if isinstance(x,(np.integer,int)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if math.isfinite(x) else None
 if isinstance(x,np.bool_):return bool(x)
 if isinstance(x,Path):return str(x)
 return x
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
