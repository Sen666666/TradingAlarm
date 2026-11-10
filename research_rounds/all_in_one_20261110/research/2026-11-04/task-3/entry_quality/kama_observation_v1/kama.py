"""KAMA/EMA20 observations and old-line-only protection shadows. No accounts."""
import math
from collections import deque
from statistics import median
import numpy as np
import pandas as pd

ER_LENGTH=10
FAST=2./3.
SLOW=2./31.
EMA_ALPHA=2./21.
SCALE_WINDOW=63
SCALE_FACTOR=1.4826
SCALE_GUARD=1e-8
EPS=4*2**-53/(1-4*2**-53)
def finite(x):
    try:return x is not None and x is not pd.NA and math.isfinite(float(x))
    except (ValueError,TypeError):return False
def positive(x):return finite(x) and float(x)>0
def bit(x):return int(x) if finite(x) and float(x) in (0.,1.) else None
def ge(a,b):return a>=b or abs(a-b)<=EPS*max(abs(a),abs(b),1e-300)

def calculate(price,features):
    """Full prefix. Strict close/source invalid breaks warmth; no CP/I resets.

    KAMA and EMA20 both seed at j=9 using the first ten completed close mean.
    j=10 is the first ER/KAMA and fixed EMA20 update. No economic warm gate.
    seed_weight tracks the remaining numerical influence of that seed exactly.
    """
    C=price.close.to_numpy();cv=features.close_valid.to_numpy();seg=features.source_key.to_numpy()
    previous_source=None;closes=deque(maxlen=11);abslogs=deque(maxlen=63)
    K=None;EMA=None;kw=None;ew=None;previous_C=None;clean_count=0;rows=[]
    for j,t in enumerate(price.index):
        source=seg[j];valid=bool(cv[j]) and source is not None and positive(C[j])
        if source!=previous_source or not valid:
            closes.clear();abslogs.clear();K=EMA=kw=ew=previous_C=None;clean_count=0
        r=None if previous_C is None or not valid else math.log(float(C[j])/previous_C)
        s=SCALE_FACTOR*median(abslogs) if r is not None and len(abslogs)==63 else None
        scale_status='READY' if s is not None and s>SCALE_GUARD else 'LOW_SCALE_GUARD' if s is not None else 'UNREADY_OR_INVALID'
        ER=alpha=None;seed=False;oldK=K;oldEMA=EMA
        if valid:
            value=float(C[j]);closes.append(value);clean_count+=1
            if clean_count==10:
                K=EMA=math.fsum(closes)/10.;kw=ew=1.;seed=True
            elif clean_count>10:
                values=list(closes);den=math.fsum(abs(values[i]-values[i-1]) for i in range(1,11))
                ER=0. if den==0 else abs(values[-1]-values[0])/den
                alpha=(ER*(FAST-SLOW)+SLOW)**2
                K=K+alpha*(value-K);kw*=1.-alpha
                EMA=EMA+EMA_ALPHA*(value-EMA);ew*=1.-EMA_ALPHA
        band_ready=K is not None and scale_status=='READY'
        rows.append(dict(day=str(t.date()),source_key=source,close_valid=valid,C=float(C[j]) if valid else None,
            raw_C=price.raw_close.iloc[j],clean_completed_observations=clean_count,r=r,s63=s,scale_status=scale_status,
            seed_event=seed,math_ready=K is not None,ER=ER,alpha=alpha,K_previous=oldK,K=K,seed_weight=kw,
            EMA20_previous=oldEMA,EMA20=EMA,EMA20_alpha=EMA_ALPHA if clean_count>10 else None,EMA20_seed_weight=ew,
            proposed_band=K*math.exp(-s) if band_ready else None,
            EMA20_proposed_band=EMA*math.exp(-s) if band_ready else None,
            band_ready=band_ready,CP_or_I_resets=False,economic_seed_decay_gate='NONE'))
        if valid and r is not None:abslogs.append(abs(r))
        previous_C=float(C[j]) if valid else None;previous_source=source
    return pd.DataFrame(rows,index=price.index)

def shadow(pair,price,features,native,indicators,label):
    """Common original P0. Test only stored P; today's Q lives next CLOSE.

    Original CP is not updated/recomputed; its saved control is annotation only.
    Q >= C is recorded, never retroactively used as an exit on that same CLOSE.
    Unknown indicator is not zero; the known independent I floor is retained.
    """
    assert label in ('KAMA','EMA20')
    where={str(t.date()):j for j,t in enumerate(price.index)};n=native.reindex(price.index)
    start=where[(pair['entry_reference'])['next_observation_day']];end=where[pair['common_end_day']]
    a=where[pair['anchor_day']];source=features.source_key.iloc[a];P=float(pair['P0']);steps=[]
    exit_day=exit_line=exit_reason=None;exitj=None;ever_unknown=False
    band_col='proposed_band' if label=='KAMA' else 'EMA20_proposed_band'
    for j in range(start,end+1):
        day=str(price.index[j].date());valid=bool(features.close_valid.iloc[j]) and features.source_key.iloc[j]==source
        C=float(price.close.iloc[j]) if valid else None;ri=bit(n.i_target.iloc[j]);IF=n.i_floor.iloc[j]
        band=indicators[band_col].iloc[j];oldP=P;Q=None;unknown=None
        if features.source_key.iloc[j]!=source:unknown='SOURCE_INCOMPARABLE'
        elif ri==0:exit_reason='ORIGINAL_I_INVALID_CURRENT';exit_line=P
        elif valid and ge(P,C):exit_reason='EXIT_STORED_LINE';exit_line=P
        elif not valid:unknown='UNKNOWN_CLOSE'
        elif ri is None or not positive(IF):unknown='UNKNOWN_CURRENT_I_OR_IFLOOR'
        else:
            Q=max(P,float(IF))
            if positive(band):Q=max(Q,float(band))
            else:unknown='INDICATOR_BAND_UNREADY_OR_UNKNOWN'
            # A proposal is installed for the next CLOSE, even if above this C.
            P=Q
        if unknown:ever_unknown=True
        row=dict(day=day,label=label,C=C,raw_C=price.raw_close.iloc[j],I_target=ri,I_floor=IF,
            P_old=oldP,band=band,Q_for_next_close=Q,P_next=None if exit_reason else P,
            pending_above_current=bool(Q is not None and C is not None and ge(Q,C)),
            exit_reason=exit_reason,unknown_reason=unknown,
            ER=indicators.ER.iloc[j],alpha=indicators.alpha.iloc[j],K=indicators.K.iloc[j],
            seed_weight=indicators.seed_weight.iloc[j],EMA20=indicators.EMA20.iloc[j],s63=indicators.s63.iloc[j],
            new_Q_never_tests_same_close=True,CP_candidate_not_used_after_anchor=True)
        steps.append(row)
        if exit_reason:exit_day=day;exitj=j;break
        if unknown in ('SOURCE_INCOMPARABLE','UNKNOWN_CLOSE','UNKNOWN_CURRENT_I_OR_IFLOOR'):break
    quote=None
    if exitj is not None and exitj+1<len(price):
        j=exitj+1;valid=bool(features.close_valid.iloc[j]) and features.source_key.iloc[j]==source and positive(price.open.iloc[j])
        quote=dict(day=str(price.index[j].date()),OPEN=float(price.open.iloc[j]) if valid else None,
            raw_OPEN=price.raw_open.iloc[j] if valid else None,status='REFERENCE_ONLY_EXECUTION_UNKNOWN' if valid else 'NEXT_SOURCE_ROW_INVALID_OR_INCOMPARABLE')
    return dict(sid=pair['sid'],anchor_day=pair['anchor_day'],label=label,P0=pair['P0'],
        anchor_seed_weight=indicators.seed_weight.iloc[a],entry_reference=pair['entry_reference'],
        outcome='EXIT_SIGNAL' if exit_reason else 'UNKNOWN' if ever_unknown else 'RIGHT_CENSORED',
        exit_day=exit_day,exit_reason=exit_reason,exit_line=exit_line,next_source_OPEN_reference=quote,
        ever_unknown=ever_unknown,original_CP_control=pair['CP'],steps=steps,not_actual_position_or_order=True)
