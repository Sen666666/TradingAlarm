"""Original PVR once, fixed dual memories from that same e; no ranking/labels."""
from pathlib import Path
import importlib.util
import numpy as np
import pandas as pd

ORIGINAL=Path(__file__).resolve().parents[2]/'pvr_information_v1/feature_design/features.py'
spec=importlib.util.spec_from_file_location('local_selection_original_pvr',ORIGINAL)
API=importlib.util.module_from_spec(spec);spec.loader.exec_module(API)
TARGETS=['2022-01-10','2022-01-24','2024-09-24','2024-10-08','2026-01-15','2026-01-20','2026-05-15']
FLOATS=list(API.PVR_COLUMNS)+['E_fast','E_slow']


def calculate(frame):
    g=frame.sort_values('trade_date').set_index('trade_date')
    assert g.index.is_unique and g.index.is_monotonic_increasing
    assert g.source.nunique(dropna=False)==1 and g.source.notna().all()
    signal=g[['close','amount']].copy();signal['segment_id']=0
    valid,block=API.original_observation_clock(signal)
    out=API.original_pvr(signal)  # e is computed exactly once, reused below.
    out['source_segment']=0
    out['pvr_clock_block']=block
    out['pvr_valid_observation']=valid
    out['current_close_qfq']=g.close
    out['current_amount_passthrough']=g.amount
    out['qfq_adjustment_factor']=g.adjustment_factor
    out['raw_adjustment_factor']=g.raw_adjustment_factor
    out['reference_adjustment_factor']=g.reference_adjustment_factor
    out['reference_trade_date']=g.reference_trade_date
    out['source']=g.source
    out['E_fast']=np.nan;out['E_slow']=np.nan
    for n in ['fast_known_count5','slow_known_count58','e_known_count63','current_block_observations_through_t']:
        out[n]=pd.Series(pd.NA,index=g.index,dtype='Int64')
    dates=['block_start_day','scale_prior63_return_start_day','scale_prior63_return_end_day','scale_prior_return_price_base_day',
           'amount_prior21_start_day','amount_prior21_end_day','E_start_day','E_end_day',
           'fast_start_day','fast_end_day','slow_start_day','slow_end_day']
    for n in dates:out[n]=pd.Series(pd.NaT,index=g.index,dtype='datetime64[ns]')
    for n in ['pvr_status','e_status','fast_status','slow_status']:
        out[n]=pd.Series('INVALID_ORIGINAL_PVR_OBSERVATION',index=g.index,dtype='string')
        out.loc[valid,n]='WARMUP'
    out.loc[np.isfinite(out.score),'pvr_status']='KNOWN'
    out.loc[np.isfinite(out.e),'e_status']='KNOWN'
    weights=.8**np.arange(4,-1,-1)
    for _,grp in signal.loc[valid].groupby(block[valid],sort=False):
        idx=grp.index;n=len(idx);e=out.loc[idx,'e'];a=e.to_numpy(float);ix=idx.to_numpy(dtype='datetime64[ns]')
        out.loc[idx,'block_start_day']=ix[0]
        out.loc[idx,'current_block_observations_through_t']=np.arange(n)+1
        out.loc[idx,'fast_known_count5']=e.rolling(5,min_periods=1).count().astype('int64')
        out.loc[idx,'slow_known_count58']=e.shift(5).rolling(58,min_periods=1).count().astype('int64')
        out.loc[idx,'e_known_count63']=e.rolling(63,min_periods=1).count().astype('int64')
        offsets=[('scale_prior63_return_start_day',-63,64),('scale_prior63_return_end_day',-1,64),('scale_prior_return_price_base_day',-64,64),
                 ('amount_prior21_start_day',-21,21),('amount_prior21_end_day',-1,21),('E_start_day',-20,20),('E_end_day',0,20),
                 ('fast_start_day',-4,4),('fast_end_day',0,4),('slow_start_day',-62,62),('slow_end_day',-5,62)]
        for name,offset,start in offsets:
            if n>start:out.loc[idx[start:],name]=ix[np.arange(start,n)+offset]
        if n>=5:
            w=np.lib.stride_tricks.sliding_window_view(a,5);z=(w*weights).sum(axis=1)/weights.sum();ok=np.isfinite(w).all(axis=1)&np.isfinite(z)
            out.loc[idx[4:],'E_fast']=np.where(ok,z,np.nan);out.loc[idx[4:][ok],'fast_status']='KNOWN'
        if n>=63:
            w=np.lib.stride_tricks.sliding_window_view(a,63)[:,:58];z=w.mean(axis=1);ok=np.isfinite(w).all(axis=1)&np.isfinite(z)
            out.loc[idx[62:],'E_slow']=np.where(ok,z,np.nan);out.loc[idx[62:][ok],'slow_status']='KNOWN'
    return out


def selected_rows(sid,frame,full):
    dates=pd.DatetimeIndex(TARGETS);out=full.reindex(dates).copy();present=dates.isin(full.index)
    out.insert(0,'day',TARGETS);out.insert(0,'sid',sid)
    out['target_row_present']=present
    out['target_status']=np.where(present,'OBSERVED_TARGET_BAR','MISSING_TARGET_BAR')
    out['source_first_observation_day']=frame.trade_date.min()
    out['source_last_observation_day']=frame.trade_date.max()
    out['past_source_observation_count']=frame.trade_date.to_numpy().searchsorted(dates.to_numpy(),side='left')
    out['source_observation_count_through_t']=frame.trade_date.to_numpy().searchsorted(dates.to_numpy(),side='right')
    for n in ['pvr_status','e_status','fast_status','slow_status']:
        out[n]=out[n].fillna('MISSING_TARGET_BAR')
    out['qfq_reference_later_than_target']=pd.arrays.BooleanArray(
        (pd.to_datetime(out.reference_trade_date).to_numpy()>dates.to_numpy()),~present)
    out['decision_at']=out.day+'T15:00:00+08:00'
    return out.reset_index(drop=True)


def reference(signal):
    """Independent fixed-parameter finite-array implementation, no pandas rolling."""
    valid,block=API.original_observation_clock(signal)
    out=pd.DataFrame(np.nan,index=signal.index,columns=FLOATS)
    w21=.9**np.arange(20,-1,-1);w21/=w21.sum();w5=.8**np.arange(4,-1,-1)
    for _,g in signal.loc[valid].groupby(block[valid],sort=False):
        c=g.close.to_numpy(float);amt=g.amount.to_numpy(float);n=len(g);r=np.r_[np.nan,np.diff(np.log(c))];e=np.full(n,np.nan)
        for j in range(n):
            ref=float(np.median(amt[j-21:j]))if j>=21 else np.nan
            scale=max(float(np.median(np.abs(r[j-63:j])))*1.4826,1e-8)if j>=64 else np.nan
            u=float(np.tanh(r[j]/scale));b=float(np.tanh(np.log(amt[j]/ref)));e[j]=u*(1+.5*abs(u)*b)
            E=float(np.dot(w21,e[j-20:j+1]))if j>=20 and np.isfinite(e[j-20:j+1]).all()else np.nan
            fast=float((w5*e[j-4:j+1]).sum()/w5.sum())if j>=4 and np.isfinite(e[j-4:j+1]).all()else np.nan
            slow=float(e[j-62:j-4].mean())if j>=62 and np.isfinite(e[j-62:j-4]).all()else np.nan
            out.loc[g.index[j]]=[r[j],scale,ref,u,b,e[j],E,50+50*np.tanh(2*E),fast,slow]
    return out
