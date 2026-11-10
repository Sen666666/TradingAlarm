"""Account-independent local price-volume recovery receipts, no temperature."""
import math
import numpy as np
import pandas as pd

def greater(a,b):return a>b+32*np.finfo(float).eps*max(1.,abs(a),abs(b))
def reached(a,b):return a>=b-32*np.finfo(float).eps*max(1.,abs(a),abs(b))

def recover(e,m,g,joint=True):
 if not e.index.equals(m.index) or not e.index.equals(g.index):raise ValueError('Identical clocks required')
 if not e.index.is_unique or not e.index.is_monotonic_increasing:raise ValueError('Ordered unique input required')
 if not isinstance(joint,(bool,np.bool_)):raise ValueError('Boolean joint mode required')
 rows=[];journal=[];seg=None;state=None;previous_adverse=False;last_up_high=math.nan;segment_high=math.nan;episode=0
 for dt,r in e.iterrows():
  if r.segment_id!=seg:
   seg=r.segment_id;state=None;previous_adverse=False;last_up_high=math.nan;segment_high=math.nan;episode=0
  row=dict(ready=False,episode=np.nan,reset=False,reset_reason='',anchor_date='',anchor=np.nan,s0=np.nan,v0=np.nan,delta5=np.nan,delta21=np.nan,x=np.nan,frontier=np.nan,credit=np.nan,increment=0.,credit_increment=0.,weight=np.nan,checkpoint_x=np.nan,checkpoint_q=np.nan,receipt=False,receipt5=False,receipt21=False,tier=0,pre_high=np.nan,below_pre_high=False,context='unknown',acute_down=False)
  if not bool(r.valid_strength_observation) or not bool(g.loc[dt,'ready']):rows.append(row);continue
  c=float(r.close);s=float(r.strength_s);vref=float(r.strength_volume_reference);v=float(r.volume);z5=float(g.loc[dt,'z5']);a=int(r.strength_S21);b=int(r.strength_S63)
  if not all(np.isfinite([c,s,vref,v])) or min(c,s,vref,v)<=0:raise ValueError('Ready evidence must have finite positive price, scale, volume references')
  # Latest known UP structure high, never replace it with a down structure low.
  prior_high=last_up_high if np.isfinite(last_up_high) else segment_high
  segment_high=max(segment_high,c) if np.isfinite(segment_high) else c
  down=bool(r.strength_acute_down);adverse=z5<=-1.
  reasons=[]
  if state is None:reasons.append('initialize')
  if down:reasons.append('new_acute_down')
  if adverse and not previous_adverse:reasons.append('new_fast_adverse_onset')
  if any(float(r[f'strength_confirmed_direction_{h}'])==-1 for h in [21,63]):reasons.append('new_down_structure_confirmation')
  if state is not None and greater(0.,math.log(c/state['anchor'])):reasons.append('new_local_low')
  if reasons:
   pre_high=prior_high if np.isfinite(prior_high) else segment_high
   if state is not None and reasons==['new_local_low']:pre_high=state['pre_high']
   episode+=1;state=dict(anchor=c,anchor_date=str(dt.date()),s0=s,v0=vref,delta5=math.sqrt(5)*s,delta21=math.sqrt(21)*s,frontier=0.,credit=0.,checkpoint_x=0.,checkpoint_q=0.,broad_seen=False,pre_high=pre_high)
   row.update(reset=True,reset_reason='|'.join(reasons));journal.append(dict(date=str(dt.date()),kind='reset',episode=episode,reasons=reasons,**state))
  x=math.log(c/state['anchor']);old_f=state['frontier'];d=0.;dq=0.;weight=float(np.clip(math.sqrt(v/state['v0']),.5,2.)) if joint else 1.
  # No same-observation reset and confirmation, and no duplicate frontier credit.
  if not row['reset'] and greater(x,old_f) and float(r.strength_r)>0:
   d=x-old_f;dq=d*weight;state['frontier']=x;state['credit']+=dq
  step=bool(d>0 and reached(x-state['checkpoint_x'],state['delta5']) and reached(state['credit']-state['checkpoint_q'],state['delta5']))
  broad=bool(d>0 and not state['broad_seen'] and reached(x,state['delta21']) and reached(state['credit'],state['delta21']))
  if broad:state['broad_seen']=True
  receipt=step or broad
  if receipt:
   state['checkpoint_x']=x;state['checkpoint_q']=state['credit']
  mu63=float(m.loc[dt,'mu63']);mu126=float(m.loc[dt,'mu126'])
  weak=b==-1 or (np.isfinite(mu63+mu126) and mu63<0 and mu126<0)
  up=b==1 and np.isfinite(mu63) and mu63>0 and (not np.isfinite(mu126) or mu126>0)
  context='down' if weak else 'up' if up else 'mixed'
  row.update(ready=True,episode=episode,anchor_date=state['anchor_date'],anchor=state['anchor'],s0=state['s0'],v0=state['v0'],delta5=state['delta5'],delta21=state['delta21'],x=x,frontier=state['frontier'],credit=state['credit'],increment=d,credit_increment=dq,weight=weight,checkpoint_x=state['checkpoint_x'],checkpoint_q=state['checkpoint_q'],receipt=receipt,receipt5=step,receipt21=broad,tier=21 if state['broad_seen'] else 5 if receipt else 0,pre_high=state['pre_high'],below_pre_high=greater(math.log(state['pre_high']/c),0.),context=context,acute_down=down)
  if receipt:journal.append(dict(date=str(dt.date()),kind='local_recovery_receipt',episode=episode,**{k:row[k] for k in ['anchor_date','anchor','s0','v0','delta5','delta21','x','frontier','credit','increment','credit_increment','weight','receipt5','receipt21','tier','pre_high','below_pre_high','context']}))
  if a==1 and np.isfinite(r.strength_running_extreme_price_21):last_up_high=float(r.strength_running_extreme_price_21)
  previous_adverse=adverse;rows.append(row)
 return pd.DataFrame(rows,index=e.index),journal
