"""Frozen earnings-growth screen; selection only, never consumes forward returns."""
import numpy as np
import pandas as pd

def select_pair(candidates,financial):
 """Returns matched low-ATR selections, before/after positive YTD profit-growth filter.

 financial requires one row for every candidate with a usable vintage label.
 This exploratory function does not certify vendor vintage authenticity.
 """
 required=['symbol','date','atr_fraction','turnover60']
 x=candidates[required].copy();f=financial[['symbol','date','ytd_attributable_growth_vendor','latest_vendor_pubDate','requested_windows_complete']].copy()
 if x.duplicated(['symbol','date']).any() or f.duplicated(['symbol','date']).any():raise ValueError('duplicate candidate or financial record')
 x=x.merge(f,on=['symbol','date'],how='left',validate='one_to_one')
 if not x.requested_windows_complete.eq(True).all():raise ValueError('incomplete requested report windows')
 x['growth']=pd.to_numeric(x.ytd_attributable_growth_vendor,errors='coerce')
 pub=pd.to_datetime(x.latest_vendor_pubDate,errors='coerce')
 if not np.isfinite(x[['growth','atr_fraction','turnover60']].to_numpy()).all() or pub.isna().any() or not pub.lt(x.date).all():raise ValueError('missing/invalid or not-yet-published financial value')
 def choose(part):return part.sort_values(['date','atr_fraction','turnover60','symbol'],ascending=[True,True,False,True]).groupby('date').head(10)
 return dict(base=choose(x),positive_ytd_growth=choose(x[x.growth>0]))
