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
 if mode=='CONTROL':return
 if not hasattr(a,'risk_state'):a.risk_state=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0)
 day=pd.Timestamp(at.date());i=RECOVERY.index.searchsorted(day,side='right')-1
 if i<0:fast=False;br=False
 else:r=RECOVERY.iloc[i];fast=bool(r.fast_on);br=bool(r.breakout) if RECOVERY.index[i]==day else False
 flat=not any(p.shares for p in a.positions.values()) and not a.exits and not a.buys
 a.risk_state,dd,event=advance(a.risk_state,a.current_nav,flat,fast,br,mode)
 a.log('risk_checkpoint',at,policy=mode,nav=a.current_nav,episode_drawdown=dd,flat=flat,fast=fast,breakout=br,event=event,**a.risk_state)

def override(a,stocks,clock,mode,Fact):
 if mode=='CONTROL' or a.risk_state['on']:return stocks
 return tuple(replace(s,trend_up=Fact(False,clock.decision_at,clock.decision_at,source_id='actual_account_risk_pause'),buy_allowed=Fact(False,clock.decision_at,clock.decision_at,source_id='actual_account_risk_pause')) for s in stocks)
