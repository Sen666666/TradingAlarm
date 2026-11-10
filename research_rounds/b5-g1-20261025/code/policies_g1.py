"""Three explicit consumers of saved market evidence; no account inputs."""
import math
import numpy as np
import pandas as pd

def project(e,base,g,kind):
    if kind not in ['G1_I','G1_X','G1_IX']:raise ValueError(kind)
    use_i=kind in ['G1_I','G1_IX'];use_x=kind in ['G1_X','G1_IX']
    active=False;floor=math.nan;segment=None;rows=[]
    for dt,r in e.iterrows():
        b=base.loc[dt];a=g.loc[dt]
        if r.segment_id!=segment:active=False;floor=math.nan;segment=r.segment_id
        valid=bool(r.valid_price_observation)
        if not valid:
            rows.append(dict(date=dt,target=np.nan,entered=0,exited=0,floor=np.nan,exit_line=np.nan,buy_event=False,entry_kind='',exit_reason='',grade=a.grade));continue
        shadow=bool(b.target);ready=bool(a.ready);entered=exited=0;reason='';entry_kind=''
        fresh=bool(a.fresh_up) if ready else False
        warm=ready and a.grade>=2
        cold=ready and (a.grade<=-2 or bool(a.acute_down))
        if active:
            if not shadow or float(r.close)<=floor:reason='E0_structure_boundary'
            elif use_x and cold:reason='G1_cold_or_acute'
            if reason:active=False;exited=1
            elif np.isfinite(b.floor):floor=max(floor,float(b.floor))
        # Entry-only is a new-evidence gate and restoration channel, while
        # exit-only preserves E0's new-cycle entry stream. An exit-only entry
        # is first checked by the extra exit rule on the next observation,
        # matching the original sensitive-policy ordering.
        opportunity=shadow and warm and (bool(b.entered) or fresh) if use_i else bool(b.entered)
        if not active and not exited and opportunity:
            active=True;entered=1;floor=float(b.floor)
            entry_kind='G1_fresh_warm_evidence' if use_i else str(b.entry_kind)
        buy=bool(active and opportunity) if use_i else bool(active)
        rows.append(dict(date=dt,target=int(active),entered=entered,exited=exited,floor=floor if active or exited else np.nan,exit_line=floor if active or exited else np.nan,buy_event=buy,entry_kind=entry_kind,exit_reason=reason,grade=a.grade))
    return pd.DataFrame(rows).set_index('date')

def e0_adapter(s):
    x=s.copy();x['exit_line']=x.floor;x['exit_reason']=np.where(x.exited.eq(1),'structure','');return x

def initial(d,s,g,start,kind):
    n=d.index.get_loc(d.loc[start:].index[0]);assert n>0
    r=s.iloc[n-1];active=bool(r.target)
    if kind in ['G1_I','G1_IX']:
        active=active and bool(g.ready.iloc[n-1]) and g.grade.iloc[n-1]>=2
    return dict(active=bool(active),floor=float(r.floor) if active else None,previous_close=float(d.close.iloc[n-1]))
