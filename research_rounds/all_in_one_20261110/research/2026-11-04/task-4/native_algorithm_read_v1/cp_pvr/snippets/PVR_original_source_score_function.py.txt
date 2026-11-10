def score(f):
 """Independent finite-window calculation, no state/account/future input."""
 out=pd.DataFrame(index=f.index,columns=['r','scale','amount_ref','u','b','e','E','score'],dtype=float)
 valid=(f.close.gt(0)&np.isfinite(f.close)&f.amount.gt(0)&np.isfinite(f.amount))
 for k in ['price_eligible','observed_bar','is_observed_bar']:
  if k in f:valid &= f[k].fillna(False).astype(bool)
 for k in ['source_invalid','synthetic_event_bar']:
  if k in f:valid &= ~f[k].fillna(True).astype(bool)
 # Invalid rows and declared source changes restart the full preparation.
 seg=f.segment_id if 'segment_id' in f else pd.Series(0,index=f.index)
 block=((~valid)|(~valid.shift(fill_value=False))|seg.ne(seg.shift())).cumsum()
 weights=.9**np.arange(20,-1,-1);weights/=weights.sum()
 for _,g in f.loc[valid].groupby(block[valid],sort=False):
  r=np.log(g.close).diff();s=r.abs().shift().rolling(63,min_periods=63).median().mul(1.4826).clip(lower=1e-8)
  ar=g.amount.shift().rolling(21,min_periods=21).median()
  u=np.tanh(r/s);b=np.tanh(np.log(g.amount/ar));e=u*(1+.5*u.abs()*b)
  z=e.rolling(21,min_periods=21).apply(lambda x:np.dot(weights,x),raw=True)
  out.loc[g.index]=pd.DataFrame({'r':r,'scale':s,'amount_ref':ar,'u':u,'b':b,'e':e,'E':z,'score':50+50*np.tanh(2*z)},index=g.index)
 return out
