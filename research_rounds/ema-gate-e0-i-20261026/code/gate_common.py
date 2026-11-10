from pathlib import Path
from datetime import datetime,timezone
import sys,json,hashlib,math
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
SEC=ROOT/'research_rounds/sector-ix-i-20261026';OLD=ROOT/'research_rounds/rs-h1-execution-20261025';IX=ROOT/'research_rounds/ix-a-share-entry-20261025';LER=ROOT/'research_rounds/a-share-local-entry-reentry-20261026';VIDEO=ROOT/'research_rounds/video-ema-a-share-20261026'
START='2021-01-04';END='2026-10-16';GROUPS={'SEMI':('半导体','URFI881121'),'COMM':('通信','URFI881129'),'DRUG':('创新药','THEME931152'),'BANK':('银行','URFI881155')}
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(np.bool_,bool)):return bool(x)
 if isinstance(x,(np.integer,int)):return int(x)
 if isinstance(x,(np.floating,float)):return float(x) if math.isfinite(x) else None
 if isinstance(x,(Path,datetime)):return str(x)
 return x
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def gate(f):
 q=pd.DataFrame(index=f.index)
 for n in [9,21,50]:q['ema'+str(n)]=f.groupby('segment_id',sort=False).close.transform(lambda x:x.ewm(span=n,adjust=False,min_periods=n).mean())
 same=f.segment_id.eq(f.segment_id.shift());q['ordering']=(q.ema9>q.ema21)&(q.ema21>q.ema50)
 q['rising']=(q.ema9.diff()>0)&(q.ema21.diff()>0)&(q.ema50.diff()>0)&same
 q['gate']=q.ordering&q.rising
 return q
