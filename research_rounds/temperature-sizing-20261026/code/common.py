from pathlib import Path
from datetime import datetime,timezone
import sys,json,gzip,hashlib,importlib.util
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
OLD=ROOT/'research_rounds/rs-h1-execution-20261025';IX=ROOT/'research_rounds/ix-a-share-entry-20261025';PREV=ROOT/'research_rounds/unlimited-capital-20261026'
for p in [OLD/'code',IX/'code',PREV/'code']:sys.path.append(str(p))
import multi_runner as native
import sector_account as ledger
import sector_stock_admission as admission
from current_pool_bridge import load_bundle,load_prepared_states
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(native.encoded(x),f,ensure_ascii=False,indent=2,allow_nan=False)
def now():return datetime.now(timezone.utc).isoformat()
def rows(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
