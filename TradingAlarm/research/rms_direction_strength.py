"""Matched EWMA signed-close direction, RMS versus absolute-return normalization."""
import numpy as np
import pandas as pd

def rms_direction_frame(close,volume,joint=False):
 f=pd.concat([close.rename('close'),volume.rename('volume')],axis=1);f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)];r=f.close.pct_change(fill_method=None)
 w=(f.volume/f.volume.shift().rolling(21).median()).pow(.5).clip(.25,4) if joint else pd.Series(1.,index=f.index)
 w=w.where(f.volume.shift().rolling(21).count().eq(21));ew=lambda x:x.ewm(alpha=1/21,adjust=False,min_periods=21).mean()
 mass=ew(w);mean=ew(r*w)/mass;rms=(ew(r.pow(2)*w)/mass).pow(.5);balance=(mean/rms).where(rms.gt(0),0.).where(rms.notna())
 return pd.DataFrame(dict(strength=5+5*np.tanh(np.sqrt(5)*balance),mean=mean,rms=rms,balance=balance)).reindex(close.index)
