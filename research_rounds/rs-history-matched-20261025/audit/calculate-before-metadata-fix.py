"""Offline descriptive RS calculations only; never executes an account."""
from pathlib import Path
import json,hashlib
import numpy as np
import pandas as pd
from prepare import HERE,SOURCE,NEW,OLD,EXAMPLES,read,write,sha,now
from model import raw_momentum,mid_percentile

class Study:
 def __init__(self,until=None):
  self.z=np.load(HERE/'inputs/matrix.npz')
  self.dates=pd.DatetimeIndex(self.z['dates']);self.symbols=list(self.z['symbols']);self.facts=read(HERE/'inputs/facts.json')
  if until is not None:self.dates=self.dates[self.dates<=until]
  self.arrays={k:self.z[k][:len(self.dates)] for k in ['close','raw_close','volume','segment','old_rs','e0_ready','e0_up','obs_count']}
  self.cache={}
 def at(self,t,h):
  if (t,h) not in self.cache:self.cache[t,h]=raw_momentum(self.arrays['close'],self.arrays['segment'],self.arrays['obs_count'],t,h)
  return self.cache[t,h]
 def row(self,sid,date,h_override=None):
  t=self.dates.get_loc(pd.Timestamp(date));j=self.symbols.index(sid);a=self.arrays
  origin=pd.Timestamp(self.facts[sid]['first_valid_close'])
  # The cache calendar starts in 2024. Older origins are censored but h already
  # reaches 252 at every fixed study date; no IPO age is claimed for those lines.
  age=t-self.dates.searchsorted(origin)
  h=min(252,int(age)) if h_override is None else int(h_override)
  fresh=bool(np.isfinite(a['close'][t,j]))
  reason=None
  if not fresh:reason='no_fresh_actual_close'
  elif a['obs_count'][t,j]<6 or h<5:reason='fewer_than_6_actual_closes'
  elif h>age:reason='requested_history_unavailable'
  values=self.at(t,h) if reason is None else np.full(len(self.symbols),np.nan)
  m=float(values[j]);score,nref=mid_percentile(values,m)
  if reason is None and not np.isfinite(m):reason='missing_anchor_or_source_segment_boundary'
  if reason is None and not np.isfinite(score):reason='reference_too_small'
  old=a['old_rs'][t,j] if fresh else np.nan
  oldvalues=np.where(np.isfinite(a['close'][t]),a['old_rs'][t],np.nan)
  oldpct,nold=mid_percentile(np.round(oldvalues,12),float(np.round(old,12)))
  end=a['close'][t,j];start=a['close'][t-h,j] if 0<=h<=t else np.nan
  def clean(x):return float(x) if np.isfinite(x) else None
  blocks=[]
  if reason is None:
   b=np.minimum(np.arange(5)*63,h)
   for k,w in enumerate([.4,.2,.2,.2],1):
    if b[k]>b[k-1]:
     p,q=a['close'][t-int(b[k-1]),j],a['close'][t-int(b[k]),j]
     blocks.append({'near':int(b[k-1]),'far':int(b[k]),'weight':w,'return':float(p/q-1)})
  return dict(symbol=sid,name=self.facts[sid]['name'],industry=self.facts[sid]['industry'],date=str(self.dates[t].date()),
   observations=int(a['obs_count'][t,j]),h=h,score=clean(score),reference_n=nref,raw_momentum=clean(m),
   horizon_return=clean(end/start-1) if np.isfinite(end) and np.isfinite(start) else None,
   old_rs=clean(old),old_percentile=clean(oldpct),old_reference_n=nold,
   e0_ready=bool(a['e0_ready'][t,j]) if np.isfinite(a['e0_ready'][t,j]) else None,
   e0_up=bool(a['e0_up'][t,j]) if np.isfinite(a['e0_up'][t,j]) else None,
   status=reason or 'rated',blocks=blocks,artificial_history_cut=h_override is not None)

def main():
 out=HERE/'results';out.mkdir(exist_ok=False)
 s=Study();date='2026-10-22';latest=[s.row(sid,date) for sid in s.symbols]
 examples=[s.row(sid,date) for sid in EXAMPLES]
 milestones=[]
 for sid in NEW:
  j=s.symbols.index(sid);real=np.flatnonzero(np.isfinite(s.arrays['close'][:,j]))
  for count in [6,22,64,127,253]:
   if len(real)<count:continue
   d=s.dates[real[count-1]]
   for target in [sid]+OLD:
    row=s.row(target,d);row['milestone_symbol']=sid;row['milestone_closes']=count;milestones.append(row)
 curves=[]
 for sid in EXAMPLES:
  j=s.symbols.index(sid);dates=s.dates[(s.dates>=max(pd.Timestamp('2025-12-31'),pd.Timestamp(s.facts[sid]['first_valid_close'])))];
  for d in dates:curves.append(s.row(sid,d))
 truncations=[s.row(sid,date,h_override=h) for sid in OLD for h in [5,21,63,126,252]]
 for name,rows in [('latest-all',latest),('examples',examples),('milestones',milestones),('curves',curves),('artificial-truncations',truncations)]:
  write(out/(name+'.json'),rows)
  frame=pd.DataFrame([{k:v for k,v in r.items() if k!='blocks'} for r in rows]);frame.to_csv(out/(name+'.csv'),index=False,encoding='utf-8-sig')
 from collections import Counter
 valid=[r for r in latest if r['score'] is not None]
 new_valid=[r for r in valid if r['old_rs'] is None]
 summary={'recorded_at':now(),'model':'RS-H1','date':date,'reference_pool':len(latest),'rated':len(valid),
  'old_rated':sum(r['old_rs'] is not None for r in latest),'newly_rated':len(new_valid),
  'newly_rated_symbols':[r['symbol'] for r in new_valid],'statuses':dict(Counter(r['status'] for r in latest)),
  'examples':examples,'algorithm_core_changes':0,'ranking_candidate_count':1,'formula_revisions_after_outputs':0,'accounts_run':0,
  'source_matrix_sha256':sha(HERE/'inputs/matrix.npz'),'protocol_sha256':sha(HERE/'PROTOCOL.md'),
  'code_sha256':{str(p.relative_to(HERE)):sha(p) for p in sorted((HERE/'code').glob('*.py'))}}
 write(out/'summary.json',summary)
 print(json.dumps({k:v for k,v in summary.items() if k not in ['examples','code_sha256','newly_rated_symbols']},ensure_ascii=False),flush=True)

if __name__=='__main__':main()
