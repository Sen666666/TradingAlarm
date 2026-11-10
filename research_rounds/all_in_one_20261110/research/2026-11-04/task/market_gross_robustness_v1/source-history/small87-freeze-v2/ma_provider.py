"""Adjacent inclusive MA on the SAME stored causal X; stored63 never replaced."""
from pathlib import Path
import sys,math
import pandas as pd
O=Path(__file__).resolve().parent
sys.path.insert(0,str(O.parent/'market_gross_admission_native_v1'))
from market_info_v2 import MarketInfo as OriginalInfo

class MarketInfo(OriginalInfo):
 def __init__(self,path,expected_closes,window=63,cut=None):
  assert window in(62,63,64);self.ma_window=window
  super().__init__(path,expected_closes,cut)
  if window==63:
   for r in self.observations:r['MA_window']=63
   return
  f=pd.read_csv(path,index_col='date',parse_dates=True)
  if cut is not None:f=f.loc[:cut]
  ma=f.signal_close.rolling(window,min_periods=window).mean();prior=None
  for r,v in zip(self.observations,ma.to_numpy()):
   x=r['X'];v=float(v);known=all(z is not None and math.isfinite(z)and z>0 for z in(x,v,prior))
   r.pop('MA63');r.pop('previous_MA63');r.update(MA_window=window,MA_value=v,previous_MA_value=prior,state='UNKNOWN'if not known else'DOWN'if x<v and v<prior else'NOT_DOWN');prior=v
 def prefix(self,cut):return MarketInfo(self.path,self.expected_closes,self.ma_window,cut)
