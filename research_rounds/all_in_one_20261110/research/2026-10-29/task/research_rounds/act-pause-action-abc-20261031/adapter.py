from pathlib import Path
from decimal import Decimal as D
from dataclasses import replace
import sys,json,pandas as pd
O=Path(__file__).resolve().parent;OLD=O.parent/'entry-loss-budget-full-account-20261031';sys.path.insert(0,str(OLD));import wire as w
ORIGINAL_ADVANCE=None

def advance(state,nav,*,flat,no_orders,fast,breakout,policy,mode='ACT20_BREAK'):
 assert policy in ['B','C'];assert ORIGINAL_ADVANCE is not None
 return ORIGINAL_ADVANCE(state,nav,flat if policy=='B' else no_orders,fast,breakout,mode)

def controlled_step(a,at,mode,recovery):
 if not hasattr(a,'risk_state'):a.risk_state=dict(on=True,peak=D(1000000),saw_off=False,previous_fast=False,episode=0)
 assert getattr(a,'act_last_step',None)!=at,'duplicate ACT transition clock';a.act_last_step=at
 day=pd.Timestamp(at.date());i=recovery.index.searchsorted(day,side='right')-1
 if i<0:fast=False;br=False
 else:r=recovery.iloc[i];fast=bool(r.fast_on);br=bool(r.breakout) if recovery.index[i]==day else False
 before=dict(a.risk_state);flat=not any(p.shares for p in a.positions.values()) and not a.exits and not a.buys;no_orders=not a.exits and not a.buys
 a.risk_state,dd,event=advance(before,a.current_nav,flat=flat,no_orders=no_orders,fast=fast,breakout=br,policy=a.act_policy,mode=mode)
 assert int(before['on']!=a.risk_state['on'])<=1
 a.act_last_event=event
 a.log('risk_checkpoint',at,policy=mode,nav=a.current_nav,episode_drawdown=dd,flat=flat,fast=fast,breakout=br,event=event,**a.risk_state)
 waiting='transition_or_active'
 if not before['on'] and not a.risk_state['on']:
  waiting='orders' if not no_orders else 'flat' if a.act_policy=='B' and not flat else 'market' if not br else 'unknown'
  assert waiting!='unknown'
 a.log('act_checkpoint',at,policy=a.act_policy,previous_on=before['on'],previous_peak=before['peak'],on=a.risk_state['on'],peak=a.risk_state['peak'],nav=a.current_nav,episode=a.risk_state['episode'],flat=flat,no_orders=no_orders,has_holdings=any(p.shares for p in a.positions.values()),buy_orders=tuple(a.buys),sell_orders=tuple(a.exits),market=br,event=event,waiting_primary=waiting,held={s:a.quantity(s) for s in a.positions if a.quantity(s)})

def controlled_override(a,stocks,clock,mode,Fact):
 if a.risk_state['on']:return stocks
 if a.act_last_event=='pause':
  a.log('act_pause_holdings',clock.decision_at,policy=a.act_policy,held={s:a.quantity(s) for s in a.positions if a.quantity(s)},original_I={s.security_id:s.trend_up.read(clock) for s in stocks if a.quantity(s.security_id)},original_E0={s:None if (r:=a.facts.row(s,clock.decision_at)) is None or pd.isna(r.e0_target) else bool(r.e0_target) for s in a.positions if a.quantity(s)},existing_sell_orders=tuple(a.exits),existing_buy_orders=tuple(a.buys))
 return tuple(replace(s,buy_allowed=Fact(False,clock.decision_at,clock.decision_at,source_id='ACT_paused_no_new_buy_keep_native_trend')) for s in stocks)

def setup(sector,root,enabled,cutoff=None):
 global ORIGINAL_ADVANCE
 R,E,core,prep,mode=w.setup(sector,root,False,cutoff);ORIGINAL_ADVANCE=E.risk_policy.advance;step0=E.risk_policy.step;override0=E.risk_policy.override;spec0=R.specs
 def specs(modes,stresses,variant):
  ss=spec0(modes,stresses,variant)
  return tuple(replace(s,account_id=s.account_id.split('__')[0]+'__'+p+'_'+s.account_id.split('__')[1]) for p in ['B','C'] for s in ss) if enabled else ss
 R.specs=specs;Base=R.Runner
 class Runner(Base):
  def run_tech(self):
   for aid,a in self.accounts.items():a.act_policy=aid.split('__')[1].split('_')[0] if enabled else 'A'
   return super().run_tech()
 R.Runner=Runner
 def step(a,at,riskmode):return controlled_step(a,at,riskmode,E.risk_policy.RECOVERY) if a.act_policy in ['B','C'] else step0(a,at,riskmode)
 def override(a,stocks,clock,riskmode,Fact):return controlled_override(a,stocks,clock,riskmode,Fact) if a.act_policy in ['B','C'] else override0(a,stocks,clock,riskmode,Fact)
 E.risk_policy.step=step;E.risk_policy.override=override
 return R,E,core,prep,mode
