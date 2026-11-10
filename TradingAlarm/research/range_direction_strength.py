"""Signed high/low directional movement, not ADX or a profit probability.
21-observation smoothing and normalized signed score are fixed research choices.
"""
import numpy as np
import pandas as pd


def range_frame(frame,volume,joint=False,close_only=False):
    f=frame[['high','low','close']].join(volume.rename('volume'))
    f=f.loc[(f>0).all(axis=1)&np.isfinite(f).all(axis=1)]
    if (f.high<f.low).any():raise ValueError('high below low')
    up=(f.high-f.high.shift())/f.close.shift()
    down=(f.low.shift()-f.low)/f.close.shift()
    if close_only:
        up=f.close.pct_change(fill_method=None)
        down=-up
    plus=up.where(up.gt(down)&up.gt(0),0.).where(up.notna())
    minus=down.where(down.gt(up)&down.gt(0),0.).where(down.notna())
    weight=np.sqrt(f.volume/f.volume.shift().rolling(21).median()).clip(.25,4) if joint else pd.Series(1.,index=f.index)
    # Same warmup in both variants; common finite observation support.
    weight=weight.where(f.volume.shift().rolling(21).count().eq(21))
    plus=(plus*weight).ewm(alpha=1/21,adjust=False,min_periods=21).mean()
    minus=(minus*weight).ewm(alpha=1/21,adjust=False,min_periods=21).mean()
    total=plus+minus;balance=((plus-minus)/total).where(total.gt(0),0.).where(total.notna())
    return pd.DataFrame(dict(strength=5+5*np.tanh(np.sqrt(5)*balance),positive=plus,negative=minus,balance=balance)).reindex(frame.index)
