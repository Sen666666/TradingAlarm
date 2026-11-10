"""Array execution of the exact old one-asset base rule; no stock selection."""
from common import *

def run(d,s,initial,guard=True,events=True):
 o=d.open.to_numpy(float);c=d.close.to_numpy(float);target=s.target.to_numpy(bool);floor=s.floor.to_numpy(float);buy=s.buy_event.to_numpy(bool) if events else target;cash=1.;qty=0.;pending=('buy',0,float(initial['floor']),-1) if initial['active'] else None;entry=None;trades=[];nav=[];held=[];gap=0;fee=.0005;slip=.0005
 for i in range(len(d)):
  washeld=qty>0
  if pending and pending[0]=='buy' and i>0 and not target[i-1]:pending=None
  if pending and pending[1]<=i:
   side,due,f,sig=pending;pending=None
   if side=='buy' and guard and o[i]<=f:gap+=1
   elif side=='buy' and qty==0:
    px=o[i]+o[i]*slip;capital=cash;qty=cash/(px*(1+fee));cash=0.;entry=(i,sig,capital);washeld=True
   elif side=='sell' and qty>0:
    px=o[i]-o[i]*slip;cash+=qty*px*(1-fee);trades.append(dict(entry_i=entry[0],entry_signal_i=entry[1],exit_i=i,net_return=cash/entry[2]-1,net_pnl=cash-entry[2],terminal=False));qty=0.;entry=None
  if qty>0 and not target[i] and pending is None:pending=('sell',i+1,floor[i],i)
  elif qty==0 and target[i] and pending is None and buy[i]:pending=('buy',i+1,floor[i],i)
  elif pending and pending[0]=='buy' and not target[i]:pending=None
  if i==len(d)-1:
   pending=None
   if qty>0:
    px=c[i]-c[i]*slip;cash+=qty*px*(1-fee);trades.append(dict(entry_i=entry[0],entry_signal_i=entry[1],exit_i=i,net_return=cash/entry[2]-1,net_pnl=cash-entry[2],terminal=True));qty=0.;entry=None
  nav.append(cash+qty*c[i]);held.append(washeld or qty>0)
 a=np.array(nav);dd=a/np.maximum.accumulate(np.r_[1.,a])[1:]-1
 return dict(net_return=a[-1]-1,max_drawdown=-dd.min(),trades=len(trades),wins=sum(t['net_return']>0 for t in trades),gap_cancels=gap,exposure=np.mean(held)),np.array(nav),trades

def frames(f,policy):
 x=f.loc[START:END];n=f.index.searchsorted(START);prev=f.iloc[n-1] if n>0 else None
 pref='ix' if policy=='IX' else 'e0';s=pd.DataFrame(dict(target=x[pref+'_target'],floor=x[pref+'_floor'],buy_event=x.IX if policy=='IX' else x.e0_target),index=x.index)
 active=bool(prev[pref+'_target']) if prev is not None else False
 if policy=='IX':active=active and bool(prev.strength_ready) and prev.grade>=2
 ini=dict(active=active,floor=float(prev[pref+'_floor']) if active else None)
 return x,s,ini
