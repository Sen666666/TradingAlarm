"""Pure current-cache-equivalent E0/G1_I adapter. No account/cache imports."""
from pathlib import Path
import sys
import numpy as np
import pandas as pd

RR=Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
sys.path[:0]=[str(RR/'pv-strength-b5-20261025/code'),str(RR/'b5-g1-20261025/code'),str(RR/'pv-participation-response-20261020/code')]
from data_utils import eligible_prices
from numeric import event_frame_numeric
from participation import participation_frame
from evidence import build_evidence
from policy import e0_policy
from grade import classify
from policies_g1 import project


def calculate(frame):
    """frame is already full-available-prefix-clipped OHLCV single-source data.

    Exactly mirrors cache.py:23-34, generating its numeric events, participation
    ready/effort fields and G1 grade rather than borrowing old cached values.
    Not S0: no sector/cap/issuer/listing/trading eligibility is manufactured.
    """
    assert frame.index.is_unique and frame.index.is_monotonic_increasing
    f=eligible_prices(frame).copy()
    if f.empty:return pd.DataFrame(index=f.index)
    assert f.segment_id.nunique()==1
    events=event_frame_numeric(f.close,f.volume,joint=True,event_exit=False)
    state,_=participation_frame(f,events,mode='volume')
    e=f[['segment_id','open','high','low','close','volume']].copy()
    e['valid_price_observation']=True
    e['price_observation']=e.groupby('segment_id',sort=False).cumcount()
    e['event']=events.event;e['confirmed_pivot_price']=events.confirmed_pivot_price
    e['ready']=state.ready;e['previous_close']=e.groupby('segment_id',sort=False).close.shift()
    v=e.volume.where(np.isfinite(e.volume)&e.volume.gt(0))
    e['volume_baseline']=v.groupby(e.segment_id,sort=False).transform(lambda q:q.shift().rolling(21,min_periods=21).median())
    for field in ['volume_ratio','high_effort','declined']:e[field]=state[field]
    e['decline_candidate']=False;e['candidate_lower']=np.nan;e['candidate_reclaim']=np.nan
    base,_=e0_policy(e);assert not base.pending.fillna(0).any()
    inputs=f[['open','high','low','close','volume','segment_id']].copy()
    inputs['valid_price_observation']=True
    inputs['valid_strength_observation']=np.isfinite(inputs.volume)&inputs.volume.gt(0)
    evidence,_=build_evidence(inputs)
    g,_=classify(evidence)
    projected=project(e,base,g,'G1_I')
    out=pd.DataFrame(index=f.index)
    for n in ['ready','target','floor','entered','exited']:out['e0_'+n]=base[n]
    for n in ['target','floor','entered','exited','buy_event','exit_reason']:out['i_'+n]=projected[n]
    out=out.rename(columns={'i_buy_event':'i_buy'})
    for n in ['grade','ready','fresh_up','acute_down','up_reasons']:out['g_'+n]=g[n]
    out['numeric_event']=events.event
    out['numeric_leg_direction']=events.leg_direction
    out['close']=f.close
    return out
