"""Causal research indicators and next-open, long/cash backtests.

The seven labels describe an experimental model, not Trend Animal's formula.
Adjusted OHLC simulations require separately verified adjustment semantics.
"""
import math
import numpy as np
import pandas as pd

def frame(rows):
    df = pd.DataFrame(rows).set_index('date').sort_index()
    df.index = pd.to_datetime(df.index)
    if df.index.has_duplicates:
        raise ValueError('Duplicate dates')
    cols = ['open','high','low','close']
    if len(df) < 253 or not np.isfinite(df[cols].to_numpy()).all():
        raise ValueError('Insufficient or nonfinite OHLC')
    if (df[cols] <= 0).any().any():
        raise ValueError('Nonpositive prices')
    if ((df.high < df[cols].max(axis=1)) | (df.low > df[cols].min(axis=1))).any():
        raise ValueError('Inconsistent OHLC')
    return df

def features(df, fast=20, slow=60):
    logp = np.log(df.close)
    r = logp.diff()
    vol = r.rolling(slow).std(ddof=1)
    denom = vol.replace(0,np.nan)
    ema_fast = logp.ewm(span=fast,adjust=False).mean()
    ema_slow = logp.ewm(span=slow,adjust=False).mean()
    direction = (ema_fast-ema_slow)/(denom*math.sqrt(fast))
    momentum = logp.diff(slow)/(denom*math.sqrt(slow))
    score = .5*direction+.5*momentum
    tr = pd.concat([df.high-df.low,(df.high-df.close.shift()).abs(),(df.low-df.close.shift()).abs()],axis=1).max(axis=1)
    out = pd.DataFrame({'score':score,'atr':tr.rolling(20).mean(),'vol_ratio':r.rolling(20).std()/denom,'momentum':momentum,'direction':direction})
    out['temperature'] = 'unknown'
    valid = score.notna()
    out.loc[valid & (score.abs()<.25),'temperature']='平'
    out.loc[valid & (score>=.25),'temperature']='温'
    out.loc[valid & (score>=.75),'temperature']='热'
    out.loc[valid & (score<=-.25),'temperature']='凉'
    out.loc[valid & (score<=-.75),'temperature']='寒'
    out.loc[valid & (score>=1.75) & (out.vol_ratio>=1.25),'temperature']='沸'
    out.loc[valid & (score<=-1.75) & (out.vol_ratio>=1.25),'temperature']='冻'
    return out

def signals(df, variant='v1', fast=20, slow=60, entry=.75):
    f = features(df,fast,slow)
    s = f.score
    enter = (s>=entry) & (s.shift()>=entry)
    leave = (s<=0) & (s.shift()<=0)
    held, peak, targets = False, 0., []
    for i, row in enumerate(df.itertuples()):
        if held:
            peak = max(peak,row.close)
            stopped = variant != 'no_stop' and row.close < peak-3*f.atr.iloc[i]
            if bool(leave.iloc[i]) or stopped:
                held = False
        elif bool(enter.iloc[i]):
            held, peak = True,row.close
        targets.append(float(held))
    f['target'] = targets
    return f

def baselines(df):
    result = pd.DataFrame(index=df.index)
    result['buy_hold'] = 1.
    result['sma200'] = (df.close>df.close.rolling(200).mean()).astype(float)
    result['momentum252'] = (df.close>df.close.shift(252)).astype(float)
    # Close-confirmed breakout adaptation, not exact intraday Turtle replication.
    high = df.high.shift().rolling(55).max()
    low = df.low.shift().rolling(20).min()
    held, values = False,[]
    for c,h,l in zip(df.close,high,low):
        if held and c<l:
            held=False
        elif not held and c>h:
            held=True
        values.append(float(held))
    result['donchian55_20'] = values
    return result

def structure_change_v2(df):
    """Exploratory revision: separate slow structure from fast change alerts.

    Fixed 3/6/12-month horizons, no per-asset fitting. Not a proprietary replica.
    Entry/exit hysteresis avoids using short-term acceleration as a liquidation
    rule. Parameters were proposed after v1's historical results were viewed.
    """
    lp=np.log(df.close)
    vol=lp.diff().rolling(60).std().replace(0,np.nan)
    distances=pd.concat([(lp-lp.ewm(span=h,adjust=False).mean())/(vol*math.sqrt(h)) for h in (63,126,252)],axis=1)
    score=distances.median(axis=1)
    change=lp.diff(20)/(vol*math.sqrt(20))
    enter=(score>.1)&(score.shift()>.1)
    leave=(score<-.1)&(score.shift()<-.1)
    held=False
    target=[]
    for buy,sell in zip(enter,leave):
        if held and sell:
            held=False
        elif not held and buy:
            held=True
        target.append(float(held))
    return pd.DataFrame({'structure':score,'change':change,'target':target},index=df.index)

def backtest(df, target, start=None, end=None, cost_bps=5):
    """Close signal on t is executed at t+1 open, then marked at close.

    Fractional holdings, zero cash yield. No forced terminal liquidation.
    This generic ETF approximation does not model board lots, daily price-limit
    queues, stamp-duty schedules, suspensions or FX conversion.
    """
    if not target.index.equals(df.index) or not target.isin([0.,1.]).all():
        raise ValueError('Target must be aligned long/cash series')
    eligible = df.index >= df.index[252]
    if start:
        eligible &= df.index >= pd.Timestamp(start)
    if end:
        eligible &= df.index <= pd.Timestamp(end)
    dates=df.index[eligible]
    equity, pos, previous_close = 1.,0.,None
    history=[]
    decision = target.shift(1).fillna(0)
    for date in dates:
        row=df.loc[date]
        before=equity
        if previous_close is not None:
            equity *= 1+pos*(row.open/previous_close-1)
        desired=float(decision.loc[date])
        turnover=abs(desired-pos)
        equity *= 1-turnover*cost_bps/10000
        pos=desired
        equity *= 1+pos*(row.close/row.open-1)
        history.append({'date':date,'nav':equity,'return':equity/before-1,'position':pos,'turnover':turnover})
        previous_close=row.close
    path=pd.DataFrame(history).set_index('date')
    if len(path)<2:
        raise ValueError('Insufficient evaluation interval')
    nav=path.nav
    peak=np.maximum.accumulate(np.r_[1.,nav.to_numpy()])[1:]
    dd=nav.to_numpy()/peak-1
    years=max((path.index[-1]-path.index[0]).days/365.25,1/252)
    cagr=float(nav.iloc[-1]**(1/years)-1)
    daily=path['return']
    sd=float(daily.std(ddof=1))
    mdd=float(dd.min())
    underwater=max_underwater=0
    for value in dd:
        underwater = underwater+1 if value < -1e-10 else 0
        max_underwater=max(max_underwater,underwater)
    metrics={'start':str(path.index[0].date()),'end':str(path.index[-1].date()),'days':len(path),'total_return':float(nav.iloc[-1]-1),'cagr':cagr,'max_drawdown':mdd,'sharpe':float(daily.mean()/sd*math.sqrt(252)) if sd else None,'calmar':cagr/abs(mdd) if mdd else None,'exposure':float(path.position.mean()),'entries':int(((path.position.diff().fillna(path.position.iloc[0]))>0).sum()),'turnover':float(path.turnover.sum()),'max_underwater_sessions':int(max_underwater),'cost_bps_per_side':cost_bps,'terminal_position':float(path.position.iloc[-1])}
    path['drawdown']=dd
    return metrics,path
