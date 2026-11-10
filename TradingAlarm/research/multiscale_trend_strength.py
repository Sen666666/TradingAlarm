"""Fixed weekly/monthly/quarterly price-volume path agreement experiment.
Descriptive score, not a probability or significance statistic.
"""
import numpy as np
import pandas as pd
HORIZONS=(5,21,63)

def multiscale_frame(close,volume):
    f=pd.concat([close.rename('close'),volume.rename('volume')],axis=1)
    f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    y=np.log(f.close.to_numpy());v=f.volume.to_numpy();r=np.r_[np.nan,np.diff(y)]
    rows=np.full((len(f),4),np.nan)
    for i in range(63,len(f)):
        evidence=[]
        for h in HORIZONS:
            x=np.arange(1-h,1,dtype=float)
            w=np.clip(np.sqrt(v[i-h+1:i+1]/np.median(v[i-h+1:i+1])),.25,4)
            d=np.column_stack([np.ones(h),x])
            b=np.linalg.lstsq(d*np.sqrt(w[:,None]),(y[i-h+1:i+1]-y[i])*np.sqrt(w),rcond=None)[0]
            scale=np.sqrt(np.mean(r[i-h+1:i+1]**2))
            evidence.append(np.tanh(np.sqrt(h)*b[1]/scale) if scale>1e-12 else 0.)
        rows[i]=[5+5*np.mean(evidence),*evidence]
    return pd.DataFrame(rows,index=f.index,columns=['strength','weekly','monthly','quarterly']).reindex(close.index)
