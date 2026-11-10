import pandas as pd,numpy as np

def evidence(f,g):
 f=f.reindex(g.index);valid=f.close.gt(0)&f.amount.gt(0)&np.isfinite(f.close)&np.isfinite(f.amount)
 for k in ['price_eligible','observed_bar','is_observed_bar']:
  if k in f:valid &= f[k].fillna(False).astype(bool)
 block=(~valid|~valid.shift(fill_value=False)|g.segment_id.ne(g.segment_id.shift())).cumsum()
 out=pd.DataFrame({k:pd.Series(np.nan,index=g.index,dtype=float) for k in ['ema21','return10','up_amount10']});out['new_ok']=False;out['weak']=False
 for _,q in f.loc[valid].groupby(block[valid],sort=False):
  c=q.close;a=q.amount;ema=c.ewm(span=21,adjust=False,min_periods=21).mean();ret=c.pct_change(10);up=a.where(c.diff()>0,0).rolling(10,min_periods=10).sum()/a.rolling(10,min_periods=10).sum()
  warm=(g.loc[q.index,'e0_target'].astype(bool)&g.loc[q.index,'g_ready'].astype(bool)&g.loc[q.index,'g_grade'].ge(2))
  new=(warm.rolling(5,min_periods=5).sum()>=3)&c.gt(ema)&ema.gt(ema.shift(5))&ret.gt(0)&up.ge(.6)
  weak=(c.lt(ema).rolling(3,min_periods=3).sum()==3)&ret.le(0)&up.lt(.5)
  out.loc[q.index]=pd.DataFrame(dict(ema21=ema,return10=ret,up_amount10=up,new_ok=new,weak=weak),index=q.index)
 out[['new_ok','weak']]=out[['new_ok','weak']].fillna(False).astype(bool)
 return out

def gap_ok(new,old):return new is not None and old is not None and np.isfinite(new) and np.isfinite(old) and new>=50 and new-old>=10

def perturb(stocks,clock,seed,admission):
 if seed==0:return stocks
 from dataclasses import replace
 groups={}
 for s in stocks:
  rank=s.rank.read(clock) if s.rank else None
  if rank is not None:groups.setdefault(int(rank//10),[]).append(s.security_id)
 values={}
 for band,ids in groups.items():
  ids=sorted(ids,reverse=seed==2)
  for j,sid in enumerate(ids):values[sid]=band*10+9.999*(len(ids)-j)/(len(ids)+1)
 return tuple(replace(s,rank=admission.Rank(values[s.security_id],clock.decision_at,clock.decision_at)) if s.security_id in values else s for s in stocks)
