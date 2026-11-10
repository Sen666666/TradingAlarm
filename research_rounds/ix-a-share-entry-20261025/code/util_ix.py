from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,math,sys,importlib.util
import numpy as np

HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
OLD=ROOT/'research_rounds/rs-h1-execution-20261025'
G1=ROOT/'research_rounds/b5-g1-20261025'
B5=ROOT/'research_rounds/pv-strength-b5-20261025'
ENTRY_TYPES=['IX','W23','W2H','C3']

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def now():return datetime.now(timezone.utc).isoformat()
def read(p):return json.loads(Path(p).read_text())
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(list,tuple)):return [clean(v) for v in x]
 if isinstance(x,(bool,np.bool_)):return bool(x)
 if isinstance(x,(int,np.integer)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(float(x)) else None
 if isinstance(x,Path):return str(x)
 return x
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def frozen():
 ids={}
 for directory in [B5,G1]:
  f=read(directory/'freeze.json')
  for p,h in f['sha256'].items():
   if '/code/' in p:ids[p]=h
 for p in sorted((OLD/'code').glob('*.py')):ids[str(p.relative_to(ROOT))]=sha(p)
 for p in [OLD/'inputs-v2/input-manifest.json',OLD/'prepared-v2/manifest.json',OLD/'h1/matrix.npz',OLD/'h1/manifest.json',OLD/'analysis-v2/summary.json',OLD/'accounts-v2/summary.json']:
  ids[str(p.relative_to(ROOT))]=sha(p)
 return ids
def verify(mapping):
 bad=[p for p,h in mapping.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=h]
 assert not bad,bad
 return len(mapping)
