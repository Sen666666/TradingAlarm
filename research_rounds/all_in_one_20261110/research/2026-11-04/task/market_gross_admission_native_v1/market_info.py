"""Stored, already-audited ETF observations only; no rolling or price model."""
from pathlib import Path
from decimal import Decimal as D
import bisect,hashlib,math
import pandas as pd

class MarketInfo:
 def __init__(self,path,cut=None):
  self.path=str(Path(path).resolve());self.sha256=hashlib.sha256(Path(path).read_bytes()).hexdigest()
  f=pd.read_csv(path,index_col='date',parse_dates=True)
  if cut is not None:f=f.loc[:cut]
  self.observations=[];prior=None
  for at,r in f.iterrows():
   x,ma=float(r.signal_close),float(r.ma63);known=all(v is not None and math.isfinite(v)and v>0 for v in(x,ma,prior))
   state='UNKNOWN'if not known else'DOWN'if x<ma and ma<prior else'NOT_DOWN'
   self.observations.append(dict(day=str(at.date()),available_at=pd.Timestamp(str(at.date())+'T15:10:00+08:00'),X=x,MA63=ma,previous_MA63=prior,state=state));prior=ma
  self.clocks=[r['available_at']for r in self.observations]
 def state(self,at):
  k=bisect.bisect_right(self.clocks,pd.Timestamp(at))-1
  return dict(self.observations[k],source=self.path,source_sha256=self.sha256)if k>=0 else dict(state='UNKNOWN',day=None,available_at=None,source=self.path,source_sha256=self.sha256)
 def prefix(self,cut):return MarketInfo(self.path,cut)
