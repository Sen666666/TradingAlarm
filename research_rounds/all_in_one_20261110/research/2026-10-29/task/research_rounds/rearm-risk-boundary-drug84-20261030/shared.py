"""Drug input mapping for the verified local v2/Decimal audit. No account runner."""
from pathlib import Path
from datetime import datetime,time as dt,timezone
from decimal import Decimal as D,getcontext
from dataclasses import replace
from collections import Counter
import sys,json,gzip,csv,time,hashlib,importlib.util,bisect,ast,math
import pandas as pd
import numpy as np
O=Path(__file__).resolve().parent;W=O.parent;R=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');DRUG=R/'innovative-drug-local-recovery-20261028';PRE=R/'innovative-drug-sfw3-20261028/prepared';PH=R/'ph1-cross-sector-20261028';V=W/'rearm-risk-boundary-design-20261030';TECH=W/'rearm-risk-boundary-all69-20261030';Z=D(0);ONE=D(1);EPS=64*np.finfo(float).eps
def loadmod(n,p):
 sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sys.modules[n]=m;sp.loader.exec_module(m);return m
H=loadmod('drug84_shared_verified_ledger',R/'s-entry-mechanism-audit-20261029/code/audit.py')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):return json.loads(Path(p).read_text())
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,allow_nan=False))
def export(p,x):pd.DataFrame(H.encoded(x)).to_csv(p,index=False)
def stamp(x):return datetime.fromisoformat(x)
def market(ids):
 # Same load_bundle/FastMarket/ledger/schedules as TECH; only DRUG manifest replaces TECH records.
 b=H.C.load_bundle(H.OLD/'inputs-v2/input-manifest.json');b.lines=tuple(x for x in b.lines if x.security_id in ids);assert {x.security_id for x in b.lines}==set(ids)
 sectors={x.sector_id for x in b.lines};needed=set(ids)|sectors;rec={x['series_id']:x for x in read(PRE/'manifest.json')['series']};b.series={s:x for s,x in b.series.items() if s in needed};b.sector_series={s:x for s,x in b.sector_series.items() if s in sectors}
 for s,x in b.series.items():x.record=rec[s]
 rules=read(H.PRIOR/'execution-rules-v2.json');rules['calendars']['A']=sorted(set(rules['calendars']['A'])|{f'2026-10-{d}T09:30:00+08:00' for d in [27,28,29,30]});rules['decision_cutoffs']=sorted(set(rules['decision_cutoffs'])|{f'{d}T15:10:00+08:00' for d in ['2023-12-29','2026-10-23','2026-10-26','2026-10-27']})
 return H.FM(b,rules,[],read(H.OLD/'inputs-v2/economic-protocol.json'))
def original():
 obj=read(DRUG/'S0/accounts-v2/ACT__S0_base.json');audit=obj['audit_log'];daily={}
 with gzip.open(DRUG/'S0/accounts-v2/daily.jsonl.gz','rt') as f:
  for line in f:
   x=json.loads(line)
   if x['account']=='ACT__S0_base':daily[x['at'][:10]]=x
 assert len(daily)==681
 cycles={f"{x['symbol']}|{x['entry_at'][:10]}":x for x in csv.DictReader((DRUG/'S0/analysis/campaigns.csv').open()) if x['policy']=='ACT' and x['scenario']=='base'};assert len(cycles)==84
 return cycles,audit,daily
