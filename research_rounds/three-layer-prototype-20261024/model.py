"""One independent OHLCV market-state prototype. No accounts, screenshot targets or date rules."""
import math
import numpy as np
import pandas as pd

STAGES=['无热段','立夏·启动','夏至·推进','小暑·延伸','大暑·远程推进']
CUTS=(math.sqrt(20),math.sqrt(63),2*math.sqrt(63))
PARAMS=dict(noise=63,volume=21,breakout=20,background=63,background_slope=20,
    acceptance_volume=1.5,acceptance_clv=2/3,acceptance_window=5,acceptance_closes=3,
    danger_daily_z=-2.,danger_volume=2.,flat_confirmation=3,stage_cuts=CUTS,stage_hysteresis=1.)

def three_layer(bars,use_volume=True,background_gate=True,danger_exit=True):
    if not bars.index.is_unique or not bars.index.is_monotonic_increasing:raise ValueError('ordered unique bars')
    if not np.isfinite(bars[['open','high','low','close','volume']]).all().all():raise ValueError('unknown bars must be segmented')
    if not bars[['open','high','low','close','volume']].gt(0).all().all():raise ValueError('positive OHLCV required')
    c=bars.close.astype(float);r=np.log(c/c.shift())
    f=pd.DataFrame(index=bars.index)
    f['sigma']=np.sqrt(r.pow(2).shift().rolling(63).mean()).clip(lower=1e-8)
    f['q']=bars.volume/bars.volume.shift().rolling(21).median()
    f['daily_z']=r/f.sigma
    f['high20']=c.shift().rolling(20).max();f['high63']=c.shift().rolling(63).max()
    f['low20']=bars.low.shift().rolling(20).min()
    f['ma20']=c.rolling(20).mean();f['ma63']=c.rolling(63).mean()
    f['net20']=np.log(c/c.shift(20));f['net63']=np.log(c/c.shift(63))
    f['slope63']=np.log(f.ma63/f.ma63.shift(20))
    f['clv']=((c-bars.low)/(bars.high-bars.low).replace(0,np.nan)).fillna(.5)
    active=False;candidate=None;memory=None;floor=anchor=anchor_sigma=math.nan
    episode=0;stage=0;max_stage=0;peak_g=0.;flat_count=0;rows=[];ledger=[]
    for n,(dt,b) in enumerate(bars.iterrows()):
        x=f.loc[dt];ready=bool(np.isfinite(x).all())
        entered=exited=accepted=blocked=recovered=rejected=raised=shock=0
        entry_kind=exit_kind='';notes=[];g=math.nan;display_stage=0;phase='预热未知'
        background='未知';flat=False;expansion=False;impulse=False
        if ready:
            down=bool(x.net63<0 and x.slope63<0)
            up=bool(x.net63>0 and x.slope63>0)
            background='下降' if down else '上行' if up else '混合'
            shock=int(x.daily_z<=-2 and (not use_volume or x.q>=2))
            if memory is not None:
                if b.close>memory['reclaim']:
                    recovered=1;notes.append('收复危险日前收盘，继承原放量证据');recovery_floor=memory['low'];memory=None
                elif b.close<memory['low']:
                    rejected=1;notes.append('跌破危险日低点，旧收复假说失效');memory=None
            if active:
                flat=bool(b.close<x.ma20 and x.net20<=0)
                flat_count=flat_count+1 if flat else 0
                if danger_exit and shock:exit_kind='放量急跌'
                elif b.close<=floor:exit_kind='结构破坏'
                elif flat_count>=3:exit_kind='持续转弱'
                if exit_kind:
                    ledger.append(dict(date=str(dt.date()),event='exit',episode=episode,kind=exit_kind,
                        anchor=anchor,close=float(b.close),floor=floor,stage=stage))
                    active=False;exited=1;candidate=None;notes.append(exit_kind+'，结束市场热段')
                    if danger_exit and shock:memory=dict(date=str(dt.date()),reclaim=float(c.iloc[n-1]),low=float(b.low))
            if candidate is not None and (b.close<=candidate['floor'] or n-candidate['n']>=5):candidate=None
            breakout=bool(b.close>x.high20)
            if breakout and candidate is None:
                candidate=dict(n=n,date=str(dt.date()),ceiling=float(x.high20),price=float(b.close),floor=float(x.low20))
            impulse=bool(breakout and x.clv>=2/3 and (not use_volume or x.q>=1.5))
            support=math.nan
            if impulse:
                accepted=1;entry_kind='放量突破' if use_volume else '价格突破'
            elif candidate is not None:
                a=candidate['n'];z=c.iloc[a:n+1];rr=r.iloc[a:n+1];qq=f.q.iloc[a:n+1]
                upq=float(qq[rr.gt(0)].mean()) if rr.gt(0).any() else 0.
                downq=float(qq[rr.lt(0)].mean()) if rr.lt(0).any() else 0.
                if z.gt(candidate['ceiling']).sum()>=3 and b.close>=candidate['price'] and (not use_volume or upq>=downq):
                    accepted=1;entry_kind='守位量价接受' if use_volume else '守位价格接受'
            if accepted:
                support=candidate['floor'] if candidate is not None else float(x.low20)
                candidate=None
            if recovered and not active and not exited:
                accepted=1;support=recovery_floor;entry_kind='危险证据跨日收复'
            if accepted and not exited:
                if active:
                    if support>floor:floor=support;raised=1
                elif memory is not None:
                    blocked=1;notes.append('危险日前收盘尚未收复，暂缓重启')
                elif background_gate and down and not b.close>x.high63:
                    blocked=1;notes.append('63日净推进与均价方向均向下，视为逆势回暖')
                else:
                    active=True;entered=1;episode+=1;floor=float(support)
                    anchor=float(b.close);anchor_sigma=float(x.sigma);stage=max_stage=1;peak_g=0.;flat_count=0
                    notes.append(entry_kind+'，以今日收盘创建量价起点')
            if active:
                g=float(np.log(b.close/anchor)/anchor_sigma);peak_g=max(peak_g,g)
                # Upgrade may jump across cuts; downgrade requires one anchor-noise unit of hysteresis.
                proposed=1+sum(g>=k for k in CUTS)
                if proposed>stage:stage=proposed
                while stage>1 and g<CUTS[stage-2]-1:stage-=1
                max_stage=max(max_stage,stage)
                hot=bool(entered or (b.close>=x.ma20 and x.net20>0))
                phase='热' if hot else '转弱待确认' if flat else '温·整理'
                display_stage=stage if hot else 0
                expansion=bool(hot and b.close>x.high63 and x.daily_z>=2 and (not use_volume or x.q>=2))
                if not notes:notes.append('热段存续；升降温本身不触发买卖')
            else:
                flat_count=0
                phase='危险待收复' if memory is not None else '逆势回暖' if down and (b.close>x.ma20 or x.net20>0 or blocked) else '下降' if down else '突破待验' if candidate is not None else '平·无热段'
                if not notes:notes.append('尚无通过背景和量价接受的独立起点')
        rows.append(dict(date=dt,ready=ready,background=background,phase=phase,
            target=int(active),entered=entered,exited=exited,episode=episode if active else None,
            anchor=anchor if active else math.nan,anchor_sigma=anchor_sigma if active else math.nan,
            floor=floor if active else math.nan,raised=raised,entry_kind=entry_kind if entered else '',exit_kind=exit_kind,
            candidate=int(candidate is not None),accepted=accepted,blocked=blocked,impulse=int(impulse),
            memory=int(memory is not None),memory_reclaim=memory['reclaim'] if memory else math.nan,
            memory_low=memory['low'] if memory else math.nan,recovered=recovered,rejected=rejected,
            shock=shock,flat_count=flat_count,g=g,peak_g=peak_g if active else math.nan,
            stage=stage if active else 0,display_stage=display_stage,max_stage=max_stage if active else 0,
            stage_label=STAGES[display_stage],expansion=int(expansion),reason='；'.join(notes),
            **{k:float(x[k]) for k in f.columns}))
    return pd.DataFrame(rows).set_index('date'),pd.DataFrame(ledger)
