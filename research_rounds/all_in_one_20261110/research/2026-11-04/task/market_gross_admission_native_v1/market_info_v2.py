"""Availability-domain repair only; original stored-value D formula unchanged."""
import bisect
import pandas as pd
from market_info import MarketInfo as OriginalMarketInfo

class MarketInfo(OriginalMarketInfo):
 def __init__(self,path,expected_closes,cut=None):
  super().__init__(path,cut)
  self.expected_closes=tuple(sorted(pd.Timestamp(x)for x in expected_closes))
  assert self.expected_closes and len(set(self.expected_closes))==len(self.expected_closes)
 def state(self,at):
  at=pd.Timestamp(at);v=super().state(at);k=bisect.bisect_right(self.expected_closes,at)-1
  if k<0 or at.date()>self.expected_closes[-1].date():
   return dict(v,state='UNKNOWN',availability_reason='outside_expected_session_domain')
  expected=self.expected_closes[k]
  if v['available_at']!=expected:
   return dict(v,state='UNKNOWN',availability_reason='missing_expected_completed_CLOSE',expected_completed_CLOSE=expected)
  return v
 def prefix(self,cut):return MarketInfo(self.path,self.expected_closes,cut)
