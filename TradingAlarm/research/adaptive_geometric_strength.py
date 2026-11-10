"""Sequential expert weighting, no hindsight smoothing or return-trained parameters."""
import numpy as np
import pandas as pd

def fit_experts(log_prices,volume=None):
    y=np.asarray(log_prices,float);time=np.arange(1-len(y),1,dtype=float)
    design=np.column_stack([np.ones(len(y)),time,.5*time*time]);w=np.exp2(time/5)
    if volume is not None:w*=np.clip(np.sqrt(np.asarray(volume)/np.median(volume)),.25,4)
    velocities=[];forecasts=[]
    for degree in (1,2):
        d=design[:,:degree+1];beta=np.linalg.lstsq(d*np.sqrt(w[:,None]),(y-y[-1])*np.sqrt(w),rcond=None)[0]
        velocities.append(beta[1]);forecasts.append(y[-1]+np.array([1.,1.,.5])[:degree+1]@beta)
    return np.asarray(velocities),np.asarray(forecasts)

def update_weights(previous,errors,variance):
    prior=(1-1/21)*np.asarray(previous)+(1/21)*.5
    logweights=np.log(prior)-.5*np.square(errors)/max(float(variance),1e-12)
    logweights-=np.max(logweights);weights=np.exp(logweights)
    return weights/weights.sum()

def adaptive_frame(signal_close,raw_close,volume,joint=True):
    frame=pd.concat([signal_close.rename('signal'),raw_close.rename('raw'),volume.rename('volume')],axis=1)
    f=frame.loc[(frame>0).all(axis=1)&np.isfinite(frame).all(axis=1)]
    logp=np.log(f.signal.to_numpy());v=f.volume.to_numpy();r=np.r_[np.nan,np.diff(logp)]
    rows=np.full((len(f),7),np.nan);weights=np.array([.5,.5]);forecast=None;variance=None
    for i in range(21,len(f)):
        if forecast is not None:weights=update_weights(weights,logp[i]-forecast,variance)
        velocities,forecast=fit_experts(logp[i-20:i+1],v[i-20:i+1] if joint else None)
        scale=float(np.sqrt(np.mean(r[i-20:i+1]**2)));variance=scale**2
        velocity=float(weights@velocities);score=5+5*np.tanh(np.sqrt(5)*velocity/scale) if scale>1e-12 else 5.
        rows[i]=[score,velocity,scale,weights[0],weights[1],velocities[0],velocities[1]]
    return pd.DataFrame(rows,index=f.index,columns=['strength','velocity','path_rms','linear_weight','quadratic_weight','linear_velocity','quadratic_velocity']).reindex(frame.index)
