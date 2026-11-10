"""PVS-B3: declared-scale directional evidence and acute PV damage. No trading."""
import math
import numpy as np
import pandas as pd

LABELS={-2:'freeze',-1:'cold',0:'neutral',1:'warm',2:'hot'}
FIELDS=['sigma','activity','shock','effective_shock','speed_21','speed_63','z_21','z_63',
        'amplitude_21','amplitude_63','return_21','return_63','local','background',
        'normal_grade','grade','freeze_active','freeze_created','freeze_released',
        'freeze_count','freeze_id','freeze_age','freeze_anchor','freeze_low','rapid_up']

def tol(a,b):return 32*np.finfo(float).eps*max(1.,abs(a),abs(b))
def ge(a,b):return bool(a>=b-tol(a,b))
def le(a,b):return bool(a<=b+tol(a,b))
def direction(z,prior):
    if ge(z,1.):return 1
    if le(z,-1.):return -1
    if prior==1 and not le(z,.5):return 1
    if prior==-1 and not ge(z,-.5):return -1
    return 0

def normal_grade(B,L):
    if L==-1:return -1,'local_decline'
    if L==0:return (B,{-1:'down_background_pause',0:'no_clear_progress',1:'up_background_pause'}[B])
    if B==-1:return 0,'down_background_rebound'
    if B==0:return 1,'up_building'
    return 2,'aligned_up'

def run_valid(f,joint=True):
    p=np.log(f.close.to_numpy(float)/float(f.close.iloc[0]));r=np.r_[np.nan,np.diff(p)]
    v=f.volume.to_numpy(float);rows=[];events=[];B=L=0;active=[];seq=0
    def emit(t,kind,**kw):events.append(dict(observation=int(t),date=str(f.index[t].date()),kind=kind,**kw))
    for t in range(len(f)):
        row={k:math.nan for k in FIELDS};row['phase']='unknown'
        if t<64:rows.append(row);continue
        sig=max(float(np.sqrt(np.mean(r[t-63:t]**2))),1e-8)
        a=float(v[t]/np.median(v[t-21:t]));q=float(r[t]/sig)
        eq=q*math.sqrt(float(np.clip(a,1.,4.)) if joint else 1.)
        row.update(sigma=sig,activity=a,shock=q,effective_shock=eq,rapid_up=float(ge(eq,2.)))
        for h in (21,63):
            x=np.arange(h+1,dtype=float)-h/2
            y=p[t-h:t+1];beta=float(x@(y-y.mean())/(x@x))
            row['speed_'+str(h)]=beta;row['z_'+str(h)]=math.sqrt(h)*beta/sig
            row['amplitude_'+str(h)]=100*h*beta
            row['return_'+str(h)]=100*math.expm1(float(p[t]-p[t-h]))
        B=direction(row['z_63'],B);L=direction(row['z_21'],L)
        g,phase=normal_grade(B,L);row.update(background=float(B),local=float(L),normal_grade=float(g),
            grade=float(g),phase=phase,freeze_active=0.,freeze_created=0.,freeze_released=0.,freeze_id=0.)
        keep=[]
        for event in active:
            event['low']=min(event['low'],float(p[t]));reason=None
            if ge(float(p[t]),event['anchor']):reason='price_recovered'
            elif L==-1:reason='downtrend_takeover'
            elif t-event['birth']>=21:reason='outside_current_scale'
            if reason is not None:
                emit(t,reason,event=event['id'],birth=event['birth'],low=event['low'],anchor=event['anchor'],close=float(p[t]),age=t-event['birth'],
                     price_recovered=ge(float(p[t]),event['anchor']))
                row['freeze_released']+=1.
            else:keep.append(event)
        active=keep
        if le(eq,-2.):
            seq+=1;event=dict(id=seq,birth=t,anchor=float(p[t-1]),low=float(p[t]));active.append(event)
            row['freeze_created']=1.
            emit(t,'freeze_created',event=seq,anchor=event['anchor'],close=float(p[t]),shock=q,activity=a,effective_shock=eq)
        row['freeze_count']=float(len(active))
        if active:
            row.update(grade=-2.,phase='acute_damage',freeze_active=1.,freeze_id=float(active[-1]['id']),
                freeze_age=float(t-min(e['birth'] for e in active)),freeze_anchor=max(e['anchor'] for e in active),
                freeze_low=min(e['low'] for e in active))
        rows.append(row)
    z=pd.DataFrame(rows,index=f.index)
    z['freeze_anchor_price']=float(f.close.iloc[0])*np.exp(z.freeze_anchor)
    z['freeze_low_price']=float(f.close.iloc[0])*np.exp(z.freeze_low)
    z.attrs['terminal']=active
    return z,events

def strength_frame(f,joint=True):
    if not isinstance(f.index,pd.DatetimeIndex) or f.index.tz is not None:
        raise ValueError('Naive DatetimeIndex required')
    if not f.index.is_unique or not f.index.is_monotonic_increasing or f.index.hasnans:
        raise ValueError('Ordered unique dated observations required')
    if f.segment_id.isna().any():raise ValueError('Explicit source segment required')
    blocks=f.segment_id.loc[f.segment_id.ne(f.segment_id.shift())]
    if blocks.duplicated().any():raise ValueError('Noncontiguous segment identity')
    if not pd.api.types.is_bool_dtype(f.valid_strength_observation) or f.valid_strength_observation.isna().any():
        raise ValueError('Non-null Boolean validity required')
    columns=FIELDS+['freeze_anchor_price','freeze_low_price']
    out=pd.DataFrame(np.nan,index=f.index,columns=columns);out['phase']='unknown'
    journal=[];terminal=None;previous=None
    for segment,g in f.groupby('segment_id',sort=False):
        if terminal:journal.append(dict(segment=str(segment),date=str(g.index[0].date()),observation=None,
            kind='source_discontinuity',previous_segment=previous,unresolved=terminal))
        good=g.loc[g.valid_strength_observation]
        if len(good):
            a=good[['close','volume']].to_numpy(float)
            if not np.isfinite(a).all() or not (a>0).all():raise ValueError('Finite positive valid price/volume required')
            z,j=run_valid(good,joint);out.loc[good.index,z.columns]=z
            journal.extend(dict(segment=str(segment),**e) for e in j);terminal=z.attrs['terminal']
        else:terminal=None
        previous=str(segment)
    return out,journal
