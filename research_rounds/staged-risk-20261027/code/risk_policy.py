from pathlib import Path
from decimal import Decimal as D
from dataclasses import replace
import pandas as pd
O=Path(__file__).resolve().parents[1]
RECOVERY=pd.read_csv(O/'recovery.csv',index_col=0,parse_dates=True)

def advance(state,nav,flat,fast,breakout,mode):
 s=dict(state);s['peak']=max(s['peak'],nav) if s['on'] else s['peak'];dd=1-nav/s['peak'];event=None;threshold=D('.1') if mode=='ACT10_BREAK' else D('.2')
 if s['on']:
  if dd>=threshold:
   s.update(on=False,saw_off=not fast);event='pause'
 else:
  s['saw_off']=s['saw_off'] or not fast
  recover=(s['saw_off'] and fast and not s['previous_fast']) if mode=='ACT20_FAST' else breakout
  if flat and recover:
   s.update(on=True,peak=nav,episode=s['episode']+1,saw_off=False);event='resume'
 s['previous_fast']=fast
 return s,dd,event

def step(a,at,mode):
 if mode in ('CONTROL','HALF'):return
 if not hasattr(a,'risk_state'):a.risk_state=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0)
 day=pd.Timestamp(at.date());i=RECOVERY.index.searchsorted(day,side='right')-1
 if i<0:fast=False;br=False
 else:r=RECOVERY.iloc[i];fast=bool(r.fast_on);br=bool(r.breakout) if RECOVERY.index[i]==day else False
 flat=not any(p.shares for p in a.positions.values()) and not a.exits and not a.buys
 if mode=='STEP':
  a.risk_state,dd,event=advance_staged(a.risk_state,a.current_nav,flat,not bool(a.exits),fast,br)
  a.risk_reduce_once=event=='reduce'
 else:a.risk_state,dd,event=advance(a.risk_state,a.current_nav,flat,fast,br,mode)
 a.log('risk_checkpoint',at,policy=mode,nav=a.current_nav,episode_drawdown=dd,flat=flat,no_exits=not bool(a.exits),fast=fast,breakout=br,event=event,**a.risk_state)

def override(a,stocks,clock,mode,Fact):
 if mode in ('CONTROL','HALF'):return stocks
 if mode=='STEP' and a.risk_state['phase']=='defensive':
  return tuple(replace(s,buy_allowed=Fact(False,clock.decision_at,clock.decision_at,source_id='staged_risk_no_new_buy')) for s in stocks)
 if a.risk_state['on']:return stocks
 return tuple(replace(s,trend_up=Fact(False,clock.decision_at,clock.decision_at,source_id='actual_account_risk_pause'),buy_allowed=Fact(False,clock.decision_at,clock.decision_at,source_id='actual_account_risk_pause')) for s in stocks)


def advance_staged(state,nav,flat,no_exits,fast,breakout):
 s=dict(state);phase=s.get('phase','full');s['peak']=max(s['peak'],nav) if phase!='paused' else s['peak'];dd=1-nav/s['peak'];event=None
 if phase!='paused' and dd>=D('.2'):phase='paused';event='pause'
 elif phase=='full' and not fast and dd>=D('.1'):phase='defensive';event='reduce'
 elif phase in ('defensive','paused') and breakout and no_exits and (phase!='paused' or flat):
  phase='full';s['peak']=nav;s['episode']+=1;event='resume'
 s.update(phase=phase,on=phase!='paused',previous_fast=fast,saw_off=not fast)
 return s,dd,event

def reduce_after_commit(a,clock,mode):
 if mode!='STEP' or not getattr(a,'risk_reduce_once',False):return
 a.risk_reduce_once=False
 for sid in sorted(a.positions):
  if sid in a.exits:continue
  qty=a.quantity(sid);quote=a.market.quote(sid,clock.decision_at)
  if quote is None:raise ValueError('Missing reduction decision quote')
  sale=quote.quantity.sell_floor(qty//2,qty)
  if sale<=0:
   a.log('risk_reduction_minimum',clock.decision_at,sid=sid,quantity=qty);continue
  a.request_reduction(quote,clock,int(sale));a.exits[sid].purpose='risk_reduction'
  a.log('risk_reduction_intent',clock.decision_at,sid=sid,shares=sale,held_shares=qty,event_id=a.exits[sid].event_id)
