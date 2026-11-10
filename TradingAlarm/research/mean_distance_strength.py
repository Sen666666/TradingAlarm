"""Fixed20/60price EMA distance with volume-only ablation; native sign crossover."""
import numpy as np
import pandas as pd

def distance_frame(close,volume,joint=False):
 f=pd.concat([close.rename('close'),volume.rename('volume')],axis=1);f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
 if joint:
  w=(f.volume/f.volume.shift().rolling(21,min_periods=21).median()).pow(.5).clip(.25,4);w=w.fillna(1.)
 else:w=pd.Series(1.,index=f.index)
 means={h:(f.close*w).ewm(span=h,adjust=False).mean()/w.ewm(span=h,adjust=False).mean() for h in [20,60]}
 distance=(means[20]-means[60])/f.close;rms=np.log(f.close).diff().pow(2).rolling(21,min_periods=21).mean().pow(.5)
 ready=pd.Series(np.arange(len(f))>=59,index=f.index);scaled=(distance/(rms*np.sqrt(20))).where(rms.gt(1e-12),0.)
 return pd.DataFrame(dict(strength=(5+5*np.tanh(scaled)).where(ready),distance=distance.where(ready),target=distance.gt(0).where(ready,False).astype(float))).reindex(close.index)
