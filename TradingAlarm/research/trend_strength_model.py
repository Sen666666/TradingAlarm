"""Causal Gaussian regime mixture, reset before each observation.
Strength is model-conditional drift confidence, not profit probability.
"""
import numpy as np
import pandas as pd
import math


def ndtr(values):
    return np.fromiter((.5*(1+math.erf(float(v)/math.sqrt(2))) for v in values),dtype=float,count=len(values))


def logsumexp(values):
    maximum=np.max(values)
    return maximum+np.log(np.exp(values-maximum).sum())


def online_regimes(observations,hazard=1/21):
    x=np.asarray(observations,dtype=float)
    if x.ndim==1:x=x[:,None]
    if not 0<hazard<1:raise ValueError('hazard must lie in (0,1)')
    counts=np.empty(0);sums=np.empty((0,x.shape[1]));logweights=np.empty(0);rows=[]
    for value in x:
        if not np.isfinite(value).all():
            rows.append([np.nan]*5);continue
        # Candidate zero-count state is a newly started segment; all older
        # states continue. Posterior moments below include today's observation.
        n=np.r_[0.,counts];totals=np.vstack([np.zeros(x.shape[1]),sums])
        logprior=np.r_[np.log(hazard),np.log1p(-hazard)+logweights] if len(counts) else np.array([0.])
        mean=totals/(1+n[:,None]);variance=1+1/(1+n)
        loglike=-.5*(x.shape[1]*np.log(2*np.pi*variance)+((value-mean)**2).sum(axis=1)/variance)
        logweights=logprior+loglike;logweights-=logsumexp(logweights)
        counts=n+1;sums=totals+value
        postmean=sums[:,0]/(1+counts);postvar=1/(1+counts);w=np.exp(logweights)
        drift=float(w@postmean);uncertainty=float(np.sqrt(max(0,w@(postvar+postmean**2)-drift**2)))
        rows.append([10*float(w@ndtr(postmean/np.sqrt(postvar))),drift,uncertainty,float(w[0]),float(w@counts)])
    return pd.DataFrame(rows,columns=['strength','drift','drift_sd','reset_probability','expected_run'])


def online_linear_regimes(observations,hazard=1/21):
    x=np.asarray(observations,dtype=float)
    if x.ndim==1:x=x[:,None]
    if not 0<hazard<1:raise ValueError('hazard must lie in (0,1)')
    n=np.empty(0);a=b=c=np.empty(0);u=v=np.empty((0,x.shape[1]));lw=np.empty(0);rows=[]
    for y in x:
        if not np.isfinite(y).all():rows.append([np.nan]*6);continue
        prior=np.r_[np.log(hazard),np.log1p(-hazard)+lw] if len(n) else np.array([0.])
        n=np.r_[0.,n];a=np.r_[1.,a];b=np.r_[0.,b];c=np.r_[1.,c]
        u=np.vstack([np.zeros(x.shape[1]),u]);v=np.vstack([np.zeros(x.shape[1]),v]);time=n/21
        det=a*c-b*b
        mean=((c-b*time)[:,None]*u+(a*time-b)[:,None]*v)/det[:,None]
        variance=1+(c-2*b*time+a*time*time)/det
        likelihood=-.5*(x.shape[1]*np.log(2*np.pi*variance)+((y-mean)**2).sum(axis=1)/variance)
        lw=prior+likelihood;lw-=logsumexp(lw);w=np.exp(lw)
        a=a+1;b=b+time;c=c+time*time;u=u+y;v=v+time[:,None]*y;n=n+1
        det=a*c-b*b
        intercept=(c*u[:,0]-b*v[:,0])/det;slope=(a*v[:,0]-b*u[:,0])/det
        drift=intercept+time*slope;var=(c-2*b*time+a*time*time)/det
        average=float(w@drift);sd=float(np.sqrt(max(0,w@(var+drift**2)-average**2)))
        rows.append([10*float(w@ndtr(drift/np.sqrt(var))),average,sd,float(w[0]),float(w@n),float(w@slope/21)])
    return pd.DataFrame(rows,columns=['strength','drift','drift_sd','reset_probability','expected_run','drift_slope'])


def strength_frame(signal_close,raw_close,volume,joint=True,estimator='constant'):
    frame=pd.concat([signal_close.rename('signal'),raw_close.rename('raw'),volume.rename('volume')],axis=1)
    valid=(frame>0).all(axis=1)&np.isfinite(frame).all(axis=1);f=frame.loc[valid]
    returns=np.log(f.signal).diff();scale=returns.shift().rolling(21).std(ddof=1).clip(lower=1e-8)
    price=returns/scale
    turnover=np.log(f.raw*f.volume);past=turnover.shift();vscale=past.rolling(21).std(ddof=1).clip(lower=1e-8)
    activity=(turnover-past.rolling(21).mean())/vscale
    features=pd.concat([price.rename('price'),activity.rename('activity')],axis=1) if joint else price.to_frame('price')
    if estimator not in ('constant','linear'):raise ValueError('Unknown strength estimator')
    result=(online_regimes if estimator=='constant' else online_linear_regimes)(features.to_numpy());result.index=f.index
    return result.reindex(frame.index)
