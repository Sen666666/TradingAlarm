"""Synthetic-only preflight. Never walks a real security lifecycle."""
import lifecycle as l
s=l.s
from decimal import Decimal as D
from pathlib import Path
import pandas as pd,numpy as np,json
O=Path(__file__).resolve().parent
sid='600028.SH';t=pd.Timestamp('2022-05-31');d=pd.Timestamp('2022-06-01')
results={}
def row(op=100,cl=100,factor=1):
 return dict(raw_open=op,raw_close=cl,adjustment_factor=float(factor),source_kind='SYNTH',source_path='SYNTH',segment_id=0,observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False)
def init(close=100,op=100,floor=80,cpfloor=99):
 l.reset(True);s.raw[sid]=s.DayFrame(pd.DataFrame([row(close,close),row(op,op),row(op,op)],index=[t,d,d+pd.Timedelta(days=1)]))
 s.facts[sid]=s.DayFrame(pd.DataFrame([dict(i_target=1,i_floor=floor)]*3,index=[t,d,d+pd.Timedelta(days=1)]))
 s.cp[sid]=s.DayFrame(pd.DataFrame([dict(receipt=False,candidate=np.nan)]*3,index=[t,d,d+pd.Timedelta(days=1)]));s.capacity[sid]={t:10000,d:10000};s.sector['SYNTH']={t:1,d:1,d+pd.Timedelta(days=1):1}
 s.closecache={};s.load=lambda x:None
 r=dict(sid=sid,day=t,name='SYNTH',industry='SYNTH',sector='SYNTH',window='2022',event_id='SYNTH',event_type='SYNTH',PVR_score=1.,PVR_known=True,I_qualified=True,i_floor=floor,cp_candidate=cpfloor,i_epoch='SYNTH:E1',epoch_lineage_known=True,event_Q=True,continuing_Q=True,cp_fresh=True,cp_trace_known=True,cp_id='SYNTH:CP1',AB_event_id=None,AB_I_qualified=False,source_mask='FAST_CORE|FRESH_CP')
 return r
def pending(r):
 options,checks,reason=l.prepare(r,'UNIT')
 assert reason=='PASS',(checks,reason)
 st=s.new_state(dict(r,role_options=options,signal_cp_id=r['cp_id']),'UNIT','SYNTH:ROUND',options[0]['check'])
 return {sid:st},st
r=init();a=l.close_role(r,'I_CORE',80);b=l.close_role(r,'MOBILE_CP',99)
assert a['close_q']!=b['close_q'] and a['close_plan_risk']!=b['close_plan_risk'];assert l.close_role(r,'I_CORE',80)==a
results['role_floor_cache_isolated']=dict(I=a,CP=b)
r=init(op=110);states,st=pending(r);l.entry_open(states,sid,st,d)
assert st['entry_role']=='MOBILE_CP' and len(l.role_attempts)==2 and len(l.cp_consumed)==1 and not l.core_consumed
assert l.role_attempts[0]['result']=='MINIMUM_LOT_NOT_FUNDED_NOFILL'
results['known_I_open_size_fail_CP_fallback_positive_fill_only']=l.role_attempts.copy()
r=init(op=70);states,st=pending(r);l.entry_open(states,sid,st,d)
assert sid not in states and not l.core_consumed and not l.cp_consumed and len(s.actions)==0
results['all_NOFILL_no_consumption']=True
r=init();states,st=pending(r);s.raw[sid].frame.loc[d,'adjustment_factor']=1.01;l.entry_open(states,sid,st,d)
assert states[sid]['state']=='UNKNOWN' and not s.actions and not l.cp_consumed and not l.core_consumed
results['factor_unknown_locks_no_fallback']=True
r=init();states,st=pending(r);l.entry_open(states,sid,st,d)
assert st['entry_role']=='I_CORE' and len(l.core_consumed)==1 and not l.cp_consumed
assert [x['role'] for x in l.role_options(r,'UNIT')]==['MOBILE_CP']
r['AB_event_id']='AB:SYNTH';r['AB_I_qualified']=True;r['AB_event_type']='A_SECTOR_BIRTH'
assert [x['role'] for x in l.role_options(r,'UNIT')]==['I_CORE','MOBILE_CP']
results['CORE_positive_fill_epoch_CP_separate_AB_independent']=True
# CP close uses old floor; new I/CP floor is effective only after this close.
r=init();r['event_Q']=False;states,st=pending(r);l.entry_open(states,sid,st,d)
assert st['entry_role']=='MOBILE_CP'
st['initialfloor']=D(90);s.facts[sid].frame.loc[d,'i_floor']=105;s.cp[sid].frame.loc[d,['receipt','candidate']]=[True,108]
l.cpmap[(sid,d)]=dict(cp_id='SYNTH:CP2',known=True)
l.held_close(states,sid,st,d)
assert not st['initialexitpending'] and st['initialfloor']==108
nd=d+pd.Timedelta(days=1);s.facts[sid].frame.loc[nd,'i_floor']=105;l.held_close(states,sid,st,nd)
assert st['initialexitpending']
results['CP_break_old_floor_then_raise_new_line']=True
# I false overrides CP exit and cancels additions, still held until later OPEN.
s.facts[sid].frame.loc[nd,'i_target']=0;st['addpending']=D(80);l.held_close(states,sid,st,nd)
assert st['exitpending']=='I_STRUCTURE_EXIT' and st['addpending'] is None and states[sid]['state']=='HELD'
results['I_false_priority_pending_held']=True
# CP initial can exit independently while an add remains. No initial equity sold twice.
r=init();r['event_Q']=False;states,st=pending(r);l.entry_open(states,sid,st,d);st.update(add=100,added=True,added_q=100,addfloor=D(90),initialexitpending=True)
l.held_open(states,sid,st,nd,d)
assert st['core']==0 and st['add']==100 and states[sid]['state']=='HELD'
assert s.actions[-1]['side']=='sell_initial' and st['initial_exit_day']==nd
results['CP_initial_exit_not_full_round_exit']=True
# A fill cannot be sold at the same OPEN, even when an exit flag is injected.
r=init();states,st=pending(r);l.entry_open(states,sid,st,d);st['exitpending']='SYNTH'
try:l.held_open(states,sid,st,d,t)
except AssertionError:results['T_plus_one_asserted']=True
else:raise AssertionError('same-day sale allowed')
# Exact 0 net gate remains native: no CP addition.
r=init();states,st=pending(r);l.entry_open(states,sid,st,d);old=s.mark;s.mark=lambda *x:D(0);s.cp[sid].frame.loc[d,['receipt','candidate']]=[True,90];l.held_close(states,sid,st,d);s.mark=old
assert st['addpending'] is None;results['strict_zero_profit_no_add']=True
# CP initial floor participates in the same pure-cash coordinate bridge.
r=init();r['event_Q']=False;states,st=pending(r);l.entry_open(states,sid,st,d)
old_before=l.original_before_held
def bridge(states,sid,st,d):st['fac']=D('1.1');st['factor']=1.1;s.bridges.append(dict(protections={}));return True
l.original_before_held=bridge;oldfloor=st['initialfloor'];l.before_held(states,sid,st,nd);l.original_before_held=old_before
assert st['initialfloor']==oldfloor/D('1.1') and 'initialfloor' in s.bridges[-1]['protections']
results['CP_initial_coordinate_bridge']=True

# Missing CP floor cannot silently fall back to I floor; known I remains its only offer.
r=init(op=110);r['cp_candidate']=np.nan;opts,checks,reason=l.prepare(r,'UNIT')
assert reason=='PASS' and len(opts)==1 and opts[0]['role']=='I_CORE' and checks[1]['close_check']=='ROLE_FLOOR_UNKNOWN'
states,st=pending(r);l.entry_open(states,sid,st,d)
assert sid not in states and not l.cp_consumed and not l.core_consumed and not s.actions
r=init();r['event_Q']=False;r['cp_candidate']=None;opts,checks,reason=l.prepare(r,'UNIT')
assert not opts and reason=='CLOSE_ROLE_FLOOR_UNKNOWN'
results['unknown_CP_floor_not_downgraded_or_open_fallback']=True
# CP add risk is charged to the actual current CP initial protection, not low I.
r=init();r['event_Q']=False;states,st=pending(r);l.entry_open(states,sid,st,d)
st.update(initialfloor=D(99),addpending=D(99),addpending_cp_id='SYNTH:CP2')
# A strictly profitable marked value isolates protection sizing, without new cash outcome labels.
oldmark=s.mark;s.mark=lambda *a:D(100);calls=[];oldsize=s.size
def capture(sid,d,px,fl,budget,riskmax,cap):calls.append(dict(floor=fl,riskmax=riskmax));return oldsize(sid,d,px,fl,budget,riskmax,cap)
s.size=capture;l.held_open(states,sid,st,nd,d);s.size=oldsize;s.mark=oldmark
assert calls and calls[0]['riskmax']>D(2000) and st['added']
results['CP_add_actual_initial_floor_risk']=str(calls[0]['riskmax'])


# Complete synthetic CP initial + add, dividend registration, different exits, cash reconciliation.
r=init(close=110,op=110,floor=80,cpfloor=108);r['event_Q']=False
t2=pd.Timestamp('2022-06-02');ex=pd.Timestamp('2022-06-03');pay=pd.Timestamp('2022-06-06');fac=107/106
s.raw[sid]=s.DayFrame(pd.DataFrame([row(110,110),row(110,112),row(111,107),row(106.5,106,fac),row(105,105,fac)],index=[t,d,t2,ex,pay]))
s.facts[sid]=s.DayFrame(pd.DataFrame([dict(i_target=1,i_floor=80)]*5,index=[t,d,t2,ex,pay]));s.facts[sid].frame.loc[ex,'i_target']=0
s.cp[sid]=s.DayFrame(pd.DataFrame([dict(receipt=False,candidate=np.nan)]*5,index=[t,d,t2,ex,pay]));s.cp[sid].frame.loc[d,['receipt','candidate']]=[True,105]
s.capacity[sid]={x:10000 for x in [t,d,t2,ex,pay]};s.sector['SYNTH']={x:1 for x in [t,d,t2,ex,pay]}
l.cpmap[(sid,d)]=dict(cp_id='SYNTH:CP2',known=True)
states,st=pending(r);l.entry_open(states,sid,st,d);l.held_close(states,sid,st,d)
assert st['addpending']==105 and st['initialfloor']==108
l.held_open(states,sid,st,t2,d);assert st['add']>0 and st['core']>0 and st['addfloor']==105
l.held_close(states,sid,st,t2);assert st['initialexitpending'] and not st['addexitpending']
e=dict(sid=sid,economic_event_id=sid+'|SYNTH_DIV',evidence_version='synthetic',record_date=t2,coordinate_snapshot_day=t2,previous_day=t2,ex_date=ex,pay_date=pay,d_source=D(1),d_cash=D(1),factor_old=D(1),factor_new=D(str(fac)),entitlement_verified=True)
saved=(s.BY_RECORD,s.BY_EX,s.BY_PAY,s.EVENT_AT)
s.BY_RECORD={t2:[e]};s.BY_EX={ex:[e]};s.BY_PAY={pay:[e]};s.EVENT_AT={(sid,ex):e}
s.register(states,'UNIT',t2);claim=s.claims[s.claim_key('UNIT',e)];cq=st['core'];aq=st['add']
assert claim['record_q']==cq+aq and claim['core_record_q']==cq
s.accrue_day('UNIT',ex);l.held_open(states,sid,st,ex,t2)
assert st['core']==0 and st['add']==aq and st['initial_exit_day']==ex and st['receivable']==D(cq+aq)*D('.8')
l.held_close(states,sid,st,ex);l.held_open(states,sid,st,pay,ex)
assert sid not in states and s.rounds[-1]['status']=='COMPLETE_CONDITIONAL_STOCK_ROUND' and st['initial_exit_day']==ex
s.pay_day('UNIT',pay);s.pay_day('UNIT',pay);s.finalize();ledger=s.ledger_qa()
assert st['receivable']==0 and claim['core_amount']==D(cq)*D('.8') and len(ledger)==1
assert len([a for a in s.actions if a['side']=='buy_add'])==1 and len([a for a in s.actions if a['side']=='sell_initial'])==1
# Claim stays with terminated original root after a hypothetical new root appears.
new=dict(st,round_id='SYNTH:REENTRY',cash=D(-1),receivable=D(0));s.archives[new['round_id']]=new;s.pay_day('UNIT',pay)
assert new['cash']==-1 and new['receivable']==0
results['full_CP_initial_add_dividend_T1_separate_exits_reconciled']=dict(initial_q=cq,add_q=aq,initial_exit=str(ex.date()),full_exit=str(pay.date()),core_claim=str(claim['core_amount']),all_claim=str(claim['amount']),ledger=ledger)
s.BY_RECORD,s.BY_EX,s.BY_PAY,s.EVENT_AT=saved
# Negative OTHER event must not grant independent AB authority.
r=init();r.update(event_Q=False,cp_fresh=False,AB_event_id='OTHER:SYNTH',AB_event_type='OTHER_UNKNOWN_OR_LEFT',AB_I_qualified=True)
assert not l.role_options(r,'UNIT')
results['OTHER_not_AB_negative_gate']=True

# Inherited corporate entitlement implementations are unchanged function objects.
results['inherited_entitlement_definitions_unmodified']={n:s.sha(l.BASE/'engine.py') for n in ['register','accrue_day','pay_day','pending_bridge','local_actions']}
results['scope']='Synthetic rows only; no real market lifecycle, parameter scan, or economic result.'
s.save(O/'SYNTHETIC_QA.json',results)
print('SYNTHETIC_PASS',list(results),flush=True)
