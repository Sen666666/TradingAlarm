"""Causal trajectory features and chronologically frozen ridge strength."""
import numpy as np
import pandas as pd


def features(close, raw, volume, joint=True):
    r=np.log(close).diff()
    sigma=r.shift().rolling(21).std().clip(lower=1e-8)
    p=(r/sigma).clip(-8,8)
    activity=np.log(raw*volume)
    a=((activity-activity.shift().rolling(21).mean())/
       activity.shift().rolling(21).std().clip(lower=1e-8)).clip(-8,8)
    series={'price':p,'activity':a} if joint else {'price':p}
    return pd.DataFrame({f'{key}_{lag}':s.shift(lag) for key,s in series.items() for lag in range(21)})


def path_target(close):
    r=np.log(close).diff()
    parts=[]
    for h in (5,21):
        future=pd.concat([r.shift(-k) for k in range(1,h+1)],axis=1)
        total=future.sum(axis=1,min_count=h)
        distance=future.abs().sum(axis=1,min_count=h)
        parts.append((total/distance.replace(0,np.nan)).where(distance.ne(0),0))
    return (parts[0]+parts[1])/2


def fit(x,y,weights,penalty=.1):
    x=np.asarray(x,float);y=np.asarray(y,float);w=np.asarray(weights,float);w=w/w.sum()
    mean=w@x;scale=np.sqrt(w@((x-mean)**2));scale=np.maximum(scale,1e-8)
    z=(x-mean)/scale;ym=float(w@y)
    coef=np.linalg.solve(z.T@(w[:,None]*z)+penalty*np.eye(x.shape[1]),z.T@(w*(y-ym)))
    return {'mean':mean.tolist(),'scale':scale.tolist(),'coef':coef.tolist(),'intercept':ym}


def predict(model,x):
    return ((np.asarray(x)-model['mean'])/model['scale'])@np.asarray(model['coef'])+model['intercept']
