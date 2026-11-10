from pathlib import Path
from datetime import datetime,timezone
import sys,json,gzip,hashlib,importlib.util,math
import numpy as np
import pandas as pd
HERE=Path(__file__).resolve().parents[1];ROOT=HERE.parents[1]
OLD=ROOT/'research_rounds/rs-h1-execution-20261025';IX=ROOT/'research_rounds/ix-a-share-entry-20261025'
G1=ROOT/'research_rounds/b5-g1-20261025';B5=ROOT/'research_rounds/pv-strength-b5-20261025'
TEMP=ROOT/'research_rounds/temperature-sizing-20261026';DESIGN=ROOT/'research_rounds/tech-compound-design-20261026';ROT=ROOT/'research_rounds/tech-amount-rotation-20261026'
CORE=HERE/'data/core-v3';PREP=HERE/'prepared-v2'
for p in [OLD/'code',IX/'code',ROOT/'research_rounds/unlimited-capital-20261026/code']:sys.path.append(str(p))
import multi_runner as native
import sector_account as ledger
import sector_stock_admission as admission
from current_pool_bridge import load_bundle,read_raw as original_read_raw,read_actions,prepare_signal,source_segments
def read_raw(path,record):return original_read_raw(Path(path),record)
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(native.encoded(x),f,ensure_ascii=False,indent=2,allow_nan=False);f.write('\n')
def now():return datetime.now(timezone.utc).isoformat()
def rows(p):
 with gzip.open(p,'rt') as f:
  for line in f:yield json.loads(line)
def import_path(name,path):
 spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec);sys.modules[name]=m;spec.loader.exec_module(m);return m
