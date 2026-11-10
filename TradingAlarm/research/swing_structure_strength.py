"""Causal confirmed close-swing structure, never backdates a signal to its pivot."""
import numpy as np
import pandas as pd

def envelope_view(highs,lows,extreme,direction):
    # A partial leg cannot establish a lower high or a higher low.
    # It can extend an existing boundary; confirmed events own new pivots.
    h=list(highs);l=list(lows)
    if direction==1 and h:h[-1]=max(h[-1],extreme)
    if direction==-1 and l:l[-1]=min(l[-1],extreme)
    return h,l

def swing_frame(price,developing=False,diagnostics=False,envelope=False):
    p=price.loc[price.gt(0)&np.isfinite(price)];y=np.log(p.to_numpy());r=np.r_[np.nan,np.diff(y)]
    rows=np.full((len(p),9 if diagnostics else 5),np.nan);direction=0;highs=[];lows=[];extreme=None;threshold=None;events=[]
    for i in range(22,len(p)):
        scale=float(np.sqrt(np.mean(r[i-21:i]**2)))
        if scale<=1e-12:continue
        if extreme is None:extreme=y[i-1];extreme_i=i-1;threshold=np.sqrt(5)*scale
        if direction==0:
            if abs(y[i]-extreme)>=threshold:
                kind='low' if y[i]>extreme else 'high';(lows if kind=='low' else highs).append(extreme);events.append((kind,extreme_i,i,extreme));direction=1 if kind=='low' else -1;extreme=y[i];extreme_i=i;threshold=np.sqrt(5)*scale
        elif direction==1:
            if y[i]>=extreme:extreme=y[i];extreme_i=i;threshold=np.sqrt(5)*scale
            elif extreme-y[i]>=threshold:
                highs.append(extreme);events.append(('high',extreme_i,i,extreme));direction=-1;extreme=y[i];extreme_i=i;threshold=np.sqrt(5)*scale
        else:
            if y[i]<=extreme:extreme=y[i];extreme_i=i;threshold=np.sqrt(5)*scale
            elif y[i]-extreme>=threshold:
                lows.append(extreme);events.append(('low',extreme_i,i,extreme));direction=1;extreme=y[i];extreme_i=i;threshold=np.sqrt(5)*scale
        current_highs=highs+([extreme] if developing and direction==1 else [])
        current_lows=lows+([extreme] if developing and direction==-1 else [])
        if envelope:current_highs,current_lows=envelope_view(highs,lows,extreme,direction)
        h=current_highs[-1]-current_highs[-2] if len(current_highs)>=2 else np.nan
        l=current_lows[-1]-current_lows[-2] if len(current_lows)>=2 else np.nan
        z=0.
        if np.isfinite(h+l):
            if h>0 and l>0:z=min(h,l,y[i]-current_lows[-1])/scale
            elif h<0 and l<0:z=max(h,l,y[i]-current_highs[-1])/scale
        row=[5+5*np.tanh(z),h,l,highs[-1] if highs else np.nan,lows[-1] if lows else np.nan]
        if diagnostics:row += [current_highs[-1] if current_highs else np.nan,current_lows[-1] if current_lows else np.nan,direction,scale]
        rows[i]=row
    frame=pd.DataFrame(rows,index=p.index,columns=['strength','high_change','low_change','last_high','last_low']+(['view_high','view_low','leg_direction','scale'] if diagnostics else [])).reindex(price.index)
    return frame,[dict(kind=k,pivot_date=str(p.index[a].date()),confirmation_date=str(p.index[b].date()),log_price=float(value)) for k,a,b,value in events]
