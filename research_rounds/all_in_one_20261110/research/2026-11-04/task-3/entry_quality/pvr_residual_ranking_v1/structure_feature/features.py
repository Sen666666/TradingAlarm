"""Pure ten-observation close-low improvement; no PVR or ranking calculation."""
import numpy as np
import pandas as pd


def calculate(signal, valid, block):
    """valid/block must be the unchanged original PVR observation clock.

    L_t=min(C[t-4:t])/min(C[t-9:t-5])-1 within one comparable block.
    Both windows contain exactly five original valid observations. Min-date ties
    select the earliest occurrence inside the relevant five-observation window.
    """
    if not signal.index.equals(valid.index) or not signal.index.equals(block.index):
        raise ValueError('Exact original source clock alignment required')
    if not signal.index.is_unique or not signal.index.is_monotonic_increasing or signal.segment_id.isna().any():
        raise ValueError('Ordered unique dates and explicit source identity required')
    out=pd.DataFrame(index=signal.index)
    out['source_segment']=signal.segment_id
    out['pvr_valid_observation']=valid.astype(bool)
    out['pvr_clock_block']=block.astype('int64')
    out['pvr_block_observation']=pd.Series(pd.NA,index=signal.index,dtype='Int64')
    out['current_close_signal']=signal.close
    for name in ['L','recent5_low','prior5_low']:
        out[name]=np.nan
    for name in ['recent5_low_day','prior5_low_day']:
        out[name]=pd.Series(pd.NaT,index=signal.index,dtype='datetime64[ns]')
    out['L_status']=pd.Series('INVALID_ORIGINAL_PVR_OBSERVATION',index=signal.index,dtype='string')
    out.loc[valid,'L_status']='WARMUP_FEWER_THAN10_IN_BLOCK'
    for _,g in signal.loc[valid].groupby(block[valid],sort=False):
        idx=g.index
        out.loc[idx,'pvr_block_observation']=np.arange(len(g))
        if len(g)<10:continue
        values=g.close.to_numpy(float)
        window=np.lib.stride_tricks.sliding_window_view(values,5)
        arg=window.argmin(axis=1)
        lows=window[np.arange(len(window)),arg]
        low_dates=idx.to_numpy(dtype='datetime64[ns]')[np.arange(len(window))+arg]
        target=idx[9:]
        recent=lows[5:];prior=lows[:-5]
        L=recent/prior-1.
        out.loc[target,'recent5_low']=recent
        out.loc[target,'prior5_low']=prior
        out.loc[target,'recent5_low_day']=low_dates[5:]
        out.loc[target,'prior5_low_day']=low_dates[:-5]
        known=np.isfinite(L)&np.isfinite(recent)&np.isfinite(prior)&(prior>0)
        out.loc[target,'L']=np.where(known,L,np.nan)
        out.loc[target,'L_status']='UNKNOWN_NUMERICAL_RESULT'
        out.loc[target[known],'L_status']='KNOWN'
    out.attrs=dict(definition='min(current and previous4 valid CLOSE)/min(valid observations t-9 through t-5)-1',
                   clock='Supplied exact original PVR valid/block; positive close+amount+original masks; invalid/source restarts',
                   no_future_pivots=True,no_PVR_recalculation=True,no_rank_or_gate=True,
                   minimum_tie='Earliest date within each five-observation window')
    return out
