"""Frequency-only vectorized KAMA/EMA protection comparison. No accounts."""
import math
import numpy as np
import pandas as pd

PERIODS = np.arange(4,481,dtype=int)
WARM_LIMIT = .01
EPS = 4*2**-53/(1-4*2**-53)


def ge(a,b):
    return np.greater_equal(a,b) | (np.abs(a-b)<=EPS*np.maximum(np.maximum(np.abs(a),np.abs(b)),1e-300))


def ema_matrix(price, indicators, periods=PERIODS):
    """All periods share the existing first10 seed and known-source reset clock.

    Returns all EMA values plus each date's maximum seed residual. With common
    seeds/resets this maximum is the largest-period residual, not a fitted gate.
    """
    periods=np.asarray(periods,dtype=int)
    alpha=2./(periods+1.)
    values=np.full((len(price),len(periods)),np.nan)
    state=np.full(len(periods),np.nan)
    C=price.close.to_numpy(float)
    ready=indicators.math_ready.to_numpy(bool)
    seeds=indicators.seed_event.to_numpy(bool)
    K=indicators.K.to_numpy(float)
    for j in range(len(price)):
        if not ready[j]:
            state[:]=np.nan
        elif seeds[j]:
            state[:]=K[j]
        else:
            state+=alpha*(C[j]-state)
        values[j]=state
    # All EMA seeds and resets coincide; the largest period has the greatest
    # remaining seed coefficient. This is an identity, not a warmup fit.
    count=indicators.clean_completed_observations.to_numpy(int)
    maximum_weight=np.where(ready,np.power(1.-float(alpha.min()),count-10),np.nan)
    return values,maximum_weight


def arrays(price,features,native,indicators,emas,ema_weight):
    n=native.reindex(price.index)
    return dict(days=np.array([str(t.date()) for t in price.index]),
        C=price.close.to_numpy(float),source=features.source_key.to_numpy(),
        native_source=np.array([normalize(x) for x in n.segment_id]),
        valid=features.close_valid.to_numpy(bool),I=np.array([bit(x) for x in n.i_target],dtype=object),
        IF=n.i_floor.to_numpy(float),s=indicators.s63.to_numpy(float),
        scale=indicators.scale_status.to_numpy(),K=indicators.K.to_numpy(float),
        Kweight=indicators.seed_weight.to_numpy(float),EMA=emas,EMAweight=ema_weight,
        lookup={str(t.date()):j for j,t in enumerate(price.index)})


def bit(x):
    try:return int(x) if pd.notna(x) and float(x) in (0.,1.) else None
    except (ValueError,TypeError):return None


def normalize(x):
    if x is None or pd.isna(x):return None
    if isinstance(x,str):return x or None
    return str(int(x)) if float(x).is_integer() else str(x)


def anchor_only(pair,a):
    """Shared initial entry/seed/source/P0 gate, without future20 eligibility."""
    entry_day=(pair.get('entry_reference')or{}).get('next_observation_day')
    if entry_day and len(a['days']) and entry_day>a['days'][-1]:return 'ADMINISTRATIVE_PHASE_END_BEFORE_ENTRY',None
    if pair.get('status')!='PAIRED_SHADOWS':return 'ORIGINAL_'+pair.get('status','STATUS_MISSING'),None
    anchor=a['lookup'].get(pair['anchor_day'])
    entry=a['lookup'].get(pair['entry_reference']['next_observation_day'])
    if anchor is None or entry is None:return 'REFERENCE_OUTSIDE_DEVELOPMENT_SOURCE_CUTOFF',None
    source=a['source'][anchor]
    if source is None or not a['valid'][anchor] or a['native_source'][anchor]!=source:return 'ANCHOR_SOURCE_UNKNOWN_OR_INCOMPARABLE',None
    if a['scale'][anchor]!='READY' or not np.isfinite(a['s'][anchor]) or a['s'][anchor]<=1e-8:return 'ANCHOR_SCALE_UNREADY',None
    if not np.isfinite(a['K'][anchor]) or not np.isfinite(a['EMA'][anchor]).all():return 'ANCHOR_INDICATOR_UNREADY',None
    if not np.isfinite(a['Kweight'][anchor]) or not np.isfinite(a['EMAweight'][anchor]):return 'ANCHOR_SEED_UNKNOWN',None
    if a['Kweight'][anchor]>WARM_LIMIT or a['EMAweight'][anchor]>WARM_LIMIT:return 'ANCHOR_COMMON_SEED_RESIDUAL_GT1PCT',None
    P0=pair['P0']
    if not np.isfinite(P0) or P0<=0:return 'P0_UNKNOWN',None
    # Entry reference is inherited from the same original pair, not a new fill.
    for j in range(anchor+1,entry):
        if not a['valid'][j] or a['source'][j]!=source:return 'UNKNOWN_BETWEEN_ANCHOR_AND_ENTRY',None
    return 'ANCHOR_READY',dict(anchor=anchor,entry=entry,P0=float(P0),source=source)


def common_anchor(pair,a):
    """All exclusions depend on common inputs, never arm-specific early exits."""
    status,base=anchor_only(pair,a)
    if base is None:return status,None
    anchor,entry,source=base['anchor'],base['entry'],base['source']
    span=[]
    for j in range(entry,min(entry+20,len(a['C']))):
        if a['source'][j]!=source or a['native_source'][j]!=source:return 'COMMON_SOURCE_INCOMPARABLE',None
        if not a['valid'][j]:return 'COMMON_CLOSE_UNKNOWN',None
        if a['I'][j] is None:return 'COMMON_I_UNKNOWN',None
        # The close must first be real/known; I0 then needs no new band/IF/s.
        if a['I'][j]==0:
            span.append(j)
            return 'EVALUABLE_I_COMPETING_END',dict(base,span=span)
        if not np.isfinite(a['IF'][j]) or a['IF'][j]<=0:return 'COMMON_I_FLOOR_UNKNOWN',None
        if a['scale'][j]!='READY' or not np.isfinite(a['s'][j]) or a['s'][j]<=1e-8:return 'COMMON_SCALE_UNKNOWN',None
        if not np.isfinite(a['K'][j]) or not np.isfinite(a['EMA'][j]).all():return 'COMMON_INDICATOR_UNKNOWN',None
        span.append(j)
    if len(span)==20:return 'EVALUABLE_FULL20',dict(base,span=span)
    return 'ADMINISTRATIVE_PHASE_END_BEFORE20',None


def evaluate(common,a):
    """Arm0 KAMA, then each EMA. Today's Q is stored for the next CLOSE only."""
    width=1+a['EMA'].shape[1]
    P=np.full(width,common['P0']);alive=np.ones(width,dtype=bool)
    cause=np.zeros(width,dtype=np.int8)  # 0=no exit20, 1=protection, 2=I competing
    origin=np.zeros(width,dtype=np.int8) # line origin 0=commonP0,1=I raise,2=band raise
    exit_origin=np.full(width,-1,dtype=np.int8)
    for j in common['span']:
        if a['I'][j]==0:
            cause[alive]=2
            alive[:]=False
            break
        touched=alive & ge(P,a['C'][j])
        cause[touched]=1;exit_origin[touched]=origin[touched];alive[touched]=False
        if not alive.any():continue  # common eligibility was already checked separately.
        bands=np.concatenate(([a['K'][j]],a['EMA'][j]))*math.exp(-a['s'][j])
        old=P.copy();new=np.maximum(old,a['IF'][j])
        origins=origin.copy();origins[a['IF'][j]>old]=1
        origins[bands>new]=2
        new=np.maximum(new,bands)
        P[alive]=new[alive];origin[alive]=origins[alive]
    return dict(protection=(cause==1).astype(np.int64),I_competing=(cause==2).astype(np.int64),
        no_exit20=(cause==0).astype(np.int64),protection_commonP0=((cause==1)&(exit_origin==0)).astype(np.int64),
        protection_I_raised=((cause==1)&(exit_origin==1)).astype(np.int64),
        protection_band_raised=((cause==1)&(exit_origin==2)).astype(np.int64))
