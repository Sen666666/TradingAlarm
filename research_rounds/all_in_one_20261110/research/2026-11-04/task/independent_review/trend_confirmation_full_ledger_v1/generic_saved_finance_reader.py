"""Independent saved-native audit. No strategy/account/guard import or replay.

Reads original actual fill/parts and native split/AR records; no account is run.
Split basis follows the separately reviewed conservative admission convention.
"""
from pathlib import Path
from decimal import Decimal as D
from collections import defaultdict,Counter
import argparse,gzip,json,hashlib,bisect
import pandas as pd

O=Path(__file__).resolve().parent
BASE=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/prepared-v2')
W=Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
Z=D(0);EPS=D('.000001');S=D('.0005');SRC={}
def n(v):return D(str(v))
def ts(v):return pd.Timestamp(str(v))
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p):SRC[str(Path(p).resolve())]=sha(p);return json.loads(Path(p).read_text())
def book(p):
 SRC[str(Path(p).resolve())]=sha(p)
 with gzip.open(p,'rt')as f:return json.load(f)
def rows(p):
 SRC[str(Path(p).resolve())]=sha(p)
 with gzip.open(p,'rt')as f:return[json.loads(x)for x in f]
def near(a,b,tag):assert abs(n(a)-n(b))<EPS,(tag,a,b,n(a)-n(b))

manifest={r['series_id']:r for r in read(BASE/'manifest.json')['series']}
facts={r['symbol']:r for r in read(W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')}
rawcache={};factcache={}
def raw(sid):
 if sid not in rawcache:
  r=manifest[sid]['files']['signal'];p=BASE/r['path'];assert sha(p)==r['sha256']
  SRC[str(p)]=sha(p);f=pd.read_parquet(p,columns=['raw_open','raw_close','observed_bar','synthetic_event_bar'])
  rawcache[sid]=f
 return rawcache[sid]
def mark(sid,at):
 f=raw(sid);ts=pd.Timestamp(str(at).replace('T',' '));d=pd.Timestamp(str(at)[:10]);i=f.index.searchsorted(d,side='right')-1
 while i>=0:
  r=f.iloc[i];rd=f.index[i]
  if bool(r.observed_bar)and not bool(r.synthetic_event_bar):
   col='raw_open'if rd==d and ts.hour<15 else'raw_close';v=n(r[col])
   if v.is_finite()and v>0:return v
  i-=1
 raise ValueError((sid,at,'unknown original raw mark'))
def factor(sid,at):
 if sid not in factcache:
  r=facts[sid];p=Path(r['refs']['facts']);assert sha(p)==r['output_sha256'][str(p)]
  SRC[str(p)]=sha(p);factcache[sid]=pd.read_parquet(p,columns=['factor'])
 f=factcache[sid];i=f.index.searchsorted(pd.Timestamp(str(at)[:10]),side='right')-1
 assert i>=0, (sid,at,'no causal factor row')
 return n(f.iloc[i]['factor'])

_prefix_cache_book=None
_prefix_cache_cut=0
_prefix_cache_value=None
def prefix(b,cut):
 global _prefix_cache_book,_prefix_cache_cut,_prefix_cache_value
 if _prefix_cache_book is b and cut>=_prefix_cache_cut:
  v=_prefix_cache_value;q=v['q'];basis=v['basis'];pending=v['pending'];cash=v['cash'];fees=v['fees'];entry=v['entry'];buyline=v['buyline'];divincome=v['divincome'];split_events=v['split_events'];begin=_prefix_cache_cut
 else:
  q={};basis={};pending={};cash=D('1000000');fees=Z;entry={};buyline={};divincome=Z;split_events=0;begin=0
 tx={t['receipt_id']:t for t in b['trades']};txlayer={t['layer']:t['security_id']for t in b['trades']if t['side']=='buy'}
 for r in b['audit'][begin:cut]:
  k=r['kind']
  if k in ('split','split_fraction_floor_proxy'):
   sid=r['sid'];ratio=n(r['ratio']);ids=[i for i,v in q.items()if v and txlayer[i]==sid]
   target=int(sum(q[i]for i in ids)*ratio);parts=[int(D(q[i])*ratio)for i in ids];rem=target-sum(parts)
   for j in range(rem):parts[j%len(parts)]+=1
   for i,qty in zip(ids,parts):
    q[i]=qty;entry[i]/=ratio
    if not qty:basis[i]=Z
   split_events+=1
  elif k=='dividend_accrual':divincome+=n(r['receivable']['net_local'])
  if k=='reserve':
   assert r['order_id']not in pending
   pending[r['order_id']]=dict(sid=r['sid'],gross=n(r['gross_budget_cny']),fee=n(r['fee_reserved_cny']))
  elif k=='release_buy':
   o=pending.pop(r['order_id']);near(o['gross'],r['gross_released'],'release gross');near(o['fee'],r['fee_released'],'release fee')
  elif k=='fill':
   t=tx[r['receipt']['receipt_id']];gross=n(t['gross_cny']);fee=n(t['fees_cny']);fees+=fee
   near(sum(map(n,r['fee_components'].values()),Z),fee,'native fee component total')
   if t['side']=='buy':
    i=t['layer'];assert i not in q
    q[i]=int(t['shares']);basis[i]=gross+fee;entry[i]=gross/D(q[i]);buyline[i]=n(t['floor']);cash-=gross+fee
    o=pending[r['order_id']];o['gross']=n(r['gross_budget_remaining']);o['fee']=max(Z,o['fee']-fee)
   else:
    cash+=gross-fee;got=Z
    for part in t['parts']:
     i=part['layer'];count=int(part['shares']);assert 0<count<=q[i]
     basis[i]-=basis[i]*D(count)/D(q[i]);q[i]-=count;got+=n(part['net_cash'])
    near(got,gross-fee,'sale part cash')
 _prefix_cache_book=b;_prefix_cache_cut=cut;_prefix_cache_value=dict(q=q,basis=basis,pending=pending,cash=cash,fees=fees,entry=entry,buyline=buyline,divincome=divincome,split_events=split_events)
 return _prefix_cache_value

