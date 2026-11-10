import math
import numpy as np
import pandas as pd

def run(f,revision=1,price_only=False):
 rows=[]
 for seg,b in f.groupby('segment_id',sort=False):
  C=b.close.to_numpy(float);D=b.amount.to_numpy(float);r=np.r_[np.nan,np.diff(np.log(C))]
  s=pd.Series(r*r).shift().rolling(63,min_periods=63).mean().pow(.5).clip(lower=1e-8).to_numpy();base=pd.Series(D).where(np.isfinite(D)&(D>0)).shift().rolling(21,min_periods=21).median().to_numpy()
  d=-1;e=None;F=Q=0.;temp=0;support=math.nan;active=False;ca=False;cf=math.nan;up_anchor=math.nan;up_scale=math.nan;mu=0.
  for i,t in enumerate(b.index):
   c=C[i];validD=np.isfinite(D[i]) and D[i]>0;ready=np.isfinite(s[i]) and (price_only or np.isfinite(base[i]));ev=0;pivot=math.nan;fresh=False;shock=False;delta=weight=0.;ex=ce=False;why='unprepared'
   q=D[i]/base[i] if validD and np.isfinite(base[i]) else math.nan
   if i and np.isfinite(r[i]):mu=(1-2/22)*mu+(2/22)*r[i]*(1 if price_only else min(1,math.sqrt(q)) if np.isfinite(q) else 0)
   if active and c<=support:active=False;ex=True
   if ca and c<=cf:ca=False;ce=True
   usedF=usedQ=0.;threshold=math.nan
   if ready:
    if e is None:e=i
    shock=r[i]<=-2*s[i] and (price_only or (np.isfinite(q) and q>=2))
    if shock:
     temp=-2;d=-1;e=i;F=Q=0.;why='large_directional_decline'
    else:
     newext=(d==-1 and c<C[e]) or (d==1 and c>C[e]);was_up=d==1
     if newext:
      e=i;F=Q=0.
      if was_up:fresh=True
     if i>e:
      x=(-d)*math.log(c/C[e]);delta=max(0.,x-F);F=max(F,x)
      weight=1. if price_only else min(1.,math.sqrt(D[i]/base[e])) if validD and np.isfinite(base[e]) else 0.
      Q+=delta*weight;threshold=math.sqrt(5)*s[e];usedF=F;usedQ=Q
      if delta>0 and F>=threshold and Q>=threshold:
       ev=-d;pivot=C[e]
       if ev==1:
        up_anchor=pivot;up_scale=s[e];fresh=True;temp=2
       else:temp=-2
       d=ev;e=i;F=Q=0.;why='up_confirmation' if ev==1 else 'down_confirmation'
     if revision>=3 and ev==-1 and mu>0:temp=1;why='local_pullback_positive_medium_progress'
     if revision>=3 and d==-1 and mu<=0:temp=-2;why='down_leg_negative_medium_progress'
     if revision>=2 and temp>=2 and mu<=0:temp=1;why='local_rebound_negative_medium_progress'
     if revision>=2 and d==1 and fresh and mu>0 and temp<2:temp=2;why='new_high_positive_medium_progress'
     if temp>=2 and np.isfinite(up_anchor):temp=3 if math.log(c/up_anchor)>=math.sqrt(21)*up_scale else 2
     if why=='unprepared':why='fresh_up_frontier' if fresh else 'wait_new_price_evidence'
    if ev==1:
     if active:support=max(support,pivot)
     elif not ex:active=True;support=pivot
    if ca and (not active or temp<=-2):ca=False;ce=True
    if ca and active:cf=max(cf,support)
    warm=temp>=2
    if not ca and not ce and active and warm and fresh:ca=True;cf=support
   warm=temp>=2
   rows.append(dict(date=t,segment_id=seg,ready=int(ready),event=ev,pivot=pivot,grade=temp,shock=int(shock),fresh_up=int(fresh),reason=why,q=q,scale=s[i],mu21=mu,frontier=usedF,credit=usedQ,delta_frontier=delta,weight=weight,threshold=threshold,h_target=int(active),h_floor=support if active or ex else math.nan,h_buy=bool(active and warm and fresh and not ex),c_target=int(ca),c_floor=cf if ca or ce else math.nan,c_buy=bool(ca and warm and fresh and not ce)))
 return pd.DataFrame(rows).set_index('date')
