"""Typed frozen keys, without re-ranking or changing quantities/eligibility."""
from decimal import Decimal
from numbers import Real

def freeze_priority(raw):
 if not isinstance(raw,(tuple,list)) or not raw:raise ValueError('UNKNOWN original full priority key')
 out=[]
 for value in raw:
  if isinstance(value,(Real,Decimal)):
   n=Decimal(str(int(value) if isinstance(value,bool) else value))
   if not n.is_finite():raise ValueError('UNKNOWN nonfinite priority, never neutral fill')
   out.append((0,n))
  elif isinstance(value,str) and value:out.append((1,value))
  else:raise ValueError('unsupported/UNKNOWN original priority component')
 return tuple(out)

def queue(use,role,pool):
 if use in ('S','G') and role=='mobile' and pool=='confirmed':return 'C_EXPANSION'
 if use=='T' and role in ('core','mobile') and pool=='probe':return 'TRIAL'
 raise ValueError('role/pool/use inconsistent; core-only cannot enter C queue')

def creation_record(raw,use,role,pool,sid,sequence):
 return dict(schema='FROZEN_NATIVE_DISPATCH_V1',queue=queue(use,role,pool),original_priority=tuple(raw),typed_priority=freeze_priority(raw),sid=sid,sequence=sequence)

def dispatch_key(meta,retained):
 d=meta['dispatch'];expected=creation_record(d['original_priority'],d['original_use'],meta['role'],meta['pool'],d['sid'],d['sequence'])
 for k,v in expected.items():
  if d.get(k)!=v:raise ValueError('frozen dispatch metadata changed: '+k)
 if tuple(meta['priority'])!=d['original_priority']:raise ValueError('old raw priority changed after reservation')
 if retained:
  # Original SyntheticRunner.opening appends eligible existing buys first in
  # native reservation/insertion order. Never assign them today's PVR/H1.
  return (0,((0,d['sequence']),),d['sid'])
 return (1 if d['queue']=='C_EXPANSION' else 2,d['typed_priority'],d['sid'])
