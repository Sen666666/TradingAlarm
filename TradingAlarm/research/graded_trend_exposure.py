"""Fixed three-state exposure from existing trend strength; no new price factor."""
import numpy as np
import pandas as pd

def graded_exposure(strength):
    upper=5+5*np.tanh(1);lower=5-5*np.tanh(1);state=0.;previous=None;values=[]
    for x in strength:
        if np.isfinite(x):
            if state>0 and x<=lower:state=0.
            elif state==1 and x<=5:state=.5
            elif state==.5 and x>=upper:state=1.
            elif state==0 and x>=upper and (previous is None or previous<upper):state=1.
            previous=x
        values.append(state)
    return pd.Series(values,index=strength.index,name='exposure')
