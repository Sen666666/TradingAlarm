"""PVS-B2: observed pace, retained directional structure, unrecovered PV zones.
No composite score, forecast, account, position or trade policy.
"""
import math
import numpy as np
import pandas as pd

FIELDS = ['speed_5','speed_21','pace_5','pace_21','amplitude_5','amplitude_21','return_5_log_pct','return_21_log_pct',
          'sigma','activity','shock','opposition','adverse_pre_sigma','pre_direction','pre_episode',
          'direction','episode','retention','signed_retention','span_log_pct','episode_age',
          'progress_age','support_advances','origin','extreme','support','checkpoint',
          'old_retention_at_t','old_support','structure_broken','structure_created','pivot_confirmed',
          'down_zone_log_pct','up_zone_log_pct','down_zone_sigma','up_zone_sigma',
          'down_events','up_events','down_union_parts','up_union_parts','oldest_down_age','oldest_up_age',
          'impulse_created','init']

def comparison_tolerance(a,b):
    return 32*np.finfo(float).eps*max(1.,abs(a),abs(b))

def inclusive_ge(a,b):
    return a>=b-comparison_tolerance(a,b)

def union_length(intervals):
    """Defensive union; event identity stays separate in the ledger."""
    z = sorted((float(a),float(b)) for a,b in intervals if b>a)
    merged = []
    for a,b in z:
        if merged and a <= merged[-1][1]: merged[-1][1] = max(merged[-1][1],b)
        else: merged.append([a,b])
    return sum(b-a for a,b in merged),len(merged)

class Structure:
    def __init__(self,p,t,sigma,emit):
        self.d=0; self.seq=0; self.episode=0; self.emit=emit
        self.low=self.high=p; self.low_t=self.high_t=t
        self.low_delta=self.high_delta=2*sigma
        self.A=self.E=self.S=self.K=self.pivot=math.nan
        self.A_t=self.E_t=self.born=self.last_progress=self.pivot_t=t
        self.delta,self.e_sigma=2*sigma,sigma
        self.advances=0

    def begin(self,d,A,A_t,p,t,sigma):
        assert d*(p-A)>0
        self.seq+=1; self.episode=self.seq; self.d=d
        self.A=self.S=A; self.A_t=A_t; self.E=p; self.E_t=t
        self.delta=2*sigma; self.e_sigma=sigma
        self.born=self.last_progress=t; self.advances=0
        self.K=self.pivot=math.nan
        self.emit(t,'structure_created',dict(direction=d,episode=self.episode,origin=A,
            origin_observation=A_t,extreme=p,support=A,delta=self.delta))

    def unknown(self,p,t,sigma,old_E=None,old_E_t=None,old_delta=None):
        self.d=0; self.episode=0; self.K=self.pivot=math.nan
        self.low=self.high=p; self.low_t=self.high_t=t
        self.low_delta=self.high_delta=2*sigma
        if old_E is not None:
            if old_E>p: self.high,self.high_t,self.high_delta=old_E,old_E_t,old_delta
            elif old_E<p: self.low,self.low_t,self.low_delta=old_E,old_E_t,old_delta

    def update(self,p,t,sigma,r):
        info=dict(structure_broken=0.,structure_created=0.,pivot_confirmed=0.,
                  old_retention_at_t=math.nan,old_support=math.nan)
        prior_d,prior_episode=self.d,self.episode
        info['pre_direction']=float(prior_d);info['pre_episode']=float(prior_episode)
        info['adverse_pre_sigma']=max(0.,-prior_d*(p-self.E))/self.e_sigma if prior_d else math.nan
        if self.d and self.d*(p-self.S)<=0:
            d,A,E,S,et,delta=self.d,self.A,self.E,self.S,self.E_t,self.delta
            old_R=d*(p-A)/(d*(E-A))
            info.update(structure_broken=1.,old_retention_at_t=old_R,old_support=S)
            self.emit(t,'structure_broken',dict(direction=d,episode=self.episode,old_origin=A,
                old_extreme=E,old_support=S,close=p,old_retention_at_t=old_R))
            self.unknown(p,t,sigma,E,et,delta)
            # Actual independently-sized reversal is required, in addition to old support failure.
            if inclusive_ge(-d*(p-E),delta):
                self.begin(-d,E,et,p,t,sigma);info['structure_created']=1.
        elif self.d:
            d=self.d
            if math.isfinite(self.K):
                if d*p<d*self.pivot: self.pivot,self.pivot_t=p,t
                if d*(p-self.K)>=0:
                    q,qt=self.pivot,self.pivot_t
                    self.emit(t,'pivot_confirmed',dict(direction=d,episode=self.episode,
                        pivot=q,pivot_observation=qt,checkpoint=self.K,support_before=self.S))
                    info['pivot_confirmed']=1.
                    if d*(q-self.S)>0:
                        self.S=q;self.advances+=1;self.last_progress=t
                    self.K=self.pivot=math.nan
            if d*(p-self.E)>0:
                self.E,self.E_t=p,t;self.delta,self.e_sigma=2*sigma,sigma;self.last_progress=t
            if not math.isfinite(self.K) and inclusive_ge(-d*(p-self.E),self.delta):
                self.K,self.pivot,self.pivot_t=self.E,p,t
                self.emit(t,'checkpoint_created',dict(direction=d,episode=self.episode,
                    checkpoint=self.K,extreme_observation=self.E_t,delta=self.delta))
        else:
            if p<self.low: self.low,self.low_t,self.low_delta=p,t,2*sigma
            if p>self.high: self.high,self.high_t,self.high_delta=p,t,2*sigma
            up_distance=p-self.low;down_distance=self.high-p
            up_ok=inclusive_ge(up_distance,self.low_delta);down_ok=inclusive_ge(down_distance,self.high_delta)
            up=up_distance/self.low_delta;down=down_distance/self.high_delta
            if up_ok and down_ok:
                tie=abs(up-down)<=comparison_tolerance(up,down)
                d=(1 if r>0 else -1 if r<0 else 0) if tie else (1 if up>down else -1)
            else:d=1 if up_ok else -1 if down_ok else 0
            if d:
                self.begin(d,self.low if d==1 else self.high,self.low_t if d==1 else self.high_t,p,t,sigma)
                info['structure_created']=1.
        if self.d:
            span=self.d*(self.E-self.A);ret=self.d*(p-self.A)/span
            assert span>0 and -1e-12<ret<=1+1e-12
            info.update(direction=float(self.d),episode=float(self.episode),retention=ret,
                signed_retention=100*self.d*ret,span_log_pct=100*span,
                episode_age=float(t-self.born),progress_age=float(t-self.last_progress),
                support_advances=float(self.advances),origin=self.A,extreme=self.E,support=self.S,
                checkpoint=self.K)
        else:
            info.update(direction=0.,episode=0.)
        return info

class Ledger:
    def __init__(self,emit): self.live=[];self.seq=0;self.emit=emit
    def update(self,p,prev,t,sigma,a,episode,joint=True):
        keep=[]
        for e in self.live:
            before=(e['lo'],e['hi'])
            if e['direction']==-1: e['lo']=max(e['lo'],p)
            else: e['hi']=min(e['hi'],p)
            changed=before!=(e['lo'],e['hi'])
            closed=e['lo']>=e['hi']
            if changed:
                self.emit(t,'impulse_closed' if closed else 'impulse_partly_recovered',
                    dict(event=e['event'],direction=e['direction'],birth_observation=e['birth'],
                         birth_episode=e['birth_episode'],before=list(before),after=[e['lo'],e['hi']]))
            if not closed: keep.append(e)
        self.live=keep;created=0.
        r=p-prev
        if inclusive_ge(abs(r),sigma) and (inclusive_ge(a,2.) or not joint):
            self.seq+=1;d=1 if r>0 else -1
            e=dict(event=self.seq,direction=d,lo=min(prev,p),hi=max(prev,p),birth=t,
                   birth_episode=episode,original_lo=min(prev,p),original_hi=max(prev,p),birth_sigma=sigma,birth_activity=a)
            self.live.append(e);created=float(d);self.emit(t,'impulse_created',dict(e))
        info=dict(impulse_created=created)
        for d,name in [(-1,'down'),(1,'up')]:
            events=[e for e in self.live if e['direction']==d]
            length,parts=union_length([(e['lo'],e['hi']) for e in events])
            # Legal living regions are ordered around the current close, not overlapping evidence votes.
            assert all((e['lo']>=p-1e-12 if d==-1 else e['hi']<=p+1e-12) for e in events)
            assert abs(sum(e['hi']-e['lo'] for e in events)-length)<1e-9
            info[name+'_zone_log_pct']=100*length;info[name+'_zone_sigma']=length/sigma
            info[name+'_events']=float(len(events));info[name+'_union_parts']=float(parts)
            info['oldest_'+name+'_age']=float(t-min(e['birth'] for e in events)) if events else math.nan
        return info

def run_valid(f,joint=True):
    n=len(f);p=np.log(f.close.to_numpy(float)/float(f.close.iloc[0]));v=f.volume.to_numpy(float)
    r=np.r_[np.nan,np.diff(p)];out=[];journal=[];structure=ledger=None
    def emit(t,kind,fields): journal.append(dict(observation=int(t),date=str(f.index[t].date()),kind=kind,**fields))
    for t in range(n):
        z={k:math.nan for k in FIELDS}
        if t>=64:
            sigma=max(float(np.sqrt(np.mean(r[t-63:t]**2))),1e-8)
            a=float(v[t]/np.median(v[t-21:t]));shock=float(r[t]/sigma)
            z.update(sigma=sigma,activity=a,shock=shock,init=float(t==64))
            for h in [5,21]:
                x=np.arange(h+1,dtype=float)-h/2
                beta=float(x@p[t-h:t+1]/(x@x))
                z['speed_'+str(h)]=beta
                z['pace_'+str(h)]=math.sqrt(h)*beta/sigma
                z['amplitude_'+str(h)]=100*h*beta
                z['return_'+str(h)+'_log_pct']=100*(p[t]-p[t-h])
            if structure is None:
                structure=Structure(float(p[t]),t,sigma,emit);ledger=Ledger(emit)
                info=dict(direction=0.,episode=0.,pre_direction=0.,pre_episode=0.,structure_broken=0.,structure_created=0.,pivot_confirmed=0.)
            else: info=structure.update(float(p[t]),t,sigma,float(r[t]))
            z.update(info);z['opposition']=max(0.,-z['pre_direction']*shock) if z['pre_direction'] else math.nan
            z.update(ledger.update(float(p[t]),float(p[t-1]),t,sigma,a,int(z['episode']),joint))
        out.append(z)
    result=pd.DataFrame(out,index=f.index,columns=FIELDS)
    # Log geometry is used internally. Plot coordinates use the original study-price units.
    for c in ['origin','extreme','support','checkpoint','old_support']:
        result[c+'_price']=float(f.close.iloc[0])*np.exp(result[c])
    result.attrs['terminal_unresolved']=dict(
        direction=structure.d if structure else None,episode=structure.episode if structure else None,
        origin=structure.A if structure and structure.d else None,
        support=structure.S if structure and structure.d else None,
        live_impulses=[dict(e) for e in ledger.live] if ledger else [])
    return result,journal

def three_axis_frame(f,joint=True):
    if not f.index.is_unique or not f.index.is_monotonic_increasing or f.segment_id.isna().any():
        raise ValueError('Ordered unique observations and explicit source segments required')
    blocks=f.segment_id.loc[f.segment_id.ne(f.segment_id.shift())]
    if blocks.duplicated().any():
        raise ValueError('A source segment identity cannot reappear after another segment')
    cols=FIELDS+[c+'_price' for c in ['origin','extreme','support','checkpoint','old_support']]
    result=pd.DataFrame(np.nan,index=f.index,columns=cols);journal=[];prior_segment=None;prior_terminal=None
    for segment,g in f.groupby('segment_id',sort=False):
        if prior_terminal is not None:
            journal.append(dict(segment=str(segment),date=str(g.index[0].date()),observation=None,
                kind='source_segment_start_unresolved_archive',previous_segment=prior_segment,
                prior_terminal=prior_terminal,meaning='Source discontinuity; not price recovery or healed evidence'))
        good=g.loc[g.valid_strength_observation]
        if len(good):
            if not (np.isfinite(good[['close','volume']].to_numpy(float)).all() and
                    (good[['close','volume']].to_numpy(float)>0).all()):
                raise ValueError('Valid observations require finite positive close and volume')
            z,j=run_valid(good,joint);result.loc[good.index,z.columns]=z
            journal.extend(dict(segment=str(segment),**e) for e in j)
            prior_terminal=z.attrs['terminal_unresolved']
        else: prior_terminal=None
        prior_segment=str(segment)
    return result,journal
