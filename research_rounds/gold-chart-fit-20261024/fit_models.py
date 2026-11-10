"""Finite screenshot imitation controls. No accounts, orders or profitability fit."""
import numpy as np
import pandas as pd

def configurations():
    out=[]
    for n in [10,20,40]:
        for band in [0,.5,1]:out.append(dict(id=f'ema-{n}-{band}',family='EMA',n=n,band=band))
    for n in [10,20,40]:
        for m in [5,10,20]:out.append(dict(id=f'channel-{n}-{m}',family='Channel',n=n,m=m))
    for n in [10,20,40]:
        for k in [1.5,2,2.5,3]:out.append(dict(id=f'trail-{n}-{k}',family='ATR',n=n,k=k))
    for n in [10,20,40]:
        for k in [2,3]:out.append(dict(id=f'volume-trail-{n}-{k}',family='VolumeATR',n=n,k=k))
    assert len(out)==36
    return out

def model(bars,cfg):
    c=bars.close.astype(float);prev=c.shift()
    tr=pd.concat([bars.high-bars.low,(bars.high-prev).abs(),(bars.low-prev).abs()],axis=1).max(axis=1)
    atr=tr.shift().rolling(14).mean()
    ceiling=c.shift().rolling(cfg['n']).max();channel=c.shift().rolling(cfg.get('m',5)).min()
    ema=c.ewm(span=cfg['n'],adjust=False).mean()
    q=bars.volume/bars.volume.shift().rolling(21).median()
    clv=((c-bars.low)/(bars.high-bars.low)).fillna(.5)
    active=False;peak=stop=np.nan;out=[]
    for i,dt in enumerate(bars.index):
        entered=exited=0
        if i>=64:
            if cfg['family']=='EMA':
                floor=ema.iloc[i]-cfg['band']*atr.iloc[i]
                entry=c.iloc[i]>ema.iloc[i]+cfg['band']*atr.iloc[i]
            elif cfg['family']=='Channel':floor=channel.iloc[i];entry=c.iloc[i]>ceiling.iloc[i]
            else:
                if active:
                    peak=max(peak,c.iloc[i]);stop=max(stop,peak-cfg['k']*atr.iloc[i])
                floor=stop;entry=c.iloc[i]>ceiling.iloc[i]
                if cfg['family']=='VolumeATR':entry=entry and q.iloc[i]>=1.5 and clv.iloc[i]>=2/3
            if active and c.iloc[i]<=floor:active=False;exited=1
            if not active and not exited and entry:
                active=True;entered=1;peak=c.iloc[i]
                if cfg['family'] in ['ATR','VolumeATR']:stop=peak-cfg['k']*atr.iloc[i];floor=stop
            out.append((int(active),entered,exited,float(floor) if active or exited else np.nan))
        else:out.append((0,0,0,np.nan))
    return pd.DataFrame(out,index=bars.index,columns=['target','entered','exited','floor'])

def match_events(predicted,targets,penalty=30):
    """Order-preserving edit-distance matching, separate starts and ends.

    A skipped reference or extra model event costs 30 observations. A match
    costs distance outside the target uncertainty interval. Nothing is silently
    matched to a remote event for an unpenalized nearest-neighbor statistic.
    """
    n,m=len(predicted),len(targets);d=np.zeros((n+1,m+1));back={}
    d[:,0]=np.arange(n+1)*penalty;d[0,:]=np.arange(m+1)*penalty
    for i in range(1,n+1):back[i,0]='extra'
    for j in range(1,m+1):back[0,j]='missing'
    for i,p in enumerate(predicted,1):
      for j,t in enumerate(targets,1):
        distance=max(t['index']-t['uncertainty_observations']-p,0,p-t['index']-t['uncertainty_observations'])
        options=[(d[i-1,j-1]+distance,'match'),(d[i-1,j]+penalty,'extra'),(d[i,j-1]+penalty,'missing')]
        d[i,j],back[i,j]=min(options,key=lambda a:a[0])
    i,j=n,m;rows=[]
    while i or j:
        action=back[i,j]
        if action=='match':
            p=predicted[i-1];t=targets[j-1]
            rows.append(dict(action=action,predicted_index=p,target_id=t['id'],target_index=t['index'],offset=p-t['index'],outside_band=max(abs(p-t['index'])-t['uncertainty_observations'],0)));i-=1;j-=1
        elif action=='extra':rows.append(dict(action=action,predicted_index=predicted[i-1]));i-=1
        else:rows.append(dict(action=action,target_id=targets[j-1]['id'],target_index=targets[j-1]['index']));j-=1
    return float(d[n,m]),rows[::-1]

def evaluate(state,points,index,penalty=30,uncertainty=None):
    p=[dict(x) for x in points]
    if uncertainty is not None:
        for x in p:
            if x['uncertainty_observations']:x['uncertainty_observations']=uncertainty
    truth=np.zeros(len(index),int);known=np.ones(len(index),bool)
    for a,b in zip(p[::2],p[1::2]):truth[a['index']:b['index']]=1
    for x in p:
        u=x['uncertainty_observations']
        if u:known[max(0,x['index']-u):min(len(index),x['index']+u+1)]=False
    mismatch=float(np.mean(state.target.to_numpy()[known]!=truth[known]));loss=0;matches=[]
    for kind,col in [('start','entered'),('end','exited')]:
        cost,rows=match_events(np.flatnonzero(state[col]).tolist(),[x for x in p if x['kind']==kind],penalty)
        loss+=cost;matches.extend([dict(kind=kind,**r) for r in rows])
    matched=[r for r in matches if r['action']=='match']
    summary=dict(score=.5*mismatch+.5*loss/(penalty*len(p)),state_mismatch=mismatch,event_edit_cost=loss,
      starts=int(state.entered.sum()),ends=int(state.exited.sum()),carry_in=int(bool(state.target.iloc[0] and not state.entered.iloc[0])),
      active_days=int(state.target.sum()),known_state_days=int(known.sum()),matched_events=len(matched),
      within_target_band=sum(r['outside_band']==0 for r in matched),extras=sum(r['action']=='extra' for r in matches),missing=sum(r['action']=='missing' for r in matches),
      matched_mean_absolute_offset=float(np.mean([abs(r['offset']) for r in matched])) if matched else None)
    return summary,matches
