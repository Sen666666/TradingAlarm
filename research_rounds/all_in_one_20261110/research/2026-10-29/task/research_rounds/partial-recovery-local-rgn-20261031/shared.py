from pathlib import Path
from datetime import datetime,time as tm
from decimal import Decimal as D
from collections import defaultdict
import sys,importlib.util,json,gzip,csv,hashlib,math,bisect,time
import numpy as np,pandas as pd
O=Path(__file__).resolve().parent;W=O.parent;RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds');Z=D(0)
def load(n,p):
 sp=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(sp);sys.modules[n]=m;sp.loader.exec_module(m);return m
H=load('rgn_original_market_helpers',RR/'s-entry-mechanism-audit-20261029/code/audit.py');L=H.L;A=H.A;RB=load('rgn_frozen_RB2',W/'rearm-risk-boundary-design-20261030/risk_boundary_v2.py');AR=load('rgn_frozen_arithmetic',RR/'pv-strength-b5-20261025/code/arithmetic.py')
ns=dict(vars(L));exec(compile((W/'partial-action-full-account-20261030/restore_reservation_kernel.py').read_text(),'frozen_restore_reservation_kernel','exec'),ns);reserve=ns['reserve_budget']
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def csvrows(p):
 with Path(p).open() as f:return list(csv.DictReader(f))
def gz(p):
 with gzip.open(p,'rt') as f:return [json.loads(x) for x in f]
def save(p,x):Path(p).write_text(json.dumps(H.encoded(x),ensure_ascii=False,indent=2,default=str,allow_nan=False))
def export(p,rs):pd.DataFrame(H.encoded(rs)).to_csv(p,index=False)
def stamp(s):return datetime.fromisoformat(s)
def at(day,h=15,m=10):return H.at(day,tm(h,m))
def root(sec,stress):return W/'partial-action-full-account-20261030'/sec/'on' if stress=='base' else W/'partial-action-delay-repair-20261030'/sec/'full'
def aid(sec,stress):return ('I' if sec=='TECH' else 'ACT')+'__B_S0_'+stress
class Feed:
 def __init__(self,sec,ids):
  self.f={};self.e={};self.valid={};self.sg={};self.cache={};self.sec=sec
  prep=Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261027-153013-2ffe04/prepared') if sec=='TECH' else RR/'innovative-drug-sfw3-20261028/prepared'
  for sid in ids:
   f=pd.read_parquet(prep/'facts'/f'{sid}.parquet');e=pd.read_parquet(RR/'ph1-cross-sector-20261028/events'/sec/f'{sid}.parquet');sg=pd.read_parquet(prep/'signals'/f'{sid}.parquet',columns=['volume','observed_bar','source_invalid','synthetic_event_bar']);self.f[sid]=f;self.e[sid]=e;self.sg[sid]=sg;v=f[['close','segment_id']].join(sg[['volume']]);v=v[v[['close','volume']].gt(0).all(axis=1)&np.isfinite(v[['close','volume']]).all(axis=1)];self.valid[sid]={int(seg):g for seg,g in v.groupby('segment_id',sort=False)}
 def row(self,s,day):
  f=self.f[s];j=f.index.searchsorted(pd.Timestamp(day),side='right')-1;return f.iloc[j] if j>=0 else None
 def sigma(self,s,day,seg):
  key=s,str(day),int(seg)
  if key not in self.cache:
   g=self.valid[s][int(seg)];p=g.loc[g.index<pd.Timestamp(day),'close'].tail(64).to_numpy(float)
   self.cache[key]=None if len(p)<64 else max(math.sqrt(math.fsum(x*x for x in [AR.log_ratio(p[i],p[i-1]) for i in range(1,64)])/63),1e-8)
  return self.cache[key]
 def obs(self,s,day,group):
  t=pd.Timestamp(day);f=self.f[s];e=self.e[s];sg=self.sg[s];native=t in f.index;row=f.loc[t] if native else self.row(s,day);known=t in e.index;unit=bool(row is not None and f'|source={int(row.segment_id)}|' in group);good=bool(native and t in sg.index and sg.loc[t,'observed_bar'] and not sg.loc[t,'source_invalid'] and not sg.loc[t,'synthetic_event_bar']);event=int(e.loc[t,'event']) if known else None;price=float(row.raw_close) if good and unit else None;factor=float(row.factor) if price is not None else None;floor=float(row.i_floor) if native and unit and np.isfinite(row.i_floor) else None
  return dict(raw_close=price,factor=factor,event=event,event_known=known and unit,floor=floor,floor_known=floor is not None,source_known=unit,segment=int(row.segment_id) if row is not None else None,native=native)

def market(sec,ids):
 C=H.C;old=RR/'rs-h1-execution-20261025';b=C.load_bundle(old/'inputs-v2/input-manifest.json');b.lines=tuple(x for x in b.lines if x.security_id in ids);assert {x.security_id for x in b.lines}==set(ids);sectors={x.sector_id for x in b.lines};need=set(ids)|sectors
 manifest=RR/('pvr-act-comparison-20261027/input/manifest.json' if sec=='TECH' else 'innovative-drug-sfw3-20261028/prepared/manifest.json');records={r['series_id']:r for r in read(manifest)['series']};b.series={s:x for s,x in b.series.items() if s in need};b.sector_series={s:x for s,x in b.sector_series.items() if s in sectors}
 for s,item in b.series.items():item.record=records[s]
 rules=read(RR/'pvr-act-comparison-20261027/execution-rules-v2.json');rules['calendars']['A']=sorted(set(rules['calendars']['A'])|{f'2026-10-{d}T09:30:00+08:00' for d in [27,28,29,30]});rules['decision_cutoffs']=sorted(set(rules['decision_cutoffs'])|{f'{d}T15:10:00+08:00' for d in ['2023-12-29','2026-10-23','2026-10-26','2026-10-27']});return H.FM(b,rules,[],read(old/'inputs-v2/economic-protocol.json'))

def loadcase(sec,stress):
 r=root(sec,stress);obj=read(r/'accounts-v2'/f'{aid(sec,stress)}.json');ds=[x for x in gz(r/'accounts-v2/daily.jsonl.gz') if x['account']==aid(sec,stress)];logs=obj['audit_log'];pa={x['at']:x for x in logs if x['kind']=='partial_admission'};act={x['at']:x for x in logs if x['kind']=='risk_checkpoint'};d={x['at']:x for x in ds};return dict(sec=sec,stress=stress,logs=logs,ds=ds,pa=pa,act=act,d=d,root=r)
