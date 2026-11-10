"""Additional causal pace evidence, deliberately no temperature or policy."""
import numpy as np
import pandas as pd

SPANS=(5,21,63,126)
def describe(f):
 if not f.index.is_unique or not f.index.is_monotonic_increasing:raise ValueError('Ordered unique input required')
 pieces=[]
 for seg,g in f.groupby('segment_id',sort=False):
  a=g.loc[g.valid_strength_observation.astype(bool)]
  if a.empty:continue
  if not np.isfinite(a[['close','volume']]).all().all() or not a[['close','volume']].gt(0).all().all():raise ValueError('Invalid positive price-volume observation')
  # Price-unit invariant log ratios. Invalid rows are gaps on this clock.
  p=np.log(a.close/a.close.iloc[0]);r=p.diff()
  scale=(1.4826*r.abs().shift().rolling(63,min_periods=63).median()).clip(lower=1e-8)
  q=pd.DataFrame(index=a.index);q['r']=r;q['s']=scale
  count=np.arange(1,len(a)+1)
  for h in SPANS:
   mu=r.ewm(span=h,adjust=False).mean()
   ready=count>=max(65,h+1)
   q[f'mu{h}']=mu.where(ready);q[f'z{h}']=(np.sqrt(h)*mu/scale).where(ready)
  q['short_score']=50*(np.tanh(q.z5)+np.tanh(q.z21))
  q['long_score']=50*(np.tanh(q.z63)+np.tanh(q.z126))
  q['full_ready']=q.z126.notna()
  q['acute_down']=g.reindex(a.index).acute_down.fillna(False).astype(bool) if 'acute_down' in g else False
  m,slow=q.mu21,q.mu126
  both=m.gt(0)&slow.gt(0)
  q['profile']=np.select([
   ~q.full_ready,q.acute_down,both&q.z21.ge(1),both&q.z63.ge(1)&q.z126.ge(1),both,m.gt(0)&slow.le(0),m.le(0)&slow.gt(0),m.lt(0)&slow.lt(0)
  ],['unknown_long','acute_down','fast_up','slow_up','modest_up','long_weak_short_strong','long_strong_short_weak','aligned_down'],default='mixed')
  q['segment_id']=str(seg)
  pieces.append(q)
 if not pieces:raise ValueError('At least one valid observation required')
 result=pd.concat(pieces).reindex(f.index)
 result['acute_down']=result.acute_down.astype('boolean')
 result['full_ready']=result.full_ready.fillna(False).astype(bool)
 result['profile']=result.profile.fillna('invalid_observation')
 return result
