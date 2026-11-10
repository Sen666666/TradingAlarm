from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,math,sys
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
SEC=ROOT/'research_rounds/sector-ix-i-20261026'
OLD=ROOT/'research_rounds/rs-h1-execution-20261025'
IX=ROOT/'research_rounds/ix-a-share-entry-20261025'
START='2021-01-04';END='2026-10-16'
GROUPS={'SEMI':('半导体','URFI881121'),'COMM':('通信','URFI881129'),'DRUG':('创新药','THEME931152'),'BANK':('银行','URFI881155')}
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list,set)):return [clean(v) for v in x]
 if isinstance(x,(np.bool_,bool)):return bool(x)
 if isinstance(x,(np.integer,int)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if math.isfinite(x) else None
 if isinstance(x,(datetime,Path)):return str(x)
 return x
def write(p,x):
 p=Path(p);p.parent.mkdir(exist_ok=True,parents=True)
 with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def now():return datetime.now(timezone.utc).isoformat()
