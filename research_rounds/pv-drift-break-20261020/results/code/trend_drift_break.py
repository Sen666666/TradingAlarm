"""Causal four-intervention filter: ordinary, level jump, observation shock, drift break.
Model weights are internal relative likelihoods, not calibrated market probabilities.
"""
import numpy as np
import pandas as pd

def drift_frame(close,volume,joint=True,duplicate_level=False):
    if not close.index.is_unique or not close.index.is_monotonic_increasing:raise ValueError('ordered unique dates required')
    f=pd.concat([close.rename('close'),volume.rename('volume')],axis=1);g=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    offset=np.log(g.close.iloc[0]);y=np.log(g.close/g.close.iloc[0]);r=y.diff();scale=np.sqrt(r.shift(1).pow(2).rolling(63).mean()).clip(lower=1e-8)
    activity=(g.volume/g.volume.shift(1).rolling(21).median()).pow(.5).clip(.5,2) if joint else pd.Series(1.,index=g.index)
    F=np.array([[1.,1.],[0.,1.]]);H=np.array([1.,0.]);I=np.eye(2);means=None;rows=[]
    for price,sigma,a in zip(y,scale,activity):
        if not np.isfinite(sigma) or not np.isfinite(a):rows.append([np.nan]*9);continue
        if means is None:
            means=np.tile([price,0.],(4,1));covs=np.tile(np.diag([sigma*sigma,sigma*sigma]),(4,1,1));weights=np.array([1.,0.,0.,0.]);rows.append([0.,price,0.,sigma,1.,0.,0.,0.,a]);continue
        prior=np.array([1-.04*a,.04*a/3,.04*a/3,.04*a/3]);nextmeans=[];nextcovs=[];logmass=[]
        for j in range(4):
            Q=np.diag([9. if j==1 or (j==3 and duplicate_level) else .01,.0025])*sigma*sigma
            if j==3 and not duplicate_level:Q+=8.99*sigma*sigma*np.ones((2,2))
            R=(9. if j==2 else .25)*sigma*sigma
            branches=[];logs=[]
            for k in range(4):
                mu=F@means[k];P=F@covs[k]@F.T+Q;residual=price-mu[0];S=P[0,0]+R;K=P[:,0]/S
                m=mu+K*residual;A=I-np.outer(K,H);C=A@P@A.T+np.outer(K,K)*R
                branches.append((m,C));logs.append(np.log(max(weights[k],1e-300))-.5*(np.log(2*np.pi*S)+residual*residual/S))
            logs=np.asarray(logs);z=logs.max();posterior=np.exp(logs-z);posterior/=posterior.sum();mean=sum(w*b[0] for w,b in zip(posterior,branches));cov=sum(w*(b[1]+np.outer(b[0]-mean,b[0]-mean)) for w,b in zip(posterior,branches))
            nextmeans.append(mean);nextcovs.append(cov);logmass.append(np.log(prior[j])+z+np.log(np.exp(logs-z).sum()))
        logs=np.asarray(logmass);weights=np.exp(logs-logs.max());weights/=weights.sum();means=np.asarray(nextmeans);covs=np.asarray(nextcovs)
        mean=weights@means;cov=sum(w*(P+np.outer(m-mean,m-mean)) for w,m,P in zip(weights,means,covs));sd=np.sqrt(max(cov[1,1],1e-30));strength=mean[1]/sd
        if abs(strength)<1e-6:strength=0.  # Numerical zero at vanishing covariance, not a market threshold.
        rows.append([strength,mean[0],mean[1],sd,*weights,a])
    result=pd.DataFrame(rows,index=g.index,columns=['strength','log_level','drift','drift_sd','ordinary_weight','jump_weight','shock_weight','drift_break_weight','activity']).reindex(close.index)
    result['log_level']+=offset
    return result

def exposure(strength):
    held=False;prev=np.nan;out=[]
    for s in strength:
        if np.isfinite(s):
            if held and s<=0:held=False
            elif not held and s>1 and (not np.isfinite(prev) or prev<=1):held=True
            prev=s
        out.append(float(held))
    return pd.Series(out,index=strength.index,name='target')
