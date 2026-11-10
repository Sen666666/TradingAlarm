"""Frozen negative CUSUM observation only. No account, order, or CP reset."""
import math
from collections import deque
from statistics import median
import numpy as np
import pandas as pd

SCALE_WINDOW=63
MAD_FACTOR=1.4826
SCALE_GUARD=1e-8
DRIFT=.25
LEVEL=3.

def finite(x):
    try:return x is not None and x is not pd.NA and math.isfinite(float(x))
    except (TypeError,ValueError):return False
def bit(x):return int(x) if finite(x) and float(x) in (0.,1.) else None
def source(x):
    if x is None or x is pd.NA:return None
    if isinstance(x,str):return x if x else None
    return str(int(x)) if finite(x) and float(x).is_integer() else str(x) if finite(x) else None

def calculate(sid,price,feature_frame,native):
    """Entire source prefix; r scale excludes current r, no skip over invalid rows.

    close_valid is the immutable engine's strict flags + source + positive C mask;
    high/low are not needed to observe a log close return. Initial I=1 is censored.
    Unknown within an evidenced active I cycle permanently poisons that cycle's D.
    """
    n=native.reindex(price.index);f=feature_frame
    a={k:price[k].to_numpy() for k in ['close','raw_close']}
    I=n.i_target.to_numpy();ns=n.segment_id.to_numpy();ss=f.source_key.to_numpy()
    cv=f.close_valid.to_numpy();hist=deque(maxlen=SCALE_WINDOW)
    previous_C=None;scale_source=None;last_observed_source=None;prev_I=None;prev_native_source=None
    cycle=None;ordinal=0;source_confirmation_pending=False;rows=[]
    for j,t in enumerate(price.index):
        day=str(t.date());seg=source(ss[j]);native_source=source(ns[j]);raw_i=bit(I[j])
        valid=bool(cv[j]) and seg is not None and finite(a['close'][j]) and float(a['close'][j])>0
        C=float(a['close'][j]) if valid else None
        changed=seg is not None and last_observed_source is not None and seg!=last_observed_source
        if changed:source_confirmation_pending=True
        if seg is not None:last_observed_source=seg
        if seg!=scale_source or not valid:
            hist.clear();previous_C=None;scale_source=seg
        r=None if previous_C is None or not valid else math.log(C/previous_C)
        count=len(hist);s=MAD_FACTOR*median(hist) if r is not None and count==SCALE_WINDOW else None
        scale_status='READY' if s is not None and s>SCALE_GUARD else 'LOW_SCALE_GUARD' if s is not None else 'UNREADY_OR_INVALID'
        # Native truth is comparable only with both same-day source identities known.
        current_I=raw_i if seg is not None and native_source==seg else None
        prior_D=None if cycle is None else cycle['D'];old_cycle_id=None if cycle is None else cycle['id']
        end_reason=None;start_reason=None;ended=None;event=None
        if cycle is not None and seg!=cycle['source']:
            ended=cycle['id'];end_reason='SOURCE_INCOMPARABLE';cycle=None
        start=bool(current_I==1 and valid and ((prev_I==0 and prev_native_source==seg) or (source_confirmation_pending and cycle is None)))
        if start:
            ordinal+=1;start_reason='NEW_SOURCE_CONFIRMED_I_ON' if source_confirmation_pending else 'NATIVE_I_ZERO_TO_ONE'
            cycle=dict(id=f'{sid}|{seg}|{day}|{ordinal}',source=seg,start=day,D=0.,unknown=False,crossed=False,left=False)
            source_confirmation_pending=False;event='I_CYCLE_START_D0'
        elif cycle is None and current_I==1:
            # No preceding observed zero/new-source evidence: do not invent D0.
            cycle=dict(id=f'{sid}|{seg}|LEFT_CENSORED|{day}',source=seg,start=None,D=None,unknown=True,crossed=False,left=True)
            event='LEFT_CENSORED_I_ON'
        D_before=None if cycle is None else cycle['D'];unknown_reason=None
        level=None;cross=False;first_cross=False;step=None
        active_for_close=cycle is not None and (current_I in (0,1) or current_I is None)
        if active_for_close:
            if start:D=0.
            elif cycle['unknown']:
                D=None;unknown_reason='LEFT_CENSORED_I_CYCLE' if cycle['left'] else 'PRIOR_CYCLE_INPUT_UNKNOWN'
            elif current_I is None or not valid or r is None or scale_status!='READY':
                D=None;cycle['unknown']=True
                unknown_reason='UNKNOWN_CURRENT_I_OR_SOURCE' if current_I is None else 'INVALID_CURRENT_RETURN' if not valid or r is None else scale_status
            else:
                step=-r/s-DRIFT;D=max(0.,cycle['D']+step)
            cycle['D']=D
            if D is not None:
                level=D>=LEVEL;cross=bool(level and D_before is not None and D_before<LEVEL)
                first_cross=bool(cross and not cycle['crossed'])
                if cross:cycle['crossed']=True
            if current_I==0:
                ended=cycle['id'];end_reason='NATIVE_I_ONE_TO_ZERO';event='I_CYCLE_END_CLOSE_INCLUDED'
        # An ending close may be observed for comparison, but is not an active warning.
        warning=bool(current_I==1 and level is True)
        rows.append(dict(sid=sid,day=day,source_key=seg,native_segment=native_source,C=C,raw_C=a['raw_close'][j],
            close_valid=valid,native_i_target=current_I,original_native_i_target=raw_i,source_changed=changed,
            r=r,prior_abs_return_count=count,s63=s,scale_status=scale_status,
            cycle_id=None if cycle is None else cycle['id'],cycle_start_day=None if cycle is None else cycle['start'],
            cycle_left_censored=False if cycle is None else cycle['left'],cycle_event=event,start_reason=start_reason,
            cycle_ended_id=ended,cycle_end_reason=end_reason,D_before=D_before,standardized_negative_step=step,D=D if active_for_close else None,
            D_status='INACTIVE' if cycle is None else 'UNKNOWN' if cycle['D'] is None else 'KNOWN',
            unknown_reason=unknown_reason,level_ge3=level,threshold_cross=cross,first_threshold_cross_in_cycle=first_cross,
            active_level_warning=warning,active_cross_warning=bool(current_I==1 and cross),
            old_cycle_before=old_cycle_id,CP_resets_D=False,price_only_observation_not_order=True))
        if cycle is not None and current_I==0:cycle=None
        if valid and r is not None:hist.append(abs(r))
        previous_C=C if valid else None
        prev_I=current_I;prev_native_source=native_source if current_I is not None else None
    return pd.DataFrame(rows,index=price.index)
