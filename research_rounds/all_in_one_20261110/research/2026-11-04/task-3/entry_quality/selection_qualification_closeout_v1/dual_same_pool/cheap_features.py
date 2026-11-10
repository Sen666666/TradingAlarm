"""Cheap original e/PVR once, dual memories reuse e. No E0/I/G1 imports."""
import numpy as np
import pandas as pd


def calculate(signal,api):
    valid,block=api.original_observation_clock(signal)
    out=api.original_pvr(signal)
    out['source_segment']=signal.segment_id
    out['pvr_clock_block']=block
    out['pvr_valid_observation']=valid
    out['pvr_block_observation']=pd.Series(pd.NA,index=signal.index,dtype='Int64')
    out['E_fast']=np.nan;out['E_slow']=np.nan
    for name in ['E_start_day','E_end_day','fast_start_day','fast_end_day','slow_start_day','slow_end_day']:
        out[name]=pd.Series(pd.NaT,index=signal.index,dtype='datetime64[ns]')
    for name in ['fast_known_count5','slow_known_count58','e_known_count63']:
        out[name]=pd.Series(pd.NA,index=signal.index,dtype='Int64')
    for field,value in [('pvr_status','score'),('fast_status','E_fast'),('slow_status','E_slow')]:
        out[field]=pd.Series('INVALID_ORIGINAL_PVR_OBSERVATION',index=signal.index,dtype='string')
        out.loc[valid,field]='WARMUP'
    out.loc[np.isfinite(out.score),'pvr_status']='KNOWN'
    weights=.8**np.arange(4,-1,-1)
    for _,g in signal.loc[valid].groupby(block[valid],sort=False):
        idx=g.index;dates=idx.to_numpy(dtype='datetime64[ns]');n=len(g);e=out.loc[idx,'e'];a=e.to_numpy(float)
        out.loc[idx,'pvr_block_observation']=np.arange(n)
        out.loc[idx,'fast_known_count5']=e.rolling(5,min_periods=1).count().astype('int64')
        out.loc[idx,'slow_known_count58']=e.shift(5).rolling(58,min_periods=1).count().astype('int64')
        out.loc[idx,'e_known_count63']=e.rolling(63,min_periods=1).count().astype('int64')
        for field,offset,start in [('E_start_day',-20,20),('E_end_day',0,20),('fast_start_day',-4,4),('fast_end_day',0,4),('slow_start_day',-62,62),('slow_end_day',-5,62)]:
            if n>start:out.loc[idx[start:],field]=dates[np.arange(start,n)+offset]
        if n>=5:
            w=np.lib.stride_tricks.sliding_window_view(a,5);z=(w*weights).sum(axis=1)/weights.sum();known=np.isfinite(w).all(axis=1)&np.isfinite(z)
            out.loc[idx[4:],'E_fast']=np.where(known,z,np.nan);out.loc[idx[4:][known],'fast_status']='KNOWN'
        if n>=63:
            w=np.lib.stride_tricks.sliding_window_view(a,63)[:,:58];z=w.mean(axis=1);known=np.isfinite(w).all(axis=1)&np.isfinite(z)
            out.loc[idx[62:],'E_slow']=np.where(known,z,np.nan);out.loc[idx[62:][known],'slow_status']='KNOWN'
    return out
