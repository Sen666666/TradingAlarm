from pathlib import Path
import sys,json,gzip,hashlib,math
import pandas as pd
import numpy as np
from datetime import datetime,date
from decimal import Decimal
ROOT=Path(__file__).resolve().parents[3];O=Path(__file__).resolve().parents[1]
ROUND=ROOT/'research_rounds/cp1-waiting-factorial-20261028'
sys.path.insert(0,str(ROUND/'code'))
from fw_common import PREPS,OLD_TABLES,COMBO,PREV,LABELS,MODES,SCENARIOS,pool,load,read,sha
END='2026-10-27'
STRICT={'SF','SW3F','SW10F','SCP','WCP','W10CP'}
WAIT={'SW3F':3,'SW10F':10,'A3CP':3,'A10CP':10,'WCP':3,'W10CP':10}
def native(x):
 if isinstance(x,dict):return {str(k):native(v) for k,v in x.items()}
 if isinstance(x,(list,tuple,set)):return [native(v) for v in x]
 if isinstance(x,(np.integer,np.bool_)):return x.item()
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,(pd.Timestamp,datetime,date)):return x.isoformat()
 if isinstance(x,Decimal):return str(x)
 return x
def save(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 data=json.dumps(native(x),ensure_ascii=False,separators=(',',':'),allow_nan=False).encode()
 if p.suffix=='.gz':
  with p.open('xb') as f:
   with gzip.GzipFile(fileobj=f,mode='wb',mtime=0) as z:z.write(data)
 else:
  with p.open('xb') as f:f.write(data)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
