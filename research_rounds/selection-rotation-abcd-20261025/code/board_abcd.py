"""Causal current-pool dual queues, separate from trading/account state."""
import numpy as np
import pandas as pd

def returns(c,s,h):
 out=np.full(c.shape,np.nan)
 a,b=c[h:],c[:-h];good=np.isfinite(a)&np.isfinite(b)&(a>0)&(b>0)&(s[h:]==s[:-h])
 out[h:]=np.where(good,a/b-1,np.nan);return out

def percentile(a,min_refs=20):
 f=pd.DataFrame(a);n=f.notna().sum(axis=1);return ((f.rank(axis=1,method='average')-.5).div(n,axis=0)*100).where(n.ge(min_refs),axis=0).to_numpy()

def interleave(first,second):
 out=[];seen=set();i=j=0
 while i<len(first) or j<len(second):
  while i<len(first) and first[i] in seen:i+=1
  if i<len(first):out.append(first[i]);seen.add(first[i]);i+=1
  while j<len(second) and second[j] in seen:j+=1
  if j<len(second):out.append(second[j]);seen.add(second[j]);j+=1
 return out

def gate_or(a,b):
 # Missing long channel is not a global IPO exclusion. A prepared false short
 # channel plus an unprepared long channel is an observed empty candidate set.
 return np.where((a==1)|(b==1),1.,np.where(np.isfinite(a)|np.isfinite(b),0.,np.nan))

def channel(values,condition):
 ready=np.logical_and.reduce([np.isfinite(v) for v in values]);return np.where(ready,condition.astype(float),np.nan)

def build(z,metadata):
 symbols=[str(s) for s in z['symbols']];dates=z['dates'];c=z['close'];s=z['segment'];long=z['score'];sec=np.array([x.startswith('URFI') for x in symbols]);stock=~sec
 r={h:returns(c,s,h) for h in [5,21,63,126]};short=np.full(c.shape,np.nan)
 for mask in [stock,sec]:short[:,mask]=(percentile(r[21][:,mask])+percentile(r[63][:,mask]))/2
 fast=channel([r[5],short],r[5]>0);steady=channel([r[63],r[126],long],(r[63]>0)&(r[126]>0))
 b21=np.full(c.shape,np.nan);b63=np.full(c.shape,np.nan);n21=np.zeros(c.shape,dtype=np.int16);n63=n21.copy()
 for j in np.flatnonzero(sec):
  ids=[k for k,sid in enumerate(symbols) if not sec[k] and metadata[sid]['sector_id']==symbols[j]]
  for h,breadth,count in [(21,b21,n21),(63,b63,n63)]:
   a=r[h][:,ids];n=np.isfinite(a).sum(axis=1);q=(a>0).sum(axis=1);breadth[:,j]=np.divide(q,n,out=np.full(len(n),np.nan),where=n>0);count[:,j]=n
 fast[:,sec]=channel([r[5][:,sec],r[21][:,sec],b21[:,sec],short[:,sec]],(r[5][:,sec]>0)&(r[21][:,sec]>0)&(b21[:,sec]>.5))
 steady[:,sec]=channel([r[63][:,sec],r[126][:,sec],b63[:,sec],long[:,sec]],(r[63][:,sec]>0)&(r[126][:,sec]>0)&(b63[:,sec]>.5))
 gate=gate_or(fast,steady);rank=np.full(c.shape,np.nan)
 def ordered(ids,vals):return sorted(ids,key=lambda k:(-round(float(vals[k]),12),symbols[k]))
 groups=[list(np.flatnonzero(sec))]
 groups += [[k for k,sid in enumerate(symbols) if not sec[k] and metadata[sid]['sector_id']==symbols[j]] for j in np.flatnonzero(sec)]
 for t in range(len(dates)):
  for ids in groups:
   a=ordered([j for j in ids if fast[t,j]==1],short[t]);b=ordered([j for j in ids if steady[t,j]==1],long[t]);queue=interleave(b,a) if ids and sec[ids[0]] else interleave(a,b)
   for n,j in enumerate(queue):rank[t,j]=100*(1-n/max(1,len(queue)))
 return dict(dates=dates,symbols=np.array(symbols),short=short,long=long,rank=rank,gate=gate,fast=fast,steady=steady,r5=r[5],r21=r[21],r63=r[63],r126=r[126],breadth21=b21,breadth63=b63,n21=n21,n63=n63)

class Board:
 def __init__(self,z):
  self.source=z;self.z={k:z[k] for k in ['dates','symbols','rank','gate','short','long']};self.dates=pd.DatetimeIndex(self.z['dates']);self.cols={str(s):j for j,s in enumerate(self.z['symbols'])}
 def at(self,date):
  i=self.dates.get_indexer([pd.Timestamp(date)])[0]
  if i<0:raise ValueError('Date outside frozen board')
  return Row(self,i)

class Row:
 def __init__(self,board,i):self.board=board;self.i=i
 def get(self,sid,field):
  j=self.board.cols.get(sid)
  return float(self.board.z[field][self.i,j]) if j is not None else float('nan')
 def allowed(self,sid):
  v=self.get(sid,'gate');return bool(v) if np.isfinite(v) else None
