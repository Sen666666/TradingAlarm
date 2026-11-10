from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,sys,math
from decimal import Decimal
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1];OLD=ROOT/'research_rounds/rs-h1-execution-20261025';IX=ROOT/'research_rounds/ix-a-share-entry-20261025';ABCD=ROOT/'research_rounds/selection-rotation-abcd-20261025';PREV=ROOT/'research_rounds/universe-expansion-diagnosis-20261025'
START='2021-01-04';END='2026-10-16';SECTORS=['URFI881121','URFI881129','URFI881155']
def read(p):return json.loads(Path(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,(bool,np.bool_)):return bool(x)
 if isinstance(x,(int,np.integer)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,(Path,Decimal,datetime)):return str(x)
 return x
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
