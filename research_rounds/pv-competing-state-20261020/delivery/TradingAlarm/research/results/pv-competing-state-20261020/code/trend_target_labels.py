"""Ex-post zigzag trend labels, delayed-oracle exposure and trajectory scoring.
Labels read future prices and exist only to evaluate; model exposures must never consume them."""
import math
import numpy as np
import pandas as pd

def scale(y):
    """Monthly log-return scale: RMS of the last 63 valid-bar log returns times sqrt(21)."""
    return y.diff().pow(2).rolling(63,min_periods=63).mean().pow(.5)*np.sqrt(21)

def zigzag(y,threshold):
    """Confirmed pivots [(position, 1 high / -1 low)] and provisional (position, direction) running extreme."""
    y=np.asarray(y,float);s=np.asarray(threshold,float);ready=np.flatnonzero(np.isfinite(s))
    if not len(ready):return [],None
    hi=lo=int(ready[0]);mode=0;ext=None;pivots=[]
    for t in range(hi+1,len(y)):
        if mode==0:
            hi=t if y[t]>y[hi] else hi;lo=t if y[t]<y[lo] else lo
            up=y[t]-y[lo]>=s[lo];down=y[hi]-y[t]>=s[hi]
            if up and down:pivots+=[(hi,1),(lo,-1)] if hi<lo else [(lo,-1),(hi,1)];mode=1 if hi<lo else -1;ext=t
            elif up:pivots.append((lo,-1));mode=1;ext=t
            elif down:pivots.append((hi,1));mode=-1;ext=t
        elif mode==1:
            if y[t]>y[ext]:ext=t
            elif y[ext]-y[t]>=s[ext]:pivots.append((ext,1));mode=-1;ext=t
        else:
            if y[t]<y[ext]:ext=t
            elif y[t]-y[ext]>=s[ext]:pivots.append((ext,-1));mode=1;ext=t
    return pivots,(None if mode==0 else (ext,mode))

def legs_from(index,y,threshold,pivots,provisional,ratio):
    """Legs between pivots; the leg to the running extreme and the sub-threshold tail after it are provisional."""
    y=np.asarray(y,float);points=[(p,False) for p,_ in pivots]
    if provisional is not None:points.append((provisional[0],True))
    if points and points[-1][0]<len(y)-1:points.append((len(y)-1,True))
    rows=[]
    for (a,_),(b,prov) in zip(points,points[1:]):
        move=y[b]-y[a];band=ratio*threshold[a]
        rows.append(dict(start=a,end=b,start_date=index[a],end_date=index[b],move=move,threshold=threshold[a],kind='up' if move>=band else 'down' if move<=-band else 'range',provisional=prov))
    return pd.DataFrame(rows,columns=['start','end','start_date','end_date','move','threshold','kind','provisional'])

def label_frame(close,k,ratio):
    """Bar t (return t-1 -> t) takes the label of the leg containing (t-1, t]; bars up to the first pivot are unlabeled."""
    y=np.log(close.astype(float));sigma=scale(y);threshold=(k*sigma).to_numpy()
    pivots,prov=zigzag(y.to_numpy(),threshold);legs=legs_from(y.index,y.to_numpy(),threshold,pivots,prov,ratio)
    label=np.full(len(y),'',dtype=object);leg=np.full(len(y),-1);flag=np.zeros(len(y),bool)
    for i,r in enumerate(legs.itertuples()):label[r.start+1:r.end+1]=r.kind;leg[r.start+1:r.end+1]=i;flag[r.start+1:r.end+1]=r.provisional
    return pd.DataFrame(dict(y=y,sigma=sigma,label=label,leg=leg,provisional=flag),index=y.index),legs

def oracle_state(y,legs,d,g):
    """Non-tradable bound: enter at close t0+d of each up leg, exit at the first close from the peak that has given back g,
    capped at the confirmed pivot ending the next leg. Returns close-time state and leg gain from entry to peak."""
    yv=np.asarray(y,float);n=len(yv);state=np.zeros(n);gain={};rows=list(legs.itertuples())
    for i,leg in enumerate(rows):
        if leg.kind!='up':continue
        a,b=leg.start,leg.end;e=a+d
        if e>=b:continue
        cap=rows[i+1].end if i+1<len(rows) and not rows[i+1].provisional else None
        hit=np.flatnonzero(yv[b:(n if cap is None else cap+1)]<=yv[b]+math.log(1-g))
        x=b+int(hit[0]) if len(hit) else cap
        state[e:(n if x is None else x)]=1.;gain[y.index[e]]=yv[b]-yv[e]
    return pd.Series(state,index=y.index),pd.Series(gain,dtype=float)

def trajectory(frame,legs,state,start,end):
    """Per-asset raw sums and events. held_t is the state at close t-1."""
    start,end=pd.Timestamp(start),pd.Timestamp(end);y=frame.y.to_numpy();pos=state.reindex(frame.index).to_numpy(float)
    if np.isnan(pos).any():raise ValueError('state must cover every labeled bar')
    r=np.r_[np.nan,np.diff(y)];held=np.r_[np.nan,pos[:-1]];inside=(frame.index>=start)&(frame.index<=end)&np.isfinite(r)
    days=pd.DataFrame(dict(year=frame.index.year,label=frame.label.to_numpy(),r=r,hr=held*r,h=held))[inside]
    daily=days.assign(n=1).groupby(['year','label'])[['n','r','hr','h']].sum().reset_index()
    events=[]
    for i,leg in enumerate(legs.itertuples()):
        if leg.kind!='up' or not start<=leg.end_date<=end:continue
        a,b=leg.start,leg.end;inleg=np.flatnonzero(pos[a:b]>0);e=dict(leg=i,start_date=leg.start_date,end_date=leg.end_date,move=leg.move,provisional=leg.provisional,missed=not len(inleg))
        e['entry_delay']=float(inleg[0]) if len(inleg) else np.nan
        e['elapsed']=(y[a+int(inleg[0])]-y[a])/(y[b]-y[a]) if len(inleg) else np.nan
        e['capture']=float(np.sum(pos[a:b]*np.diff(y[a:b+1]))/(y[b]-y[a]))
        if not leg.provisional:
            if pos[b]>0:
                out=np.flatnonzero(pos[b+1:]==0);x=b+1+int(out[0]) if len(out) else len(y)-1
                e.update(held_at_peak=True,exit_open=not len(out),giveback=1-math.exp(y[x]-y[b]),exit_lag=float(x-b))
            else:
                exits=[j for j in range(a+1,b+1) if pos[j]==0 and pos[j-1]>0]
                e.update(held_at_peak=False,residual=(y[b]-y[exits[-1]])/(y[b]-y[a]) if exits else np.nan)
        events.append(e)
    entries=[]
    for t in np.flatnonzero((pos>0)&(np.r_[0.,pos[:-1]]==0)):
        if t+1>=len(y) or not start<=frame.index[t]<=end:continue
        nxt=frame.label.iloc[t+1];entries.append(dict(date=frame.index[t],next_label=nxt,false=nxt in ('down','range')))
    return daily,pd.DataFrame(events),pd.DataFrame(entries,columns=['date','next_label','false'])

def summarize(daily,events,entries):
    """Pool raw sums across assets: up/down/range participation, leg-event and false-signal statistics."""
    out={};asset_years=float(daily.n.sum()/252)
    for kind in ['up','down','range']:
        x=daily[daily.label.eq(kind)];n=x.n.sum()
        out[kind+'_bars']=int(n);out[kind+'_time']=float(x.h.sum()/n) if n else np.nan
        out[kind+'_participation']=float(x.hr.sum()/x.r.sum()) if n and x.r.sum() else np.nan
    out['range_log_pnl_per_asset_year']=float(daily[daily.label.eq('range')].hr.sum()/asset_years) if asset_years else np.nan
    out['up_legs']=len(events)
    if len(events):
        out.update(missed_fraction=float(events.missed.mean()),entry_delay_median=float(events.entry_delay.median()),elapsed_median=float(events.elapsed.median()),
                   leg_capture_pooled=float((events.capture*events.move).sum()/events.move.sum()))
        peak=events[events.get('held_at_peak',pd.Series(False,index=events.index)).eq(True)]
        out.update(held_at_peak=len(peak),giveback_median=float(peak.giveback.median()) if len(peak) else np.nan,giveback_p75=float(peak.giveback.quantile(.75)) if len(peak) else np.nan,
                   exit_lag_median=float(peak.exit_lag.median()) if len(peak) else np.nan,exited_before_peak=int(events.get('held_at_peak',pd.Series(dtype=object)).eq(False).sum()),
                   residual_median=float(events.residual.median()) if 'residual' in events and events.residual.notna().any() else np.nan)
    labeled=entries[entries.next_label.ne('')]
    out.update(asset_years=asset_years,entries_per_asset_year=float(len(labeled)/asset_years) if asset_years else np.nan,
               false_per_asset_year=float(labeled.false.sum()/asset_years) if asset_years else np.nan,false_fraction=float(labeled.false.mean()) if len(labeled) else np.nan)
    out['asymmetry']=out['up_participation']-out['down_participation']
    return out
