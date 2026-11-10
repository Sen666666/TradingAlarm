"""Same frozen entry evidence, four exit policies and matched-entry control."""
from pathlib import Path
import sys,math
import numpy as np,pandas as pd
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'research_rounds/pv-participation-response-20261020/code'))
from numeric import event_frame_numeric,compare,higher
from participation import participation_frame
POLICIES=['E0','E2','E3','ED']
WINDOWS={'primary':('2025-01-02','2026-10-13'),'history2024':('2024-01-02','2024-12-31')}

def context(d):
    e=event_frame_numeric(d.close,d.volume);b,_=participation_frame(d,e,mode='volume')
    tr=pd.concat([(d.high-d.low)/d.close.shift(),(d.high/d.close.shift()-1).abs(),(d.low/d.close.shift()-1).abs()],axis=1).max(axis=1)
    f=pd.DataFrame({'atr':tr.shift().rolling(14).mean(),'q':d.volume/d.volume.shift().rolling(21).median()},index=d.index)
    return e,b,f

def state(d,e,base,f,start,end,policy='E0',mode='P'):
    z=d.loc[start:end];first=d.index.get_loc(z.index[0]);assert first>64
    prior=base.iloc[first-1];active=bool(prior.target);floor=float(prior.floor) if active else math.nan
    pending=dict(lower=float(prior.pending_lower),reclaim=float(prior.pending_reclaim)) if prior.pending else None
    prev=float(d.close.iloc[first-1]);peak=math.log(prev) if active else math.nan
    stop=peak-int(policy[1:])*float(f.atr.iloc[first-1]) if active and policy in ['E2','E3'] else -math.inf
    initial=dict(active=active,floor=floor,previous_close=prev);rows=[]
    for dt,bar in z.iterrows():
        ev=e.loc[dt];c=float(bar.close);lc=math.log(c);event=int(ev.event);entered=exited=0;reason='';kind='';response=0
        if active:
            peak=max(peak,lc)
            if mode=='M' and math.isfinite(float(base.loc[dt,'floor'])):floor=higher(floor,float(base.loc[dt,'floor']))
            if policy in ['E2','E3']:stop=max(stop,peak-int(policy[1:])*float(f.loc[dt,'atr']))
            structural=compare(c,floor)<=0 or (mode=='M' and not bool(base.loc[dt,'target']))
            extra=(policy in ['E2','E3'] and lc<=stop) or (policy=='ED' and event==-1)
            if structural or extra:active=False;exited=1;reason='structure' if structural else ('down_event' if policy=='ED' else 'atr'+policy[1:])
        if mode=='M':
            if not active and not exited and bool(base.loc[dt,'entered']):
                active=True;entered=1;floor=float(base.loc[dt,'floor']);kind=str(base.loc[dt,'entry_kind'])
            pending=None
        else:
            if pending:
                if compare(c,pending['lower'])<0:response=-1
                elif compare(c,pending['reclaim'])>0:response=1
            if event==1:
                pivot=float(ev.confirmed_pivot_price)
                if active:floor=higher(floor,pivot)
                elif not exited:active=True;entered=1;floor=pivot;kind='original_event'
            if pending:
                if response==-1 or active:pending=None
                elif response==1:
                    assert not exited
                    active=True;entered=1;floor=pending['lower'];kind='participation_reclaim';pending=None
            if not active and pending is None and pd.notna(ev.leg_direction) and compare(c,prev)<0 and compare(float(f.loc[dt,'q']),2.)>=0:
                pending=dict(reclaim=prev,lower=float(bar.low))
        if entered:
            peak=lc;stop=peak-int(policy[1:])*float(f.loc[dt,'atr']) if policy in ['E2','E3'] else -math.inf
        line=max(floor,math.exp(stop)) if active and math.isfinite(stop) else floor
        rows.append(dict(date=dt,target=int(active),entered=entered,exited=exited,floor=floor if active or exited else np.nan,exit_line=line if active or exited else np.nan,
            pending=int(pending is not None),pending_lower=pending['lower'] if pending else np.nan,pending_reclaim=pending['reclaim'] if pending else np.nan,entry_kind=kind,exit_reason=reason,event=event))
        prev=c
    result=pd.DataFrame(rows).set_index('date')
    if policy=='E0':
        for col in ['target','entered','exited','floor','pending','pending_lower','pending_reclaim']:
            np.testing.assert_allclose(result[col],base.loc[z.index,col].astype(float),rtol=0,atol=0,equal_nan=True)
    if mode=='M':
        assert not (result.entered.astype(bool)&~base.loc[z.index,'entered'].astype(bool)).any()
        assert not (result.target.astype(bool)&~base.loc[z.index,'target'].astype(bool)).any()
    return result,initial
