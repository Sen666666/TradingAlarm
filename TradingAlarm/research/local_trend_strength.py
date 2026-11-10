"""Forward local-linear log-price filter; fixed covariance ratios, no smoother.

Standard model structure: statsmodels statespace_local_linear_trend example.
Covariance ratios and volume weighting below are research assumptions, not
estimated market parameters or a claim of statistical calibration.
"""
import numpy as np
import pandas as pd


def local_trend_frame(price, volume, joint=False):
    f=pd.concat([price.rename('price'),volume.rename('volume')],axis=1)
    f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    y=np.log(f.price); r=y.diff()
    variance=r.shift().pow(2).rolling(21).mean().clip(lower=1e-16)
    activity=np.sqrt(f.volume/f.volume.shift().rolling(21).median()).clip(.25,4)
    F=np.array([[1.,1.],[0.,1.]])
    H=np.array([1.,0.]); I=np.eye(2); state=None; rows=[]
    for t in range(len(f)):
        v=variance.iloc[t]
        if not np.isfinite(v):rows.append([np.nan]*8);continue
        if state is None:
            state=np.array([y.iloc[t-1],0.]); P=np.diag([v,v/21**2])
        pred=F@state; prior=F@P@F.T+np.diag([v/21,v/21**3])
        R=v/(activity.iloc[t] if joint else 1.)
        S=prior[0,0]+R; K=prior[:,0]/S
        innovation=y.iloc[t]-pred[0]; state=pred+K*innovation
        A=I-np.outer(K,H); P=A@prior@A.T+np.outer(K,K)*R
        score=5+5*np.tanh(np.sqrt(5)*state[1]/np.sqrt(v))
        rows.append([score,state[0],state[1],pred[0],innovation,np.sqrt(v),K[1],np.linalg.eigvalsh(P).min()])
    return pd.DataFrame(rows,index=f.index,columns=['strength','level','velocity','forecast','innovation','scale','slope_gain','min_cov_eigenvalue']).reindex(price.index)
