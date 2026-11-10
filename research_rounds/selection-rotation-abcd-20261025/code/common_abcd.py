from pathlib import Path
from datetime import datetime,timezone
import json,hashlib,math,sys,importlib.util
import numpy as np
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
OLD=ROOT/'research_rounds/rs-h1-execution-20261025';SRC=ROOT/'research_rounds/ix-a-share-entry-20261025'
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def now():return datetime.now(timezone.utc).isoformat()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(np.bool_,bool)):return bool(x)
 if isinstance(x,(np.integer,int)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,Path):return str(x)
 return x
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def verify(mapping):
 bad=[p for p,h in mapping.items() if sha(ROOT/p)!=h];assert not bad,bad
 return len(mapping)
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);sys.modules[name]=m;s.loader.exec_module(m);return m
