from pathlib import Path
from datetime import datetime, timezone
import json,hashlib,math
import numpy as np

HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
SRC=ROOT/'research_rounds/ix-a-share-entry-20261025'
GAP=ROOT/'research_rounds/winner-gap-attribution-20261025'
OLD=ROOT/'research_rounds/rs-h1-execution-20261025'
NAMES={'AU0':'沪金主连','518880':'黄金ETF','512480':'半导体ETF','001309.SZ':'德明利','688981.SH':'中芯国际','600036.SH':'招商银行','600519.SH':'贵州茅台','688256.SH':'寒武纪','300308.SZ':'中际旭创','300502.SZ':'新易盛'}
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(Path(p).read_text())
def now():return datetime.now(timezone.utc).isoformat()
def clean(x):
 if isinstance(x,dict):return {str(k):clean(v) for k,v in x.items()}
 if isinstance(x,(tuple,list)):return [clean(v) for v in x]
 if isinstance(x,(bool,np.bool_)):return bool(x)
 if isinstance(x,(int,np.integer)):return int(x)
 if isinstance(x,(float,np.floating)):return float(x) if math.isfinite(x) else None
 if isinstance(x,Path):return str(x)
 return x
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(clean(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def verify():
 f=read(HERE/'freeze-v2.json');bad=[p for p,h in f['sha256'].items() if sha(ROOT/p)!=h];assert not bad,bad
 return len(f['sha256'])
