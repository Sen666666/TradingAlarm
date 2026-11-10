"""R1-IR-20261024. One new qualification; original R exits unchanged."""
from pathlib import Path
import sys,math
import numpy as np,pandas as pd
P=Path(__file__).resolve().parent.parent/'strategy-switching-20261024'
sys.path.append(str(P))
from legacy import compare,higher

def r1_state(d,e,base,f,start,end,enable_recovery=True):
    z=d.loc[start:end];i=d.index.get_loc(z.index[0]);prior=base.iloc[i-1]
    active=bool(prior.target);floor=float(prior.floor) if active else math.nan
    previous=float(d.close.iloc[i-1]);peak=math.log(previous) if active else math.nan
    stop=peak-2*float(f.atr.iloc[i-1]) if active else -math.inf
    initial=dict(active=active,floor=floor,previous_close=previous)
    memory=None;rows=[];cycle=0;attempt=0
    for dt,bar in z.iterrows():
        b=base.loc[dt];ev=e.loc[dt];price=float(bar.close);lc=math.log(price)
        entered=exited=resume=0;reason=kind=rejection='';used=None
        if bool(b.entered):cycle+=1
        if active:
            if b.target:floor=higher(floor,float(b.floor))
            peak=max(peak,lc);stop=max(stop,peak-2*float(f.loc[dt,'atr']))
            structural=not bool(b.target) or compare(price,floor)<=0
            if structural or lc<=stop:
                active=False;exited=1;reason='structure' if structural else 'atr2'
                memory=dict(date=dt,floor=float(b.floor)) if enable_recovery and not structural and b.target else None
        if not b.target:memory=None
        if not active and not exited and b.target:
            fresh=bool(b.entered);recover=False
            if fresh:memory=None
            elif enable_recovery and memory is not None and int(ev.event)==1:
                pivot_dt=pd.Timestamp(ev.confirmed_pivot_date);pivot=float(ev.confirmed_pivot_price)
                assert pivot_dt<dt, 'confirmed pivot must precede recognition'
                if pivot_dt<=memory['date']:rejection='trough_not_after_exit_signal'
                elif compare(pivot,memory['floor'])<=0:rejection='trough_not_higher_than_exit_support'
                else:recover=True;used=memory.copy()
            if fresh or recover:
                active=True;entered=1;resume=int(recover);attempt+=1
                floor=float(b.floor);peak=lc;stop=peak-2*float(f.loc[dt,'atr'])
                kind='E0_new_cycle' if fresh else 'higher_trough_reentry';memory=None
        anchor=used if used is not None else memory
        rows.append(dict(date=dt,target=int(active),entered=entered,exited=exited,
            floor=floor if active or exited else math.nan,
            exit_line=max(floor,math.exp(stop)) if active or exited else floor,
            entry_kind=kind,exit_reason=reason,event=int(ev.event),shadow_target=int(b.target),
            recovery_entry=resume,recovery_armed=int(memory is not None),
            recovery_exit_signal=str(anchor['date'].date()) if anchor else '',
            recovery_anchor_floor=anchor['floor'] if anchor else math.nan,
            confirmed_pivot_date=str(ev.confirmed_pivot_date) if int(ev.event)==1 else '',
            confirmed_pivot_price=float(ev.confirmed_pivot_price) if int(ev.event)==1 else math.nan,
            confirmation=float(ev.confirmation) if pd.notna(ev.confirmation) else math.nan,
            recovery_rejection=rejection,cycle_id=cycle,attempt_id=attempt))
    return pd.DataFrame(rows).set_index('date'),initial
