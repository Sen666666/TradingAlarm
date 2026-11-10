"""Fixed-state forward filter, no fitted returns or backward state smoothing."""
import numpy as np
import pandas as pd
MEANS=np.array([-1.,0.,1.])/np.sqrt(5)

def filter_states(observations,evidence_weight=None,memory=True,student=False):
    x=np.asarray(observations,float);w=np.ones(len(x)) if evidence_weight is None else np.asarray(evidence_weight,float)
    if len(w)!=len(x):raise ValueError('weight length')
    transition=np.full((3,3),1/42) if memory else np.full((3,3),1/3)
    if memory:np.fill_diagonal(transition,20/21)
    state=np.ones(3)/3;rows=[]
    for value,weight in zip(x,w):
        if not np.isfinite(value) or not np.isfinite(weight):rows.append([np.nan]*4);continue
        if weight<=0:raise ValueError('positive evidence weight required')
        prior=state@transition;loglike=-.5*weight*(value-MEANS)**2
        # Student-t df5, scale sqrt(3/5), hence unit variance like the control.
        # Constants independent of state cancel during normalization.
        if student:loglike=-3*weight*np.log1p((value-MEANS)**2/3)
        z=np.log(prior)+loglike;state=np.exp(z-z.max());state/=state.sum()
        rows.append([10*state[2],*state])
    return pd.DataFrame(rows,columns=['strength','down_weight','neutral_weight','up_weight'])

def markov_frame(price,volume,joint=False,memory=True,student=False):
    f=pd.concat([price.rename('price'),volume.rename('volume')],axis=1)
    f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    r=np.log(f.price).diff();scale=np.sqrt(r.shift().pow(2).rolling(21).mean()).clip(lower=1e-8)
    weights=np.sqrt(f.volume/f.volume.shift().rolling(21).median()).clip(.25,4) if joint else None
    result=filter_states((r/scale).to_numpy(),weights.to_numpy() if joint else None,memory,student);result.index=f.index
    return result.reindex(price.index)
