"""Continuous synthetic-unit merger valuation, NOT raw-share cash accounting."""
import numpy as np
import pandas as pd

def bridge(parent,child,calendar,last_parent_date,listing_date,parent_raw_close,child_raw_close,ratio):
 last=pd.Timestamp(last_parent_date);listing=pd.Timestamp(listing_date)
 if last>=listing or not all(np.isfinite(x) and x>0 for x in [parent_raw_close,child_raw_close,ratio]):raise ValueError('invalid merger terms')
 if last not in parent.index or listing not in child.index:raise ValueError('missing bridge anchors')
 if not bool(parent.at[last,'observed_bar'] and parent.at[last,'positive_volume']) or not bool(child.at[listing,'observed_bar'] and child.at[listing,'positive_volume']):raise ValueError('unobserved anchors')
 # A synthetic parent unit has parent signal/raw units of raw-share value at last observation.
 # Child signal/raw scale at listing normalizes the subsequent adjusted-price continuation.
 factor=float(parent.at[last,'signal_close'])/parent_raw_close*ratio/(float(child.at[listing,'signal_close'])/child_raw_close)
 if not np.isfinite(factor) or factor<=0:raise ValueError('invalid factor')
 out=parent.reindex(calendar).copy();after=calendar>=listing
 out.loc[after,'signal_close']=child.signal_close.reindex(calendar[after])*factor
 for col in ['observed_bar','positive_volume']:
  out[col]=out[col].fillna(False).astype(bool)
  out.loc[after,col]=child[col].reindex(calendar[after],fill_value=False).astype(bool)
 gap=(calendar>last)&(calendar<listing)
 out.loc[gap,['observed_bar','positive_volume']]=False
 out['signal_close']=out.signal_close.ffill()
 # Identical two-close SMA200 exit applied to economically linked entitlement path.
 below=out.signal_close<out.signal_close.rolling(200,min_periods=200).mean()
 out['exit_signal']=below & below.shift(1,fill_value=False)
 return out,factor
