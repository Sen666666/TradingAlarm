from pathlib import Path
import json,hashlib,gzip
import pandas as pd
import numpy as np
ROOT=Path(__file__).resolve().parents[3]
O=Path(__file__).resolve().parents[1]
PRIOR=ROOT/'research_rounds/pvr-act-comparison-20261027'
FORM=ROOT/'research_rounds/s-amount-confirmation-20261028'
TECH=Path(json.loads((PRIOR/'input.json').read_text())['snapshot']['path'])
DRUG=ROOT/'research_rounds/innovative-drug-sfw3-20261028/prepared'
LOCAL=ROOT/'research_rounds/innovative-drug-local-recovery-20261028'
SOLD=ROOT/'research_rounds/strict-entry-capacity-20261027/signals'
SFOLD=ROOT/'research_rounds/strict-entry-fast-support-20261027'
PREPS={'TECH':TECH,'DRUG':DRUG}
POOLS={'TECH':ROOT/'research_rounds/tech-compound-design-20261026/proposed-pool.csv','DRUG':LOCAL/'pool.csv'}
OLD_TABLES={'TECH':SOLD,'DRUG':DRUG/'strict'}
OLD_ACCOUNTS={'TECH':SFOLD/'S0/accounts-v2','DRUG':LOCAL/'S0/accounts-v2'}
END='2026-10-27'
def read(p):return json.loads(Path(p).read_text())
def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(2**20),b''):h.update(b)
 return h.hexdigest()
def save(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
 with p.open('x') as f:json.dump(obj,f,ensure_ascii=False,indent=2,allow_nan=False)
def rows(p):
 with gzip.open(p,'rt') as f:return [json.loads(s) for s in f]
def pool(sector):return pd.read_csv(POOLS[sector])
