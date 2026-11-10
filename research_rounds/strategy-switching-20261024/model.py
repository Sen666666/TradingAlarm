"""Finite causal policies; no case labels, future trades or fitted weights."""
import math
import numpy as np
import pandas as pd
from legacy import compare, higher
from fitted import simulate

POLICIES=['E0','E2','F','C2','R','RC','RF','G']
CFG=dict(id='slope-20-PV-e1-x0-trail2-broken_peak',family='slope',n=20,
         volume='PV',entry=1.,exit=0.,danger='trail2',memory='broken_peak')

def fitted_state(d, f):
    s=simulate(d,CFG,f)
    s['exit_line']=s.floor
    s['entry_kind']=np.where(s.entered,'fitted_new_evidence','')
    s['exit_reason']=np.where(s.exited,s.reason,'')
    return s

def chan_state(d, ch):
    active=False;floor=math.nan;rows=[]
    for dt,bar in d.iterrows():
        x=ch.loc[dt];entered=exited=0;reason=''
        # Known support is tested before today's newly confirmed stroke.
        if active and (bar.low<floor or x.new_sell):
            active=False;exited=1;reason='chan_support' if bar.low<floor else 'chan_sell'
        if x.B2 and not exited:
            if active:floor=max(floor,float(x.bi_low))
            else:active=True;entered=1;floor=float(x.bi_low)
        rows.append(dict(date=dt,target=int(active),entered=entered,exited=exited,
                         floor=floor if active or exited else math.nan,
                         exit_line=floor if active or exited else math.nan,
                         entry_kind='confirmed_B2' if entered else '',exit_reason=reason))
    return pd.DataFrame(rows).set_index('date')

def own_initial(d,s,start):
    first=d.index.get_loc(d.loc[start:].index[0]);p=s.iloc[first-1]
    return dict(active=bool(p.target),floor=float(p.floor),previous_close=float(d.close.iloc[first-1]))

def combined(d,base,f,ch,fs,start,end,policy):
    """R: one participation per shadow E0 cycle; C/F can authorize retries.
    G: same cycle rule, E0 exit while 63-day PV drift>0, E2 otherwise.
    All R-family accounts inherit the same preceding E0 state at window start.
    """
    assert policy in ['R','RC','RF','G']
    z=d.loc[start:end];i=d.index.get_loc(z.index[0]);prior=base.iloc[i-1]
    active=bool(prior.target);floor=float(prior.floor) if active else math.nan
    previous=float(d.close.iloc[i-1]);peak=math.log(previous) if active else math.nan
    stop=peak-2*float(f.atr.iloc[i-1]) if active else -math.inf
    initial=dict(active=active,floor=floor,previous_close=previous);rows=[]
    for dt,bar in z.iterrows():
        b=base.loc[dt];price=float(bar.close);lc=math.log(price)
        entered=exited=0;reason='';kind=''
        background=bool(f.loc[dt,'drift_63_PV']>0)
        sensitive=policy!='G' or not background
        if active:
            if b.target:floor=higher(floor,float(b.floor))
            peak=max(peak,lc);stop=max(stop,peak-2*float(f.loc[dt,'atr']))
            structural=not bool(b.target) or compare(price,floor)<=0
            if structural or (sensitive and lc<=stop):
                active=False;exited=1;reason='structure' if structural else 'atr2'
        if not active and not exited and b.target:
            fresh=bool(b.entered)
            retry=(policy=='RC' and bool(ch.loc[dt,'B2'])) or (policy=='RF' and bool(fs.loc[dt,'entered']))
            if fresh or retry:
                active=True;entered=1;floor=float(b.floor);peak=lc
                stop=peak-2*float(f.loc[dt,'atr'])
                kind='E0_new_cycle' if fresh else ('confirmed_B2_retry' if policy=='RC' else 'fitted_restart_retry')
        rows.append(dict(date=dt,target=int(active),entered=entered,exited=exited,
                         floor=floor if active or exited else math.nan,
                         exit_line=max(floor,math.exp(stop)) if (active or exited) and sensitive else floor,
                         entry_kind=kind,exit_reason=reason,background_positive=int(background),
                         sensitive_exit=int(sensitive),shadow_target=int(b.target)))
    return pd.DataFrame(rows).set_index('date'),initial
