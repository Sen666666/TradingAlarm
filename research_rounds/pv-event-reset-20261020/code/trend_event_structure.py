"""Causal directional events with persistent price structure; heuristic, not probability."""
import numpy as np
import pandas as pd


def event_frame(close,volume,joint=True,event_exit=False,reset_on_exit=True):
    if not close.index.is_unique or not close.index.is_monotonic_increasing:
        raise ValueError('ordered unique index required')
    raw=pd.concat([close.rename('close'),volume.rename('volume')],axis=1)
    d=raw.loc[raw.gt(0).all(axis=1)&np.isfinite(raw).all(axis=1)]
    if d.empty:raise ValueError('no valid observations')
    y=np.log(d.close.to_numpy()/d.close.iloc[0]);v=d.volume.to_numpy();offset=np.log(d.close.iloc[0])
    r=pd.Series(y).diff();sigma=r.shift().pow(2).rolling(63).mean().pow(.5).clip(lower=1e-8).to_numpy()
    baseline=d.volume.shift().rolling(21).median().to_numpy()
    cum=np.r_[0.,np.cumsum(v)]
    direction=-1;ext=None;state=False;floor=np.nan;rows=[]
    for t in range(len(d)):
        event=0;entered=0;exited=0;confirmation=np.nan;pivot=np.nan;pivot_age=np.nan
        if not np.isfinite(sigma[t]+baseline[t]):
            rows.append([np.nan,np.nan,np.nan,np.nan,np.nan,0.,0.,0.,0.,np.nan]);continue
        if ext is None:ext=t
        previous_state=state
        # A previously established structure is invalidated by a return to its pivot.
        if state and not event_exit and y[t]<=floor:
            state=False;exited=1
        if (direction==-1 and y[t]<y[ext]) or (direction==1 and y[t]>y[ext]):ext=t
        if t>ext:
            activity=np.sqrt(((cum[t+1]-cum[ext+1])/(t-ext))/baseline[ext]) if joint else 1.
            activity=float(np.clip(activity,.5,2.))
            confirmation=(-direction)*(y[t]-y[ext])*activity/(np.sqrt(5)*sigma[ext])
            if confirmation>=1:
                event=-direction;pivot=y[ext];pivot_age=t-ext
                if event==1:
                    if state:floor=max(floor,pivot)
                    elif not exited:state=True;floor=pivot;entered=1
                elif event_exit and state:state=False;exited=1
                direction=event;ext=t
        # Research-only variant: a broken structure with an up detector starts a new trough search.
        # Applied after old event processing, matching the observed post-exit inconsistency.
        if reset_on_exit and exited and direction==1:
            direction=-1;ext=t
        if state and not previous_state:entered=1
        rows.append([confirmation,float(direction),y[ext],pivot,floor if state or exited else np.nan,float(event),float(state),float(entered),float(exited),pivot_age])
    columns=['confirmation','leg_direction','developing_extreme','confirmed_pivot','structure_floor','event','target','entered','exited','pivot_age']
    f=pd.DataFrame(rows,index=d.index,columns=columns).reindex(close.index)
    for col in ['developing_extreme','confirmed_pivot','structure_floor']:f[col]+=offset
    for col in ['event','entered','exited']:f[col]=f[col].fillna(0.)
    f['target']=f.target.ffill().fillna(0.)
    return f
