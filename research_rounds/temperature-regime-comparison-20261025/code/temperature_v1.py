"""Seven evidence levels; prefix-causal, OHLCV-only, no orders or accounts."""
from __future__ import annotations
import math
import numpy as np
import pandas as pd

LABELS=['冷','回暖','突破待验','量价立态','有效推进','多尺度强趋势','放量扩张']
PARAMS=dict(volume_window=21,noise_window=63,short=5,medium=20,long=63,
    acceptance_volume=1.5,expansion_volume=2.0,close_location=2/3,
    medium_z=1.,medium_er=.25,long_z=1.,long_er=.20,fast_z=2.,expansion_daily_z=1.,
    acceptance_window=5,acceptance_closes=3,entry_level=4)

def temperature_frame(bars:pd.DataFrame, use_volume=True):
    """Each source segment must be passed independently. Positive observed OHLCV."""
    if not bars.index.is_unique or not bars.index.is_monotonic_increasing:raise ValueError('ordered unique bars')
    if not np.isfinite(bars[['open','high','low','close','volume']]).all().all():raise ValueError('unknown input must be split out')
    if not bars[['open','high','low','close','volume']].gt(0).all().all():raise ValueError('positive observed bars required')
    c=bars.close.astype(float);v=bars.volume.astype(float);r=np.log(c/c.shift())
    sigma=np.sqrt(r.pow(2).shift().rolling(63).mean()).clip(lower=1e-8)
    q=v/v.shift().rolling(21).median()
    f=pd.DataFrame(index=bars.index)
    f['q']=q;f['sigma']=sigma
    for h in (5,20,63):
        net=np.log(c/c.shift(h));path=r.abs().rolling(h).sum()
        f[f'z{h}']=net/(sigma*np.sqrt(h))
        f[f'er{h}']=np.divide(net,path,out=np.zeros(len(c)),where=path.to_numpy()>0)
        f[f'high{h}']=c.shift().rolling(h).max()
        f[f'ma{h}']=c.rolling(h).mean()
    f['low20']=bars.low.shift().rolling(20).min()
    span=bars.high-bars.low
    f['clv']=((c-bars.low)/span.where(span.gt(0))).fillna(.5)
    candidate=None;structure=False;floor=math.nan;anchor=math.nan
    guard=None;participating=False;structure_id=0;rows=[];ledger=[]
    for n,(dt,b) in enumerate(bars.iterrows()):
        x=f.loc[dt];ready=bool(np.isfinite(x[['sigma','z63','high63','q']]).all())
        level=-1;created=accepted=exited=entered=raised=guard_created=guard_recovered=invalidated=0
        accept_kind='';evidence=[];breakout=False;fast=False;medium=False;long=False;expansion=False
        old_floor=floor;entry_floor=math.nan
        if ready:
            # A close touching the fixed/ratcheted structural floor rejects it.
            if structure and b.close<=floor:
                structure=False;invalidated=1;exited=int(participating);participating=False;guard=None
                evidence.append('收盘触及结构下沿，原结构撤销')
            if candidate is not None and (b.close<=candidate['floor'] or n-candidate['n']>=5):
                ledger.append(dict(candidate,ended=str(dt.date()),outcome='rejected_or_expired'))
                candidate=None
            if guard is not None and b.close>guard['reclaim']:
                guard=None;guard_recovered=1;evidence.append('收复高参与下跌前收盘，解除推进否决')
            adverse=bool(use_volume and n>0 and x.q>=1.5 and b.close<c.iloc[n-1] and b.close<x.ma20)
            if structure and adverse:
                if guard is None or c.iloc[n-1]>guard['reclaim']:
                    guard={'date':str(dt.date()),'reclaim':float(c.iloc[n-1])}
                guard_created=1;evidence.append('放量下跌且低于20日均价，推进证据待收复')
            breakout=bool(b.close>x.high20)
            if breakout and candidate is None:
                candidate=dict(n=n,date=str(dt.date()),ceiling=float(x.high20),price=float(b.close),floor=float(x.low20))
                created=1
            impulse=bool(breakout and x.clv>=2/3 and (not use_volume or x.q>=1.5))
            if impulse:
                accepted=1;accept_kind='放量突破接受' if use_volume else '价格突破接受'
            elif candidate is not None:
                a=candidate['n'];z=bars.iloc[a:n+1];above=int(z.close.gt(candidate['ceiling']).sum())
                # Compare average daily relative effort, never total volume of unequal-length legs.
                rr=r.iloc[a:n+1];qq=q.iloc[a:n+1]
                up=float(qq.loc[rr.gt(0)].mean()) if rr.gt(0).any() else 0.
                down=float(qq.loc[rr.lt(0)].mean()) if rr.lt(0).any() else 0.
                volume_response=(not use_volume or up>=down)
                if above>=3 and b.close>=candidate['price'] and volume_response:
                    accepted=1;accept_kind='突破后守位且推进日参与不弱' if use_volume else '突破后守位接受'
            if accepted:
                support=float(candidate['floor'] if candidate is not None else x.low20)
                if not structure:
                    structure=True;structure_id+=1;floor=support;anchor=float(x.high20 if candidate is None else candidate['ceiling'])
                    entry_floor=floor
                elif support>floor:
                    floor=support;raised=1
                if candidate is not None:
                    ledger.append(dict(candidate,ended=str(dt.date()),outcome=accept_kind));candidate=None
                evidence.append(accept_kind)
            # No false same-day structure resurrection after an invalidation.
            # Acceptance is possible, but the participation projection cannot reenter that day.
            medium=bool(x.z20>=1 and x.er20>=.25 and b.close>x.ma20)
            fast=bool(b.close>x.high63 and x.z5>=2 and x.clv>=2/3 and (not use_volume or x.q>=1.5))
            long=bool(x.z63>=1 and x.er63>=.20 and b.close>x.ma63)
            expansion=bool(b.close>x.high63 and r.iloc[n]/x.sigma>=1 and x.clv>=2/3 and (not use_volume or x.q>=2))
            level=0
            if x.z5>=1 or b.close>x.high5:level=1
            if candidate is not None:level=2
            if structure:
                level=3
                if medium or fast:level=4
                if (medium or fast) and long:level=5
                if (medium or fast) and long and expansion:level=6
                if guard is not None:
                    level=min(level,3)
                if level>=4 and not participating and not invalidated:
                    participating=True;entered=1
                if fast:evidence.append('63日新高＋5日快速推进，可跳级')
                if medium:evidence.append('20日净推进与路径效率共同通过')
                if long:evidence.append('63日尺度同向支持')
                if level==6:evidence.append('强趋势内新高、放量与日推进共同扩张')
            phase=('推进受阻待收复' if guard is not None else '推进' if level>=4 else '整理或证据转弱' if structure else '突破观察' if candidate else '反弹' if level==1 else '无上行依据')
            if not evidence:evidence.append('结构仍在，当前推进不足' if structure else '未建立可接受的突破结构')
        else:phase='预热未知';evidence=['不足64个有效观察，不判断冷暖']
        rows.append(dict(date=dt,level=level,label=LABELS[level] if level>=0 else '未知',phase=phase,
            ready=ready,structure=int(structure),structure_id=structure_id if structure else None,
            floor=floor if structure else math.nan,anchor=anchor if structure else math.nan,
            candidate=int(candidate is not None),candidate_created=created,accepted=accepted,accept_kind=accept_kind,
            target=int(participating),entered=entered,exited=exited,structural_invalidated=invalidated,raised=raised,
            guard=int(guard is not None),guard_created=guard_created,guard_recovered=guard_recovered,
            guard_reclaim=guard['reclaim'] if guard else math.nan,breakout=int(breakout),fast=int(fast),medium=int(medium),
            long=int(long),expansion=int(expansion),reason='；'.join(evidence),**{k:float(x[k]) for k in f.columns}))
    result=pd.DataFrame(rows).set_index('date')
    result['level_change']=result.level.diff().fillna(0).astype(int)
    result['heat_cross']=((result.level>=4)&(result.level.shift(fill_value=-1)<4)).astype(int)
    result['overextended']=(result.ready & (np.log(c/result.ma20)/result.sigma>=3)).astype(int)
    return result,pd.DataFrame(ledger)
