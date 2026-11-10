"""Causal price/volume hypothesis library. Never consumes screenshot labels."""
import numpy as np
import pandas as pd

def configurations():
    out=[]
    for family in ['drift','slope','spread','consensus','cusum']:
      for n in [20,40,63]:
       for volume in ['P','PV']:
        for entry in [1.,1.5,2.]:
         for exit in [0.,.5]:
          for danger in ['none','shock3','trail2']:
           for memory in ['rolling','broken_peak']:
            ident=f'{family}-{n}-{volume}-e{entry:g}-x{exit:g}-{danger}-{memory}'
            out.append(dict(id=ident,family=family,n=n,volume=volume,entry=entry,exit=exit,danger=danger,memory=memory))
    for n in [20,40,63]:
     for background in ['none','positive63']:
      for volume in ['P','PV']:
       for danger in ['trail2','trail3','shock3']:
        for memory in ['rolling','broken_peak']:
         ident=f'breakout-{n}-{volume}-{background}-{danger}-{memory}'
         out.append(dict(id=ident,family='breakout',n=n,volume=volume,entry=0.,exit=0.,danger=danger,memory=memory,background=background))
    assert len(out)==1152 and len({x['id'] for x in out})==1152
    return out

def features(bars):
    logc=np.log(bars.close);r=logc.diff()
    sigma=r.pow(2).shift().rolling(63).mean().pow(.5)
    q=bars.volume/bars.volume.shift().rolling(21).median()
    tr=pd.concat([(bars.high-bars.low)/bars.close.shift(),(bars.high/bars.close.shift()-1).abs(),(bars.low/bars.close.shift()-1).abs()],axis=1).max(axis=1)
    atr=tr.shift().rolling(14).mean()
    f=pd.DataFrame(dict(logc=logc,r=r,sigma=sigma,q=q,atr=atr),index=bars.index)
    for mode in ['P','PV']:
      # Neutral weights only during the unavailable initial q warm-up. Signals
      # remain disabled for64 observations; constant-volume ablation is exact.
      w=pd.Series(1.,index=bars.index) if mode=='P' else np.sqrt(q.clip(.25,4).fillna(1.))
      f['w_'+mode]=w
      for n in [6,13,20,21,40,63]:
        f[f'drift_{n}_{mode}']=(w*r).rolling(n).sum()/(w.pow(2).rolling(n).sum().pow(.5)*sigma)
      for n in [20,40,63]:
        t=np.arange(n,dtype=float);yy=np.lib.stride_tricks.sliding_window_view(logc.to_numpy(),n);ww=np.lib.stride_tricks.sliding_window_view(w.to_numpy(),n)
        sw=ww.sum(axis=1);tx=(ww*t).sum(axis=1)/sw;py=(ww*yy).sum(axis=1)/sw
        beta=(ww*(t-tx[:,None])*(yy-py[:,None])).sum(axis=1)/(ww*(t-tx[:,None])**2).sum(axis=1)
        b=pd.Series(np.r_[np.full(n-1,np.nan),beta],index=bars.index)
        f[f'slope_{n}_{mode}']=b*np.sqrt(n)/sigma
        fast=n//4
        def ew(h):
            return (logc*w).ewm(span=h,adjust=False).mean()/w.ewm(span=h,adjust=False).mean()
        f[f'spread_{n}_{mode}']=(ew(fast)-ew(n))*2*np.sqrt(n)/(n-fast)/sigma
        a=f[f'drift_{max(5,n//3)}_{mode}'];b=f[f'drift_{n}_{mode}']
        f[f'consensus_{n}_{mode}']=np.where(a*b>0,np.sign(a)*np.minimum(a.abs(),b.abs()),0.)
        f.loc[a.isna()|b.isna(),f'consensus_{n}_{mode}']=np.nan
        gp=gm=0.;z=[];decay=1-2/(n+1)
        for rr,ss,weight in zip(r,sigma,w):
            if not (np.isfinite(rr) and np.isfinite(ss) and np.isfinite(weight) and ss>0):z.append(np.nan);continue
            e=weight*rr/ss;gp=max(0.,decay*gp+e-.25);gm=max(0.,decay*gm-e-.25);z.append((gp-gm)/np.sqrt(n))
        f[f'cusum_{n}_{mode}']=z
    for n in [20,40,63]:f[f'ceiling_{n}']=logc.shift().rolling(n).max()
    return f

def simulate(bars,cfg,f=None):
    f=features(bars) if f is None else f
    family='drift' if cfg['family']=='breakout' else cfg['family']
    score=f[f'{family}_{cfg["n"]}_{cfg["volume"]}'].to_numpy()
    c=f.logc.to_numpy();r=f.r.to_numpy();atr=f.atr.to_numpy();sig=f.sigma.to_numpy();q=f.q.to_numpy();w=f['w_'+cfg['volume']].to_numpy()
    ceiling=f[f'ceiling_{cfg["n"]}'].to_numpy();background=f[f'drift_63_{cfg["volume"]}'].to_numpy()
    rows=[];active=False;peak=stop=entryc=entrysig=work=peakwork=np.nan;broken=-np.inf;had_entry=False;age=0
    for i in range(len(bars)):
        entered=exited=0;reason='';s=score[i]
        valid=i>=64 and np.isfinite(s) and np.isfinite(atr[i]) and atr[i]>0
        shock=valid and -r[i]>=3*atr[i]/(np.sqrt(np.clip(q[i],.25,4)) if cfg['volume']=='PV' else 1.)
        if active:
            peak=max(peak,c[i]);age+=1;work+=w[i]*r[i];peakwork=max(peakwork,work)
            if cfg['danger'].startswith('trail'):
                stop=max(stop,peak-float(cfg['danger'][5:])*atr[i])
            falling=valid and s<=cfg['exit'];danger=valid and ((cfg['danger']=='shock3' and shock) or (cfg['danger'].startswith('trail') and c[i]<=stop))
            if falling or danger:
                active=False;exited=1;reason='evidence_cool' if falling else cfg['danger'];broken=max(broken,peak)
        else:
            entry=valid and s>=cfg['entry']
            if cfg['family']=='breakout':entry=entry and c[i]>ceiling[i] and (cfg['background']=='none' or background[i]>0)
            if cfg['memory']=='broken_peak':entry=entry and (not had_entry or c[i]>broken)
            if entry and not (cfg['danger']=='shock3' and shock):
                active=True;entered=1;reason='new_evidence';peak=entryc=c[i];entrysig=sig[i];work=peakwork=0.;age=0;had_entry=True
                stop=peak-float(cfg['danger'][5:])*atr[i] if cfg['danger'].startswith('trail') else -np.inf
        progress=c[i]-entryc if active else np.nan
        rows.append((int(active),entered,exited,s,float(np.exp(stop)) if active and np.isfinite(stop) else np.nan,
            progress,(peak-entryc) if active else np.nan,(peak-entryc)/entrysig if active else np.nan,peakwork/entrysig if active else np.nan,age if active else np.nan,reason))
    return pd.DataFrame(rows,index=bars.index,columns=['target','entered','exited','score','floor','advance','peak_advance','normalized_peak','volume_peak','age','reason'])

def add_progress(bars,state):
    """Autonomous anchors for old saved controls, also never source starts."""
    f=features(bars);entry=peak=sigma=work=peakwork=np.nan;last=False;rows=[];age=0
    for i,(dt,row) in enumerate(state.iterrows()):
        active=bool(row.target);c=f.logc.loc[dt]
        if active and not last:entry=peak=c;sigma=f.sigma.loc[dt];work=peakwork=0.;age=0
        elif active:peak=max(peak,c);work+=f.w_PV.loc[dt]*f.r.loc[dt];peakwork=max(peakwork,work);age+=1
        rows.append((c-entry,peak-entry,(peak-entry)/sigma,peakwork/sigma,age) if active else (np.nan,)*5);last=active
    return state.join(pd.DataFrame(rows,index=state.index,columns=['advance','peak_advance','normalized_peak','volume_peak','age']))
