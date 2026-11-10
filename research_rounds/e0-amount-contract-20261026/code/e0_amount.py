"""E0-AMT-P1 calculation adapter, technical prototype only; no account imports.

The immutable E0 event and participation kernels are reused numerically. Their
legacy `volume` parameter receives the explicitly named activity input. Public
outputs carry basis/unit; the original E0 and G1 callers are not changed.
"""
from pathlib import Path
import sys
import numpy as np
import pandas as pd
ROOT=Path(__file__).resolve().parents[3]
SOURCE=ROOT/'research_rounds/pv-participation-response-20261020/code'
sys.path.insert(0,str(SOURCE))
from numeric import event_frame_numeric
from participation import participation_frame

def activity_input(bars,basis='amount',amount_unit='CNY'):
 if basis not in ('amount','shares'):raise ValueError('Explicit amount or shares basis required')
 field='amount' if basis=='amount' else 'volume'
 if basis=='amount' and amount_unit!='CNY':raise ValueError('This A-share prototype requires actual CNY turnover')
 required=['open','high','low','close',field]
 if any(c not in bars for c in required):raise ValueError('Missing observed OHLC or '+field)
 if not bars.index.is_unique or not bars.index.is_monotonic_increasing:raise ValueError('Ordered unique verified observations required')
 values=bars[required].to_numpy(float)
 if not np.isfinite(values).all() or not (values>0).all():raise ValueError('Missing/nonpositive observations require source resolution; no share fallback or synthetic amount')
 x=bars[['open','high','low','close']].copy();x['volume']=bars[field].astype(float)
 return x

def run(bars,basis='amount',amount_unit='CNY'):
 x=activity_input(bars,basis,amount_unit);events=event_frame_numeric(x.close,x.volume,joint=True);state,memory=participation_frame(x,events,mode='volume')
 state=state.rename(columns={'volume_ratio':'activity_ratio','high_effort':'high_activity'});state['activity_basis']=basis;state['activity_unit']='CNY' if basis=='amount' else 'shares'
 memory=memory.rename(columns={'event_volume':'event_activity','volume_ratio':'activity_ratio','volume_baseline':'activity_baseline','resolution_volume_ratio':'resolution_activity_ratio'})
 memory['activity_basis']=basis;memory['activity_unit']='CNY' if basis=='amount' else 'shares'
 return dict(version='E0-AMT-P1' if basis=='amount' else 'E0-shares-control',basis=basis,unit='CNY' if basis=='amount' else 'shares',events=events,state=state,memory=memory,source=str(SOURCE))
