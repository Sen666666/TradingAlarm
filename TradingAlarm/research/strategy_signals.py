"""Strategy plugins output close-time registered exposure; execution stays in account engine.
Only historical observations are used. No fitting or parameter search here.
"""
import pandas as pd
import numpy as np

HORIZONS={'short21':21,'medium63':63,'long252':252}
CHANNELS={'channel21_21':21,'channel21_63':63}
GEOMETRY={'slope21_exit0':0.,'slope21_exitminus2':-2.}


def slope_geometry(close):
    """Descriptive OLS slope/noise score, not a statistical significance test."""
    x=np.arange(21,dtype=float)-10.;xx=float(x@x)
    def score(values):
        if not np.isfinite(values).all() or np.any(values<=0):return np.nan
        y=np.log(values/values[0]);y-=y.mean();slope=float(x@y/xx)
        if abs(slope)<1e-14:return 0.
        residual=y-slope*x;sse=float(residual@residual)
        if sse<1e-24:return float(np.sign(slope)*1e6)
        return float(np.clip(slope/np.sqrt(sse/19./xx),-1e6,1e6))
    return close.rolling(21,min_periods=21).apply(score,raw=True)


def geometry_signal(close,exit_score):
    held=False;values=[]
    for score in slope_geometry(close):
        if np.isfinite(score):
            if held and score<exit_score:held=False
            elif not held and score>2.:held=True
        values.append(float(held))
    return pd.Series(values,index=close.index)


def channel_signal(frame,exit_window,initial_protection=False,trailing=False,entry_gate=None):
    upper=frame.high.shift().rolling(21).max()
    lower=frame.low.shift().rolling(exit_window).min()
    ready=frame.close.shift().rolling(63).count().ge(63)
    tr=pd.concat([frame.high-frame.low,(frame.high-frame.close.shift()).abs(),(frame.low-frame.close.shift()).abs()],axis=1).max(axis=1)
    atr=tr.rolling(21).mean()
    held=False;values=[];protection=None;highest=None
    gate=pd.Series(True,index=frame.index) if entry_gate is None else entry_gate.reindex(frame.index).fillna(False)
    for close,hi,lo,valid,volatility,allowed in zip(frame.close,upper,lower,ready,atr,gate):
        if valid:
            if held and trailing:
                highest=max(highest,close);protection=max(protection,highest-4*volatility)
            if held and (close<lo or (initial_protection and close<protection)):held=False;protection=None
            elif not held and close>hi and allowed:
                held=True;protection=close-2*volatility;highest=close
        values.append(float(held))
    return pd.Series(values,index=frame.index)


def build_signals(assets,name):
    if name in ('rms_direction_price','rms_direction_volume'):
        from rms_direction_strength import rms_direction_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            score=rms_direction_frame(sig.close.reindex(valid),v,joint=name.endswith('_volume')).strength
            result[symbol]=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name=='dual21_63':
        result={}
        for symbol,a in assets.items():
            close=a['signal'].close
            fast=close.pct_change(21,fill_method=None);slow=close.pct_change(63,fill_method=None)
            result[symbol]=(.5*fast.gt(0).astype(float)+.5*slow.gt(0).astype(float)).where(fast.notna()&slow.notna(),0.)
        return result
    if name in ('mean_distance_price','mean_distance_volume'):
        from mean_distance_strength import distance_frame
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            result[symbol]=distance_frame(sig.close.reindex(valid),v,joint=name.endswith('_volume')).target.reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('symmetric_adaptive_volume','symmetric_pairwise_volume','graded_adaptive_volume','graded_pairwise_volume'):
        from adaptive_geometric_strength import adaptive_frame
        from pairwise_trend_strength import pairwise_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            if name.endswith('adaptive_volume'):score=adaptive_frame(sig.close.reindex(valid),raw.close.reindex(valid),v).strength
            else:score=pairwise_frame(sig.close.reindex(valid),v).strength
            if name.startswith('graded_'):
                from graded_trend_exposure import graded_exposure
                exposure=graded_exposure(score)
            else:exposure=strength_exposure(score,exit_threshold=5-5*np.tanh(1))
            result[symbol]=exposure.reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('asymmetric_pairwise_volume','restored_pairwise_volume'):
        from asymmetric_pairwise import asymmetric_frame
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            result[symbol]=asymmetric_frame(sig.close.reindex(valid),v,require_crossing=name!='restored_pairwise_volume').target.reindex(sig.index,method='ffill').fillna(0)
        return result
    if name == 'confirmed_pairwise_volume':
        from confirmed_pairwise_entry import confirmed_frame
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            result[symbol]=confirmed_frame(sig.close.reindex(valid),v).target.reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('reset_pairwise_volume','reset_pair_order_volume','calibrated_pair_order_volume'):
        from calibrated_order_signal import reset_signal
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            result[symbol]=reset_signal(sig.close.reindex(valid),v,name).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('segmented_price','segmented_volume'):
        from segmented_trend_strength import segmented_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            score=segmented_frame(sig.close.reindex(valid),v,joint=name.endswith('_volume')).strength
            result[symbol]=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('pair_order_price','pair_order_volume'):
        from pair_order_strength import order_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            score=order_frame(sig.close.reindex(valid),v,joint=name.endswith('_volume')).strength
            result[symbol]=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('short_reversal_pairwise_volume','short_half_pairwise_volume','short_restore_pairwise_volume'):
        from pairwise_trend_strength import pairwise_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        from trend_exit_disagreement import features
        from short_reversal_state import short_reversal_state
        from short_half_state import short_half_state
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid);c=sig.close.reindex(valid)
            base=strength_exposure(pairwise_frame(c,v).strength)
            state_fn=(lambda b,f:short_half_state(b,f,restore=True)) if name=='short_restore_pairwise_volume' else short_half_state if name=='short_half_pairwise_volume' else short_reversal_state
            result[symbol]=state_fn(base,features(c,v).fast5).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name == 'volume_clock_pairwise':
        from volume_clock_strength import volume_clock_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            result[symbol]=strength_exposure(volume_clock_frame(sig.close.reindex(valid),v).strength).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('pairwise_price','pairwise_volume','uniform_pairwise_price','uniform_pairwise_volume'):
        from pairwise_trend_strength import pairwise_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            score=pairwise_frame(sig.close.reindex(valid),v,joint=name.endswith('_volume'),recency=not name.startswith('uniform_')).strength
            result[symbol]=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('range_direction_price','range_direction_volume','close_direction_price','close_direction_volume'):
        from range_direction_strength import range_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            score=range_frame(sig.reindex(valid),v,joint=name.endswith('_volume'),close_only=name.startswith('close_')).strength
            result[symbol]=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('cumulative_price','cumulative_volume'):
        from cumulative_trend_strength import cumulative_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            score=cumulative_frame(sig.close.reindex(valid),v,joint=name=='cumulative_volume').strength
            result[symbol]=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name=='calibrated_local_price':
        from calibrated_local_trend import calibrated_frame
        from geometric_strength import strength_exposure
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            score=calibrated_frame(sig.close.reindex(valid)).strength
            result[symbol]=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('local_trend_price','local_trend_volume'):
        from local_trend_strength import local_trend_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            score=local_trend_frame(sig.close.reindex(valid),v,joint=name=='local_trend_volume').strength
            result[symbol]=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('markov_price_map','markov_volume_map','memoryless_price_map','student_price_map','student_volume_map'):
        from markov_trend_strength import markov_frame
        from markov_state_execution import map_state_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            frame=markov_frame(sig.close.reindex(valid),v,joint=name in ('markov_volume_map','student_volume_map'),memory=name!='memoryless_price_map',student=name.startswith('student_'))
            result[symbol]=map_state_exposure(frame).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('markov_price','markov_volume','memoryless_price'):
        from markov_trend_strength import markov_frame
        from geometric_strength import strength_exposure
        from volume_units import split_consistent_volume
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            score=markov_frame(sig.close.reindex(valid),v,joint=name=='markov_volume',memory=name!='memoryless_price').strength
            result[symbol]=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('confirmed_swing_structure','developing_swing_structure','envelope_swing_structure'):
        from swing_structure_strength import swing_frame
        from geometric_strength import strength_exposure
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            score,_=swing_frame(sig.close.reindex(valid),developing=name=='developing_swing_structure',envelope=name=='envelope_swing_structure')
            result[symbol]=strength_exposure(score.strength).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('path_efficiency_price','path_efficiency_volume','fixed_path_baseline'):
        from path_efficiency_strength import path_efficiency_frame
        from volume_units import split_consistent_volume
        from geometric_strength import strength_exposure
        result={}
        for symbol,a in assets.items():
            raw=a['raw'];sig=a['signal'];valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(sig.index)
            v=split_consistent_volume(raw.volume,a.get('splits',[])).reindex(valid)
            score=path_efficiency_frame(sig.close.reindex(valid),v,joint=name.endswith('volume'),fixed=name=='fixed_path_baseline').strength
            result[symbol]=strength_exposure(score).reindex(sig.index,method='ffill').fillna(0)
        return result
    if name in ('anchored_price_volume','anchored_neutral_price_volume'):
        from anchored_trend_strength import anchored_strength_frame
        from volume_units import split_consistent_volume
        from geometric_strength import strength_exposure
        result={}
        for symbol,asset in assets.items():
            raw=asset['raw'];signal=asset['signal']
            valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(signal.index)
            volume=split_consistent_volume(raw.volume,asset.get('splits',[]))
            score=anchored_strength_frame(signal.close.reindex(valid),volume.reindex(valid),neutral='neutral' in name).strength
            result[symbol]=strength_exposure(score).reindex(signal.index,method='ffill').fillna(0)
        return result
    if name=='multiscale_price_volume':
        from multiscale_trend_strength import multiscale_frame
        from volume_units import split_consistent_volume
        from geometric_strength import strength_exposure
        result={}
        for symbol,asset in assets.items():
            raw=asset['raw'];signal=asset['signal']
            valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(signal.index)
            volume=split_consistent_volume(raw.volume,asset.get('splits',[]))
            score=multiscale_frame(signal.close.reindex(valid),volume.reindex(valid)).strength
            result[symbol]=strength_exposure(score).reindex(signal.index,method='ffill').fillna(0)
        return result
    if name in ('geometry_price_volume_split_units','linear_geometry_price_volume_split_units','adaptive_geometry_price_volume_split_units'):
        from volume_units import split_consistent_volume
        normalized={}
        for symbol,asset in assets.items():
            raw=asset['raw'].copy()
            raw['volume']=split_consistent_volume(raw.volume,asset.get('splits',[]))
            normalized[symbol]=dict(asset,raw=raw)
        # Signal input only. The caller's original raw volume still governs
        # actual share participation, fills, fees and split accounting.
        return build_signals(normalized,name.removesuffix('_split_units'))
    if name in ('geometry_price','geometry_price_volume','linear_geometry_price','linear_geometry_price_volume','adaptive_geometry_price','adaptive_geometry_price_volume'):
        from geometric_strength import geometric_frame,strength_exposure
        from adaptive_geometric_strength import adaptive_frame
        result={}
        for symbol,asset in assets.items():
            raw=asset['raw'];signal=asset['signal']
            valid=raw.index[raw.volume.gt(0)&raw.close.gt(0)].intersection(signal.index)
            close=signal.close.reindex(valid);price=raw.close.reindex(valid);volume=raw.volume.reindex(valid)
            if name.startswith('adaptive_'):
                strength=adaptive_frame(close,price,volume,joint=name.endswith('_volume')).strength
            else:
                strength=geometric_frame(close,price,volume,joint=name.endswith('_volume'),degree=1 if name.startswith('linear_') else 2).strength
            result[symbol]=strength_exposure(strength).reindex(signal.index,method='ffill').fillna(0)
        return result
    if name=='channel21_63_staged':
        result={}
        for s,a in assets.items():
            f=a['signal'];base=channel_signal(f,63,True)
            tr=pd.concat([f.high-f.low,(f.high-f.close.shift()).abs(),(f.low-f.close.shift()).abs()],axis=1).max(axis=1)
            atr=tr.rolling(21).mean();stage=0.;threshold=None;values=[]
            for active,close,volatility in zip(base,f.close,atr):
                if not active:stage=0.;threshold=None
                elif stage==0.:stage=.5;threshold=close+2*volatility
                elif stage==.5 and close>=threshold:stage=1.
                values.append(stage)
            result[s]=pd.Series(values,index=f.index)
        return result
    if name=='channel21_63_volume':
        result={}
        for s,a in assets.items():
            proxy=a['raw'].close*a['raw'].volume
            gate=proxy.gt(proxy.shift().rolling(20).mean()) & proxy.gt(0)
            result[s]=channel_signal(a['signal'],63,True,entry_gate=gate)
        return result
    if name=='channel21_63_trailing4atr':return {s:channel_signal(a['signal'],63,initial_protection=True,trailing=True) for s,a in assets.items()}
    if name=='channel21_63_initial2atr':return {s:channel_signal(a['signal'],63,initial_protection=True) for s,a in assets.items()}
    if name in GEOMETRY:return {s:geometry_signal(a['signal'].close,GEOMETRY[name]) for s,a in assets.items()}
    if name in CHANNELS:return {s:channel_signal(a['signal'],CHANNELS[name]) for s,a in assets.items()}
    if name not in HORIZONS:raise ValueError('Unknown registered strategy')
    horizon=HORIZONS[name]
    return {s:a['signal'].close.pct_change(horizon,fill_method=None).gt(0).astype(float) for s,a in assets.items()}


def period_metrics(path,start,end):
    """Carry-in positions: previous portfolio close is the period starting NAV."""
    p=path.loc[start:end];before=path.loc[path.index<p.index[0]]
    initial=float(before.nav.iloc[-1]) if len(before) else 1.
    wealth=p.nav/initial
    peak=wealth.cummax().clip(lower=1.)
    return dict(start=str(p.index[0].date()),end=str(p.index[-1].date()),return_fraction=float(wealth.iloc[-1]-1),max_drawdown=float((wealth/peak-1).min()),
                fees=float(p.fees.sum()),average_cash_weight=float((p.cash/p.nav/1e6).mean()),starting_nav=initial)
