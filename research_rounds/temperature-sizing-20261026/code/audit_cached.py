"""Lossless account sharding and memoized independent marks; no trading code."""
from common import *
import collections
import audit as a
import hashlib
INSTANCES=[]
class MemoPrices(a.IndependentPrices):
 def __init__(self):
  super().__init__();z=np.load(HERE/'prepared/facts.npz');self.date_index={str(d):i for i,d in enumerate(z['dates'])};self.memo={};self.hits=0;self.misses=0;INSTANCES.append(self)
 def mark(self,sid,day):
  if day not in self.date_index:return super().mark(sid,day)
  if sid not in self.memo:self.memo[sid]=[None]*len(self.date_index)
  i=self.date_index[day];value=self.memo[sid][i]
  if value is None:value=super().mark(sid,day);self.memo[sid][i]=value;self.misses+=1
  else:self.hits+=1
  return value

def shard(short=False):
 source=HERE/('technical/short' if short else 'accounts-v1');sources={aid:source for aid in read(source/'summary.json')['accounts']}
 if not short:
  ctrl=HERE/'technical/controls-v2';sources={**{aid:ctrl for aid in read(ctrl/'summary.json')['accounts']},**sources}
 out=HERE/('technical/short-shards' if short else 'shards-v1');out.mkdir(exist_ok=False);handles={};digests={};counts={}
 try:
  for aid in sources:
   (out/aid).mkdir()
   for name in ['daily','audit','fills']:
    key=(aid,name);handles[key]=gzip.open(out/aid/f'{name}.jsonl.gz','wb',compresslevel=1);digests[key]=hashlib.sha256();counts[key]=0
  for src in dict.fromkeys(sources.values()):
   for name in ['daily','audit','fills']:
    with gzip.open(src/f'{name}.jsonl.gz','rb') as f:
     for line in f:
      assert line.startswith(b'{"account": "');aid=line.split(b'"',4)[3].decode();key=(aid,name);assert sources[aid]==src
      handles[key].write(line);digests[key].update(line);counts[key]+=1
 finally:
  for f in handles.values():f.close()
 receipts=[]
 for key,h in digests.items():
  aid,name=key
  with gzip.open(out/aid/f'{name}.jsonl.gz','rb') as f:actual=hashlib.sha256(f.read()).hexdigest()
  assert actual==h.hexdigest(),key
  receipts.append(dict(account=aid,stream=name,rows=counts[key],plaintext_sha256=actual))
 write(out/'manifest.json',dict(passed=True,lossless_partition=True,sources={aid:str(src.relative_to(ROOT)) for aid,src in sources.items()},receipts=receipts));return out

def main(mode):
 if mode=='validate':
  p=shard(True);old=a.IndependentPrices();memo=MemoPrices();checks=0
  for sid in ['300502.SZ','688498.SH','000063.SZ','920185.BJ']:
   record=old.records[sid];first=record['source_start']
   for day in ['2015-01-30','2018-12-28','2022-03-01','2022-03-02','2025-08-26','2026-10-22']:
    if day<first:continue
    assert old.mark(sid,day)==memo.mark(sid,day)==memo.mark(sid,day);checks+=1
  write(HERE/'technical/audit-cache-validation.json',dict(passed=True,original_mark_identity_checks=checks,lossless_short_partition=True,financial_auditor_source_unchanged=True));print('Audit cache and lossless partition validated',flush=True)
 else:
  assert read(HERE/'technical/audit-cache-validation.json')['passed'];out=shard(False);rejects=collections.defaultdict(collections.Counter);rejected_stocks=collections.defaultdict(set)
  def selected(path,aid):
   for r in rows(out/aid/path.name):
    assert r['account']==aid
    if path.name=='audit.jsonl.gz' and r['kind']=='sizing_rejection' and r['reason']=='insufficient_budget_or_quantity':
     rejects[aid][r['sizing_kind']]+=1;rejected_stocks[aid,r['sizing_kind']].add(r['sid'])
    yield r
  a.selected=selected;a.IndependentPrices=MemoPrices;a.main('economic')
  write(HERE/'analysis-v1/audit-performance.json',dict(no_arithmetic_change=True,lossless_shards=True,mark_cache=[dict(hits=p.hits,misses=p.misses) for p in INSTANCES]));print('Full independent audit complete',flush=True)
  write(HERE/'analysis-v1/rejections-by-kind.json',[dict(account=aid,initial_attempts=c.get('initial',0),add_attempts=c.get('add',0),ever_rejected_initial_stocks=len(rejected_stocks[aid,'initial']),ever_rejected_add_stocks=len(rejected_stocks[aid,'add'])) for aid,c in rejects.items()])
if __name__=='__main__':main(sys.argv[1])
