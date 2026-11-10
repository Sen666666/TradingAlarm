"""Small native-function boundary tests only, not a market economic run."""
import engine as s
from engine import pd,D
s.reset();sid='BOUNDARY.SZ';arm='A_UNION_B';d=pd.Timestamp('2022-04-29');prior=pd.Timestamp('2022-04-28');nxt=pd.Timestamp('2022-05-05')
s.raw[sid]=s.DayFrame(pd.DataFrame([dict(raw_open=10,adjustment_factor=1,source_kind='x',source_path='y',segment_id='z'),dict(raw_open=4,adjustment_factor=1,source_kind='x',source_path='y',segment_id='z')],index=[d,nxt]))
s.getmeta=lambda *a:(None,None,D(1));s.fee=lambda *a:D(0)
r=dict(event_id='NEW_EDGE',window='2022',day=d,event_type='A_SECTOR_BIRTH',sid=sid,name='boundary',industry='test',sector='TEST',PVR_score=10,I_qualified=True,PVR_known=True,i_floor=5,relative_known=True,relative_event=1)
s.checkclose=lambda *a:dict(close_check='PASS',close_q=100,prior20_capacity=100)
st=dict(r,round_id='OLD',arm=arm,state='HELD',signal_day=prior,entry_day=prior,entry_status='CONDITIONAL_OPEN_PROXY',close_q=100,core=100,add=0,cash=D(-1000),spent=D(1000),fees=D(0),origin=('x','y','z'),factor=1,fac=D(1),exitpending='I_STRUCTURE_EXIT',addexitpending=False,addpending=None,receivable=D(0),dividend_total=D(0),dividend_paid=D(0))
s.archives['OLD']=st;states={sid:st};before=s.queue(pd.DataFrame([r]),states,arm);assert before[0]['ranking_feasibility']=='BLOCKED_HELD'
s.held_open(states,sid,st,d,prior);assert sid not in states and s.actions[-1]['side']=='sell_all';after=s.queue(pd.DataFrame([r]),states,arm);assert after[0]['ranking_feasibility']=='PASS';states[sid]=s.new_state(r,arm,'NEW',s.checkclose(r));assert states[sid]['state']=='BUY_PENDING'
# No fill returns FLAT but cannot manufacture a substitute permit or invoke queue again.
oldactions=len(s.actions);oldranking=len(s.ranking_audit);s.entry_open(states,sid,states[sid],nxt);assert sid not in states and len(s.actions)==oldactions and len(s.ranking_audit)==oldranking;assert s.rounds[-1]['status']=='NEXT_OPEN_BELOW_PROTECTION_NOFILL'
# Held bridge rebases the two raw protections and keeps exit priorities/stock/cost unchanged.
e=dict(sid=sid,economic_event_id='BOUNDARY_CASH',evidence_version='v1',ex_date=d,previous_day=prior,d_source=D(1),d_cash=D('.999'),factor_old=D(1),factor_new=D(10)/D(9),coordinate_verified=True,entitlement_verified=True)
s.EVENT_AT[sid,d]=e;s.raw[sid]=s.DayFrame(pd.DataFrame([dict(raw_open=10,raw_close=10,adjustment_factor=1,source_kind='x',source_path='y',segment_id='z'),dict(raw_open=9,adjustment_factor=float(D(10)/D(9)),source_kind='x',source_path='y',segment_id='z')],index=[prior,d]));s.snapshots[s.claim_key(arm,e)]=dict(record_q=150,core_record_q=100)
st=dict(st,state='HELD',core=100,add=50,addfloor=D(8),addpending=D(7),fac=D(1),factor=1,addexitpending=True,cash=D(-1500));states={sid:st};assert s.before_held(states,sid,st,d);assert abs(st['addfloor']-D('7.2'))<D('1e-12') and abs(st['addpending']-D('6.3'))<D('1e-12');assert st['core']==100 and st['add']==50 and st['exitpending']=='I_STRUCTURE_EXIT' and st['addexitpending'] and st['cash']==-1500
# Pending coordinate requires known zero: UNKNOWN and positive registration cannot be used.
p=dict(r,arm=arm,round_id='PENDING');cur=s.raw[sid].get(d);prev=s.raw[sid].get(prior)
for q,ok in [(None,False),(100,False),(0,True)]:
 s.snapshots[s.claim_key(arm,e)]=dict(record_q=q,core_record_q=q);assert s.pending_bridge(p,d,cur,prev)==ok
s.save(s.O/'BOUNDARY_QA.json',dict(native_sell_all_releases_before_same_day_new_edge=True,exitpending_alone_stays_blocked=True,native_nofill_returns_flat_without_backfill=True,rebase_both_protections_preserves_exit_flags_qty_cash=True,pending_only_known_zero_bridge=True,synthetic_no_economic_returns=True,engine_sha256=s.sha(s.O/'engine.py')));print('BOUNDARY_PASS')
