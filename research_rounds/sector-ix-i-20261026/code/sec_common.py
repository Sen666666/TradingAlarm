from pathlib import Path
from datetime import datetime,timezone
from decimal import Decimal
import sys,json,hashlib,math
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1];OLD=ROOT/'research_rounds/rs-h1-execution-20261025';IX=ROOT/'research_rounds/ix-a-share-entry-20261025';G1=ROOT/'research_rounds/b5-g1-20261025';PREV=ROOT/'research_rounds/universe-expansion-diagnosis-20261025';ABCD=ROOT/'research_rounds/selection-rotation-abcd-20261025';BUDGET=ROOT/'research_rounds/budget-ownership-isolation-20261025'
START='2021-01-04';END='2026-10-16';GROUPS={'SEMI':('半导体','URFI881121'),'COMM':('通信设备','URFI881129'),'DRUG':('创新药','THEME931152'),'BANK':('银行','URFI881155')}
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(np.bool_,bool)):return bool(x)
 if isinstance(x,(np.integer,int)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if math.isfinite(x) else None
 if isinstance(x,(Path,Decimal,datetime)):return str(x)
 return x
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def now():return datetime.now(timezone.utc).isoformat()
