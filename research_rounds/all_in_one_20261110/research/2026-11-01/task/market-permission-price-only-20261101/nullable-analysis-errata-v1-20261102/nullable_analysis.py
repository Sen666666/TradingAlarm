"""Analysis-only nullable adapters; no strategy or financial dependencies."""
from datetime import date,datetime
import math
import numpy as np
import pandas as pd

MISSING=object()
def cached_flag(value=MISSING):
 """Original facts store known Boolean flags as 0/1; decode only those values."""
 if value is MISSING or value is None or not np.isscalar(value) or bool(pd.isna(value)):return None
 if isinstance(value,(bool,np.bool_)):return bool(value)
 if isinstance(value,(int,float,np.integer,np.floating)) and value in (0,1):return bool(value)
 return None

def pending_time(value=MISSING):
 if value is MISSING:return dict(kind='UNKNOWN',date=None,reason='missing_field')
 if value is None:return dict(kind='ABSENT',date=None,reason=None)
 if isinstance(value,(list,tuple,dict,set,np.ndarray)):return dict(kind='UNKNOWN',date=None,reason='non_scalar')
 if not isinstance(value,(bool,np.bool_)) and bool(pd.isna(value)):return dict(kind='ABSENT',date=None,reason=None)
 if isinstance(value,(date,datetime,pd.Timestamp)):
  return dict(kind='PENDING',date=value.date().isoformat() if hasattr(value,'date') else value.isoformat(),reason=None)
 if isinstance(value,str):
  try:
   d=date.fromisoformat(value)
   if value!=d.isoformat():raise ValueError('not canonical ISO')
   return dict(kind='PENDING',date=d.isoformat(),reason=None)
  except ValueError:pass
 return dict(kind='UNKNOWN',date=None,reason='unsupported_or_invalid_date')

def analysis_scope(row,has_context_advance):
 p=pending_time(row.get('pending_failure_at',MISSING))
 support=row.get('mode')=='ACTIVE' and p['kind']=='ABSENT'
 # A missing permit/mode can never be manufactured by nullable normalization.
 stored=row.get('permit_next_open',MISSING)
 permit=bool(support and isinstance(stored,(bool,np.bool_)) and bool(stored))
 return dict(support=support,permit=permit,mature=bool(support and has_context_advance),mode=row.get('mode','UNKNOWN'),
  pending_kind=p['kind'],pending_date=p['date'],pending_unknown_reason=p['reason'])

def positive(value):
 if value is MISSING or value is None or isinstance(value,(bool,np.bool_)):return False
 try:return bool(pd.notna(value)) and math.isfinite(float(value)) and float(value)>0
 except (ValueError,TypeError):return False

def candidate_inputs(row):
 """Fail closed on every other unknown; no numeric field is zero-filled."""
 reasons=[]
 for name in ['stock_Q','I_valid','canonical_known']:
  value=row.get(name,MISSING)
  if not isinstance(value,(bool,np.bool_)) or not bool(value):reasons.append(name+':false_or_unknown')
 for name in ['raw_close','factor','I_floor','CP1_floor']:
  if not positive(row.get(name,MISSING)):reasons.append(name+':invalid_or_unknown')
 if not reasons:
  floor=max(float(row['I_floor']),float(row['CP1_floor']))/float(row['factor'])
  if float(row['raw_close'])<=floor:reasons.append('price_at_or_below_protection')
 else:floor=None
 return dict(eligible=not reasons,reasons=reasons,raw_floor=floor if not reasons else None)
