"""Paper-only prior-high channels and Wilder ATR. No account or sizing."""
import math
import pandas as pd

EPS=4*2**-53/(1-4*2**-53)
def gt(a,b):
    return a>b and abs(a-b)>EPS*max(abs(a),abs(b),1e-300)

def features(price):
    if not price.index.is_unique or not price.index.is_monotonic_increasing:
        raise ValueError('ordered unique original observations required')
    out=[];segment=None;prev=None;atr=None;trs=[];highs=[]
    for day,p in price.iterrows():
        seg=p.get('segment_id')
        changed=segment!=seg
        if changed:
            segment=seg;prev=None;atr=None;trs=[];highs=[]
        vals=[p.get(k) for k in ['high','low','close']]
        finite=all(v is not None and pd.notna(v) and math.isfinite(float(v)) and float(v)>0 for v in vals)
        valid=finite and pd.notna(seg) and bool(p.get('price_eligible',False)) and bool(p.get('observed_bar',False)) and not bool(p.get('synthetic_event_bar',True)) and not bool(p.get('source_invalid',True))
        if valid:
            h,l,c=map(float,vals)
            valid=h>=l and h>=c and c>=l
        if not valid:
            out.append(dict(valid_bar=False,clean_run_prior_bars=len(highs),TR=None,ATR14=None,ATR14_prior=None,U20=None,U55=None,z20=None,z55=None,break20=None,break55=None,rolloff20=None,rolloff55=None))
            prev=None;atr=None;trs=[];highs=[]
            continue
        ap=atr
        u20=max(highs[-20:]) if len(highs)>=20 else None
        u55=max(highs[-55:]) if len(highs)>=55 else None
        old20=max(highs[-21:-1]) if len(highs)>=21 else None
        old55=max(highs[-56:-1]) if len(highs)>=56 else None
        tr=h-l if prev is None else max(h-l,abs(h-prev),abs(l-prev))
        trs.append(tr)
        if atr is None and len(trs)>=14:atr=math.fsum(trs[:14])/14.0
        elif atr is not None:atr=(13*atr+tr)/14.0
        ready=ap is not None and ap>0
        out.append(dict(valid_bar=True,clean_run_prior_bars=len(highs),TR=tr,ATR14=atr,ATR14_prior=ap,
            U20=u20,U55=u55,z20=None if not ready or u20 is None else (c-u20)/ap,
            z55=None if not ready or u55 is None else (c-u55)/ap,
            break20=None if not ready or u20 is None else gt(c,u20),
            break55=None if not ready or u55 is None else gt(c,u55),
            rolloff20=None if old20 is None or u20 is None else u20<old20,
            rolloff55=None if old55 is None or u55 is None else u55<old55))
        highs.append(h);prev=c
    return pd.DataFrame(out,index=price.index)
