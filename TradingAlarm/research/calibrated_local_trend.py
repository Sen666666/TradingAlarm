"""Past-only likelihood selection among fixed local-trend specifications.

Selection is based on the preceding 252 available one-step log scores, not
strategy returns. A random-walk candidate can decline to infer a trend.
"""
import numpy as np
import pandas as pd

PARAMETERS=[(r,q) for r in (.01,.1,1.) for q in (0.,.001,.05)]
NAMES=['random_walk']+[f'R{r}_slopeQ{q}' for r,q in PARAMETERS]


def calibrated_frame(price):
    p=price.loc[price.gt(0)&np.isfinite(price)];y=np.log(p).to_numpy()
    variance=pd.Series(y,index=p.index).diff().shift().pow(2).rolling(21).mean().clip(lower=1e-16).to_numpy()
    n=len(p);k=len(PARAMETERS);F=np.array([[1.,1.],[0.,1.]]);H=np.array([1.,0.]);I=np.eye(2)
    states=None;losses=[];rows=[]
    for t in range(n):
        v=variance[t]
        if not np.isfinite(v):rows.append([np.nan]*7);continue
        if states is None:
            states=np.tile([y[t-1],0.],(k,1));cov=np.tile(np.diag([v,v/21**2]),(k,1,1))
        predicted=states@F.T
        prior=F@cov@F.T+np.array([np.diag([v,v*q]) for _,q in PARAMETERS])
        R=v*np.array([r for r,_ in PARAMETERS]);S=prior[:,0,0]+R
        innovations=y[t]-predicted[:,0];gain=prior[:,:,0]/S[:,None]
        # Select before appending today's loss or updating today's states.
        chosen=int(np.argmin(np.mean(losses[-252:],axis=0))) if len(losses)>=252 else 0
        rw_error=y[t]-y[t-1]
        errors=np.r_[rw_error,innovations];variances=np.r_[v,S]
        nll=.5*(np.log(variances/v)+errors**2/variances)  # common log(v) term cancels
        states=predicted+gain*innovations[:,None]
        A=I-gain[:,:,None]*H[None,None,:]
        cov=A@prior@A.transpose(0,2,1)+gain[:,:,None]*gain[:,None,:]*R[:,None,None]
        slope=0. if chosen==0 else states[chosen-1,1]
        strength=5+5*np.tanh(np.sqrt(5)*slope/np.sqrt(v))
        rows.append([strength,slope,chosen,errors[chosen]/np.sqrt(v),nll[chosen],nll[0],len(losses)>=252])
        losses.append(nll)
    return pd.DataFrame(rows,index=p.index,columns=['strength','velocity','selected','standardized_error','nll','rw_nll','selection_ready'],dtype=float).reindex(price.index)
