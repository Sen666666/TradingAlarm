"""RS-H1 pure ranking prototype. No E0, execution, portfolio or network imports."""
import numpy as np

WEIGHTS=(.4,.2,.2,.2)
MIN_OBSERVATIONS=6
MIN_REFERENCE=20

def raw_momentum(prices,segments,observations,t,h):
    """All columns use exactly h intervals of the same market-date clock."""
    n=prices.shape[1]
    if h<5 or h>252 or t<h:return np.full(n,np.nan)
    b=np.minimum(np.arange(5)*63,h)
    result=np.zeros(n);valid=np.isfinite(prices[t])&(prices[t]>0)&(observations[t]>=MIN_OBSERVATIONS)
    for j,w in enumerate(WEIGHTS,1):
        near,far=int(b[j-1]),int(b[j])
        if near==far:continue
        p,q=prices[t-near],prices[t-far]
        valid&=np.isfinite(p)&np.isfinite(q)&(p>0)&(q>0)&(segments[t-near]==segments[t])&(segments[t-far]==segments[t])
        with np.errstate(divide='ignore',invalid='ignore'):
            result+=w*(p/q-1)
    return np.where(valid,np.round(result,12),np.nan)

def mid_percentile(values,value):
    ref=values[np.isfinite(values)]
    if len(ref)<MIN_REFERENCE or not np.isfinite(value):return np.nan,len(ref)
    return 100*(np.count_nonzero(ref<value)+.5*np.count_nonzero(ref==value))/len(ref),len(ref)

def rank_known(rows):
    """Unknown candidates are separate; securities with scores keep score priority."""
    known=[r for r in rows if r['score'] is not None and np.isfinite(r['score'])]
    return sorted(known,key=lambda r:(-r['score'],r['symbol'])),[r for r in rows if r not in known]
