"""Interval-aware observed-series relative directional change + mechanical M3-completion cache."""
from decimal import Decimal as D,localcontext,Context,ROUND_FLOOR,ROUND_CEILING,ROUND_HALF_EVEN
from fractions import Fraction as F
from collections import deque
import math
import numpy as np
import pandas as pd
PREC=70
DN=Context(prec=PREC,rounding=ROUND_FLOOR);UP=Context(prec=PREC,rounding=ROUND_CEILING);NEAR=Context(prec=PREC,rounding=ROUND_HALF_EVEN)
ZERO=D(0)
def divfrac(v,ctx):
 with localcontext(ctx):return D(v.numerator)/D(v.denominator)
def logfrac(v,lower):
 ctx=DN if lower else UP
 q=divfrac(v,ctx)
 with localcontext(NEAR):
  z=q.ln()
  return z.next_minus() if lower else z.next_plus()
def bounds(v):
 f=F.from_float(float(v));prev=F.from_float(math.nextafter(float(v),-math.inf));nxt=F.from_float(math.nextafter(float(v),math.inf))
 return (f+prev)/2,(f+nxt)/2
def obs(c,s,j):
 cl,ch=bounds(c);sl,sh=bounds(s)
 return dict(mid=F.from_float(float(c))/F.from_float(float(s)),lo=cl/sh,hi=ch/sl,j=j)
def delta(a,b):
 if a['j']==b['j']:return ZERO,ZERO
 return logfrac(a['lo']/b['hi'],True),logfrac(a['hi']/b['lo'],False)
def squares(lo,hi):
 with localcontext(DN):low=ZERO if lo<=0<=hi else min(lo*lo,hi*hi)
 with localcontext(UP):high=max(lo*lo,hi*hi)
 return low,high
def order(a,b):
 # Exact equality is an explicit observed-ratio convention, not proof underlying uncertain prices are equal.
 if a['mid']==b['mid']:return 0
 if a['lo']>b['hi']:return 1
 if a['hi']<b['lo']:return -1
 return None
def crossing(a,b,q):
 lo,hi=delta(a,b);ql,qh=q
 if lo>=0:
  with localcontext(DN):ls=lo*lo
  if ls>=qh:return True
 if hi<0:return False
 with localcontext(UP):hs=hi*hi
 if hs<ql:return False
 return None
def relative_clock(stock,sector,valid):
 n=len(stock)
 if len(sector)!=n or len(valid)!=n:raise ValueError('Mismatched price/valid lengths')
 if any(not isinstance(v,(bool,np.bool_,int,np.integer)) or v not in (0,1) for v in valid):raise ValueError('valid must contain explicit known boolean values')
 hist=deque();phase=0;low=high=None;lq=hq=None;prev=None;lastup=lastdown=-1;rows=[]
 def reset():return 0,None,None,None,None,-1,-1
 for j,(c,s,ok) in enumerate(zip(stock,sector,valid)):
  event=0;reason='';ql=qh=None;o=None;eventq=None
  if not np.isfinite(c) or not np.isfinite(s) or c<=0 or s<=0 or not math.isfinite(math.nextafter(float(c),math.inf)) or not math.isfinite(math.nextafter(float(s),math.inf)):
   hist.clear();prev=None;phase,low,high,lq,hq,lastup,lastdown=reset();reason='INVALID_OR_UNBOUNDED_PRICE'
  else:
   o=obs(c,s,j)
   if not ok or prev is None:
    hist.clear();phase,low,high,lq,hq,lastup,lastdown=reset();reason='SOURCE_OR_GAP_RESET'
   else:
    elo,ehi=delta(o,prev);sq=squares(elo,ehi)
    if len(hist)==63:
     with localcontext(DN):ql=sum((v[0] for v in hist),ZERO)*D(5)/D(63)
     with localcontext(UP):qh=sum((v[1] for v in hist),ZERO)*D(5)/D(63)
     if ql<=0:
      phase,low,high,lq,hq,lastup,lastdown=reset();reason='ZERO_OR_UNRESOLVED_SCALE'
     else:
      q=(ql,qh)
      if low is None:low=high=o;lq=hq=q
      if phase==0:
       ol=order(o,low);oh=order(o,high)
       if ol is None or oh is None:reason='UNRESOLVED_EXTREME_ORDER'
       else:
        if ol<0:low=o;lq=q
        if oh>0:high=o;hq=q
        u=crossing(o,low,lq);dn=crossing(high,o,hq)
        if u is None or dn is None:reason='UNRESOLVED_THRESHOLD'
        elif u:eventq=lq;phase=1;event=1;lastup=j;high=o;hq=q
        elif dn:eventq=hq;phase=-1;event=-1;lastdown=j;low=o;lq=q
      elif phase==1:
       oh=order(o,high)
       if oh is None:reason='UNRESOLVED_EXTREME_ORDER'
       else:
        if oh>0:high=o;hq=q
        dn=crossing(high,o,hq)
        if dn is None:reason='UNRESOLVED_THRESHOLD'
        elif dn:phase=-1;event=-1;lastdown=j;low=o;lq=q
      else:
       ol=order(o,low)
       if ol is None:reason='UNRESOLVED_EXTREME_ORDER'
       else:
        if ol<0:low=o;lq=q
        u=crossing(o,low,lq)
        if u is None:reason='UNRESOLVED_THRESHOLD'
        elif u:phase=1;event=1;lastup=j;high=o;hq=q
      if reason:
       phase,low,high,lq,hq,lastup,lastdown=reset();event=0
    else:
     phase,low,high,lq,hq,lastup,lastdown=reset();reason='WARMUP63_PRIOR_RETURNS'
    hist.append(sq)
    if len(hist)>63:hist.popleft()
   prev=o
  rows.append(dict(relative_phase=phase if not reason else np.nan,relative_event=event,relative_known=not bool(reason),relative_reason=reason,last_up_index=lastup,last_down_index=lastdown,low_index=low['j'] if low else -1,high_index=high['j'] if high else -1,current_scale_squared_lower=float(ql) if ql is not None else np.nan,current_scale_squared_upper=float(qh) if qh is not None else np.nan,low_frozen_q_lower=float(lq[0]) if lq else np.nan,low_frozen_q_upper=float(lq[1]) if lq else np.nan,high_frozen_q_lower=float(hq[0]) if hq else np.nan,high_frozen_q_upper=float(hq[1]) if hq else np.nan,event_frozen_q_lower=float(eventq[0]) if eventq else np.nan,event_frozen_q_upper=float(eventq[1]) if eventq else np.nan))
 return pd.DataFrame(rows)
def truth(x):return pd.notna(x) and x in (True,1)
def cached_receipts(frame,start,end,arm='CACHED',position=None,calendar=None):
 """position is causal close-after-open-action stock state. Default FLAT is explicitly signal-only."""
 if calendar is None or not frame.index.equals(pd.DatetimeIndex(calendar)) or not frame.index.is_unique or not frame.index.is_monotonic_increasing:raise ValueError('Frame must cover the explicit complete ordered common calendar')
 pending=None;events=[];trace=[];positive=0
 for j,(d,r) in enumerate(frame.iterrows()):
  pos=position.get(d,'UNKNOWN') if position is not None else 'FLAT'
  mk=truth(r.M3_known) and pd.notna(r.M3) and r.M3 in (True,False,0,1);rk=truth(r.relative_known) and pd.notna(r.relative_event) and r.relative_event in (-1,0,1);mu=r.mu5;positive=min(3,positive+1) if np.isfinite(mu) and mu>0 else 0
  active=start<=d<=end
  cancellation=None;action='WAIT' if pending is not None else 'NONE';origin=pending['origin'] if pending else None;deadline=pending['deadline'] if pending else None;cancel_origin=None;cancel_deadline=None
  if pending is not None:
   if not active:cancellation='OUTSIDE_BIRTH_WINDOW'
   elif pos!='FLAT':cancellation='POSITION_NOT_FLAT'
   elif not rk or not mk:cancellation='UNKNOWN'
   elif r.sectorS!=1:cancellation='SECTOR_NOT_TRUE'
   elif not truth(r.I_qualified):cancellation='I_INVALID'
   elif pd.isna(r.I_continuity_epoch) or r.I_continuity_epoch!=pending['I_continuity_epoch']:cancellation='I_ROOT_CHANGED'
   elif not np.isfinite(mu) or mu<=0:cancellation='MU_NOT_POSITIVE'
   elif r.relative_event==-1:cancellation='RELATIVE_DOWN'
   if cancellation:
    cancel_origin=pending['origin'];cancel_deadline=pending['deadline']
    action='CANCEL_'+cancellation;origin=pending['origin'];deadline=pending['deadline'];pending=None
   elif truth(r.M3):
    assert j==pending['deadline'],(d,'M3 completion must exactly match fixed deadline')
    action='RECEIPT_DEFERRED';origin=pending['origin'];deadline=pending['deadline']
    events.append(dict(day=d,arm_day=frame.index[origin],delay=j-origin,receipt_type='DEFERRED',arm_streak=pending['streak'],deadline=frame.index[deadline] if deadline<len(frame) else None))
    pending=None
   elif j>=pending['deadline']:
    action='EXPIRED_CONSISTENCY_FAILURE';origin=pending['origin'];deadline=pending['deadline'];pending=None
  # Processing cancellation first never lets an old receipt survive a loss of eligibility.
  if active and r.relative_event==1:
   eligible=rk and mk and r.sectorS==1 and truth(r.I_qualified) and pd.notna(r.I_continuity_epoch) and np.isfinite(mu) and mu>0 and pos=='FLAT'
   if eligible:
    if truth(r.M3):
     assert pending is None
     action='RECEIPT_IMMEDIATE';origin=j;deadline=j
     events.append(dict(day=d,arm_day=d,delay=0,receipt_type='IMMEDIATE',arm_streak=positive,deadline=d))
    elif arm=='CACHED':
     assert positive in (1,2),(d,positive)
     assert pending is None
     pending=dict(origin=j,deadline=j+3-positive,streak=positive,I_continuity_epoch=r.I_continuity_epoch);action='ARM';origin=j;deadline=pending['deadline']
    else:action='SAME_DAY_M3_NOT_READY'
   else:action='UP_NOT_ELIGIBLE'
  trace.append(dict(day=d,action=action,mu_streak=positive,arm_day=frame.index[origin] if origin is not None else None,deadline=frame.index[deadline] if deadline is not None and deadline<len(frame) else None,position_state=pos,pending=pending is not None,cancel_reason=cancellation,cancelled_arm_day=frame.index[cancel_origin] if cancel_origin is not None else None,cancelled_deadline=frame.index[cancel_deadline] if cancel_deadline is not None and cancel_deadline<len(frame) else None))
 return pd.DataFrame(events),pd.DataFrame(trace)
