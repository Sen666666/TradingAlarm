"""Complete per-field typed fingerprints; no account/event imports."""
from pathlib import Path
from datetime import date,datetime
from decimal import Decimal
from fractions import Fraction
from dataclasses import is_dataclass,fields
import hashlib,json,math,types
import numpy as np
import pandas as pd
def text(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def norm(x,refs=None,seen=None,path='$'):
 refs={} if refs is None else refs;seen={} if seen is None else seen
 if id(x) in refs:return {'reference':refs[id(x)]}
 if x is pd.NA:return {'pd.NA':True}
 if x is pd.NaT:return {'pd.NaT':True}
 if isinstance(x,np.generic):return {'numpy':str(x.dtype),'value':norm(x.item(),refs,seen,path)}
 if x is None or isinstance(x,(str,bool,int)):return x
 if isinstance(x,float):return {'float':x.hex() if math.isfinite(x) else repr(x)}
 if isinstance(x,Decimal):return {'Decimal':str(x)}
 if isinstance(x,Fraction):return {'Fraction':[x.numerator,x.denominator]}
 if isinstance(x,(date,datetime)):return {'date':x.isoformat()}
 if isinstance(x,Path):return {'Path':str(x)}
 if isinstance(x,pd.DataFrame):
  raw=pd.util.hash_pandas_object(x,index=True).to_numpy().tobytes()
  return {'DataFrame':hashlib.sha256(raw).hexdigest(),'shape':list(x.shape),'columns':norm(x.columns.tolist()),'dtypes':[str(t) for t in x.dtypes],'index_type':str(x.index.dtype),'index_names':list(x.index.names)}
 if isinstance(x,(pd.Series,pd.Index)):
  raw=pd.util.hash_pandas_object(x,index=True).to_numpy().tobytes()
  return {type(x).__name__:hashlib.sha256(raw).hexdigest(),'dtype':str(x.dtype),'name':str(x.name),'length':len(x)}
 if isinstance(x,np.ndarray):
  body=norm(x.tolist(),refs,seen,path) if x.dtype.hasobject else hashlib.sha256(x.tobytes()).hexdigest()
  return {'array':body,'dtype':str(x.dtype),'shape':list(x.shape)}
 if isinstance(x,(types.FunctionType,types.MethodType,type)):
  f=x.__func__ if isinstance(x,types.MethodType) else x
  return {'callable':f.__module__+'.'+f.__qualname__,'code':hashlib.sha256(f.__code__.co_code).hexdigest() if hasattr(f,'__code__') else None}
 if id(x) in seen:return {'alias':seen[id(x)]}
 seen[id(x)]=path
 if isinstance(x,dict):return {'type':type(x).__name__,'pairs':[[norm(k,refs,seen,path+'/key'+str(i)),norm(v,refs,seen,path+'/'+str(k))] for i,(k,v) in enumerate(sorted(x.items(),key=lambda p:repr(p[0])))]}
 if isinstance(x,(tuple,list,set,frozenset)):
  a=sorted(x,key=repr) if isinstance(x,(set,frozenset)) else x
  return {type(x).__name__:[norm(v,refs,seen,path+'/'+str(i)) for i,v in enumerate(a)]}
 d={f.name:getattr(x,f.name) for f in fields(x)} if is_dataclass(x) else getattr(x,'__dict__',None)
 if d is None:raise ValueError('unsupported snapshot type '+type(x).__module__+'.'+type(x).__qualname__)
 return {'type':type(x).__module__+'.'+type(x).__qualname__,'state':norm(d,refs,seen,path+'/state')}
def digest(x,refs=None):return hashlib.sha256(text(norm(x,refs)).encode()).hexdigest()
def snapshot(r):
 a=r.account;m=a.market;f=a.facts;i=r.inputs;old=r.rights_legacy_inputs
 refs={id(r):'runner',id(a):'account',id(m):'market',id(f):'facts',id(i):'inputs',id(old):'old_inputs',id(m.native):'native'}
 roots={'runner':r,'account':a,'market':m,'facts':f,'inputs':i,'old_inputs':old,'native':m.native}
 out={}
 for name,obj in roots.items():
  for k,v in obj.__dict__.items():
   if name=='runner' and k in {'action_evidence'}:continue
   # Source metadata was originally JSON. Fast hashing is permitted only
   # after an exact JSON roundtrip; tuples/non-string keys/NaN fall back to
   # the typed path. Financial and mutable native objects never use it.
   if name in {'inputs','old_inputs'} and k in {'m','meta','selection','rules','protocol','lines','seeds','objects','merged_objects','month_objects'}:
    try:
     encoded=text(v)
     if v==json.loads(encoded):
      out[name+'.'+k]=hashlib.sha256(('JSON:'+encoded).encode()).hexdigest();continue
    except (ValueError,TypeError):pass
   out[name+'.'+k]=digest(v,refs)
 return out
ALLOWED={'runner.last_completed_event','runner.events','runner.action_log','runner.no_subscription_actions','account.last_cursor','account.as_of','account.audit_log','account.native_callbacks','market.prices','market.known','market.factors','native._fx_cache','native.notices','native._notice_keys','inputs.row_index'}
def compare(before,after):
 changed=[k for k in sorted(set(before)|set(after)) if before.get(k)!=after.get(k)]
 unexpected=[k for k in changed if k not in ALLOWED]
 return dict(changed=changed,unexpected=unexpected,all_other_fields_exact=not unexpected,field_count_before=len(before),field_count_after=len(after))
