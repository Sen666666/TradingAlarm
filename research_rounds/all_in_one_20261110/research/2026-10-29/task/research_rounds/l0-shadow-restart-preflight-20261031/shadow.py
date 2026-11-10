"""Bounded same-snapshot research daily replay; frozen controller unchanged."""
from pathlib import Path
import importlib.util,sys,json,hashlib,pickle,io,dataclasses,collections,datetime,decimal,os,zoneinfo
O=Path(__file__).resolve().parent
p=O.parent/'lr1-cp1-add-preflight-20261031/adapter.py'
s=importlib.util.spec_from_file_location('frozen_shadow_l0',p);M=importlib.util.module_from_spec(s);sys.modules[s.name]=M;s.loader.exec_module(M)
SAVE_KEYS=('last_epoch','epoch','global_watch','daily','risk','applied_actions','record_risk')
IMMUTABLE={'bundle','market','facts','accounts','b0','actions_by_date','sector','prep','core','cp','pv','row_cache_checks'}
EXCLUDE_ACCOUNT={'market','facts','_ix','_ixn'}
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,x):M.save(p,x)
def canonical(x):
 if dataclasses.is_dataclass(x):return ['class',type(x).__module__,type(x).__name__,[[f.name,canonical(getattr(x,f.name))] for f in dataclasses.fields(x)]]
 if isinstance(x,dict):return ['dict',[[canonical(k),canonical(v)] for k,v in x.items()]]
 if isinstance(x,(set,frozenset)):return ['set',sorted([canonical(v) for v in x],key=repr)]
 if isinstance(x,(list,tuple)):return [type(x).__name__,[canonical(v) for v in x]]
 if isinstance(x,decimal.Decimal):return ['Decimal',str(x)]
 if isinstance(x,(datetime.datetime,datetime.date,datetime.time)):return [type(x).__name__,x.isoformat()]
 if hasattr(x,'item'):return canonical(x.item())
 return x
def state(r):
 unknown=set(r.__dict__)-IMMUTABLE-set(SAVE_KEYS)
 if unknown:raise ValueError(('Unclassified runner state',unknown))
 return dict(runner={k:r.__dict__[k] for k in SAVE_KEYS if k in r.__dict__},b0=r.b0.__dict__,accounts={k:{f:v for f,v in a.__dict__.items() if f not in EXCLUDE_ACCOUNT} for k,a in r.accounts.items()})
def fingerprint(r):
 v=state(r)
 # These two saved, output-only monitors sum sets in hash-dependent order.
 # Decimal last-place differences are not controller state or ledger changes.
 v['accounts']={key:{k:x for k,x in a.items() if k not in {'risk_rows','structure_risk'}} for key,a in v['accounts'].items()}
 return hashlib.sha256(json.dumps(canonical(v),ensure_ascii=False,allow_nan=False,separators=(',',':')).encode()).hexdigest()
def allowed():
 result={(x.__module__,x.__name__):x for x in [decimal.Decimal,datetime.datetime,datetime.date,datetime.time,datetime.timedelta,datetime.timezone,collections.Counter,collections.defaultdict,set,frozenset,list,dict,tuple]}
 for module in (M.L,M.A,M.N,sys.modules[M.N.B0Controller.__module__]):
  for v in vars(module).values():
   if isinstance(v,type) and dataclasses.is_dataclass(v):result[(v.__module__,v.__name__)]=v
 # Original frames put pandas timestamps/numpy scalar values into immutable receipts.
 import pandas._libs.tslibs.timestamps as pts,numpy as np
 result[('pandas._libs.tslibs.timestamps','_unpickle_timestamp')]=pts._unpickle_timestamp
 result[('numpy','dtype')]=np.dtype
 result[('zoneinfo','ZoneInfo')]=zoneinfo.ZoneInfo
 def zone_attr(cls,name):
  if cls is not zoneinfo.ZoneInfo or name!='_unpickle':raise pickle.UnpicklingError('Only ZoneInfo._unpickle may be resolved')
  return zoneinfo.ZoneInfo._unpickle
 result[('builtins','getattr')]=zone_attr
 for name in ['numpy.core.multiarray','numpy._core.multiarray']:
  mod=__import__(name,fromlist=['scalar']);result[(name,'scalar')]=mod.scalar
 return result
class Reader(pickle.Unpickler):
 def find_class(self,module,name):
  key=(module,name)
  if key not in self.classes:raise pickle.UnpicklingError('Unapproved checkpoint type '+repr(key))
  return self.classes[key]
def read_checkpoint(path):
 raw=Path(path).read_bytes();meta=json.loads(Path(str(path)+'.json').read_text());assert sha(path)==meta['sha256']
 assert meta['identity']==identity()
 reader=Reader(io.BytesIO(raw));reader.classes=allowed();return reader.load(),meta
def identity():
 freeze=O.parent/'lr1-cp1-add-preflight-20261031/FREEZE.json'
 return dict(input_manifest_sha=sha(freeze),adapter_sha=sha(p),daily_wrapper_sha=sha(__file__),python=sys.version)
class Daily:
 def __init__(self,r,cursor=None):self.r=r;self.cursor=cursor;self.committed={}
 def dump(self,path):
  value=dict(state=state(self.r),cursor=self.cursor,committed=self.committed)
  raw=pickle.dumps(value,protocol=5);path=Path(path);tmp=Path(str(path)+'.tmp');tmp.write_bytes(raw);os.replace(tmp,path)
  save(str(path)+'.json',dict(sha256=sha(path),identity=identity(),cursor=self.cursor,bytes=len(raw),fingerprint=fingerprint(self.r)))
 def load(self,path):
  value,meta=read_checkpoint(path);v=value['state'];self.r.__dict__.update(v['runner']);self.r.b0.__dict__.clear();self.r.b0.__dict__.update(v['b0'])
  assert set(self.r.accounts)==set(v['accounts'])
  for key,fields in v['accounts'].items():
   a=self.r.accounts[key];a.__dict__.clear();a.__dict__.update(fields);a.market=self.r.market;a.facts=self.r.facts;a.check()
   assert all(any(z is q for q in a.layers) for group in a.group_layers.values() for z in group)
  self.cursor=value['cursor'];self.committed=value['committed'];assert fingerprint(self.r)==meta['fingerprint'];return self
 def step(self,day,package_hash,complete=True):
  end=M.N.iso(day+'T15:10:00+08:00')
  if day in self.committed:
   if self.committed[day]!=package_hash:raise ValueError('Committed day revision requires explicit rollback; no silent replacement')
   return 'duplicate_noop'
  if not complete:return 'wait_incomplete'
  cutoffs=sorted(x for x in self.r.market.cutoffs if self.cursor is None or x>self.cursor)
  if not cutoffs or cutoffs[0]!=end:return 'wait_missing_or_out_of_order'
  opens=set(self.r.market.sessions['A']);closes=set(self.r.market.cutoffs)
  acts={datetime.datetime.combine(datetime.date.fromisoformat(d),datetime.time.min,M.N.TZ) for d in self.r.actions_by_date}
  events=sorted(x for x in opens|closes|acts if (self.cursor is None or x>self.cursor) and x<=end)
  for at in events:
   for a in self.r.accounts.values():a.settle_due(at)
   self.r._actions(at)
   for a in self.r.accounts.values():self.r._payments(a,at)
   if at in opens:
    for a in self.r.accounts.values():self.r.opening(a,at)
   if at in closes:self.r.planning(at)
  self.cursor=end;self.committed[day]=package_hash;return 'committed'
