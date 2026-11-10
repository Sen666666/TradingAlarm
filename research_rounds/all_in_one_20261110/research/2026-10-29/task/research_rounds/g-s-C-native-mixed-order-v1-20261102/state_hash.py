"""Test-only full instance graph hash, including private state and alias links.

Pickle bytes encode incidental immutable-object memoization, and may change
after an equal-state restore. This encoder traverses EVERY instance attribute;
unsupported values raise rather than being omitted. No trading code calls it.
"""
from datetime import datetime,date
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
import hashlib,json

def full_state_hash(value):
 seen={}
 def norm(x,path):
  if x is None or isinstance(x,(str,int,bool)):return x
  if isinstance(x,float):return ['float',repr(x)]
  if isinstance(x,(Decimal,Fraction,datetime,date,Path)):return [type(x).__name__,str(x)]
  if isinstance(x,bytes):return ['bytes',hashlib.sha256(x).hexdigest()]
  if id(x) in seen:return {'$ref':seen[id(x)]}
  seen[id(x)]=path
  if isinstance(x,dict):return {str(k):norm(v,path+'.'+str(k)) for k,v in sorted(x.items(),key=lambda kv:str(kv[0]))}
  if isinstance(x,(list,tuple)):return [type(x).__name__,[norm(v,path+'.'+str(i)) for i,v in enumerate(x)]]
  if isinstance(x,(set,frozenset)):return [type(x).__name__,[norm(v,path+'.set'+str(i)) for i,v in enumerate(sorted(x,key=repr))]]
  if hasattr(x,'__dict__'):return [type(x).__module__+'.'+type(x).__qualname__,norm(vars(x),path+'.vars')]
  raise TypeError('unsupported complete-state field '+path+' '+str(type(x)))
 return hashlib.sha256(json.dumps(norm(value,'root'),sort_keys=True,separators=(',',':')).encode()).hexdigest()
