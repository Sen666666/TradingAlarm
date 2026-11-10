"""Synthetic source-definition cases. None are real observed events."""
from pathlib import Path
import sys,copy
import engine_known_halt_v1 as E
from halt_evidence_v1 import HaltEvidence
sys.path.insert(0,str(E.HERE.parent/'execution_bridge_v1'))
import test_execution_v4 as old
old.E=E
SID=old.SID

def suite(s):
    out=[];original_local=s.local_actions
    def run(name,fn):
        fn();out.append(dict(name=name,status='PASS',domain='SYNTHETIC'));print('PASS',name,flush=True)
    def fix(buy=True):
        b,st,ds=old.fixture(s);s.local_actions=lambda sid:{'events':[]}
        ds += [s.pd.Timestamp('2022-01-11'),s.pd.Timestamp('2022-01-12')]
        for d in ds[4:]:
            s.raw[SID][d]=copy.deepcopy(s.raw[SID][ds[3]]);s.facts[SID][d]=dict(i_target=True,i_floor=95.);s.cp[SID][d]=dict(receipt=False,candidate=95.);s.capacity[SID][d]=100000;s.sector[st['sector']][d]=1
        if buy:b.open_phase(ds[1]);b.close_phase(ds[1])
        return b,st,ds
    def row(d,**kw):return dict(evidence_id='SYNTHETIC_HALT',sid=SID,session=str(d.date()),scope='FULL_DAY',known_at=str(d.date())+'T08:00:00+08:00',**kw)
    def evidence(b,d,r=None):b.halts=HaltEvidence([r or row(d)],synthetic=True)
    def missing(d):s.raw[SID].pop(d,None);s.facts[SID].pop(d,None);s.cp[SID].pop(d,None)
    def add_other(b,ds,signal_day):
        sid='000810.SZ';s.load(sid)
        s.raw[sid]={d:dict(raw_open=100.,raw_close=110.,adjustment_factor=1.,source_kind='SYNTHETIC',source_path='SYNTHETIC',segment_id='SYNTHETIC',observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False) for d in ds}
        s.facts[sid]={d:dict(i_target=True,i_floor=95.) for d in ds};s.cp[sid]={d:dict(receipt=True,candidate=108.) for d in ds};s.capacity[sid]={d:100000 for d in ds}
        r=s.ev[s.ev.sid.eq(sid)].iloc[0].to_dict();r.update(day=signal_day,i_floor=95.,event_id='SYNTHETIC_OTHER',PVR_score=1.,I_qualified=True,PVR_known=True,sector='SYNTHETIC_OTHER')
        s.sector[r['sector']]={d:1 for d in ds};rid='SYNTHETIC_OTHER|'+sid
        st=s.new_state(r,E.ARM,rid,dict(close_q=100,prior20_capacity=100000));b.states[sid]=st;b.caps[rid]=E.D('1200000');return st
    def cross_stock_initial():
        b,st,ds=fix(False);other=add_other(b,ds,ds[0]);evidence(b,ds[1]);missing(ds[1]);b.open_phase(ds[1]);assert other['core']>0 and not b.risk_recovery_pending and not any(a['sid']==SID for a in s.actions)
    run('liability_free_halted_initial_does_not_block_other_stock_fill',cross_stock_initial)
    def cross_stock_resume():
        b,st,ds=fix();st['exitpending']='SYNTHETIC_EXIT';evidence(b,ds[2]);missing(ds[2]);b.open_phase(ds[2]);b.close_phase(ds[2]);other=add_other(b,ds,ds[2]);n=len(s.actions);b.open_phase(ds[3]);assert st['core']==0 and other['sid'] not in b.states and len(s.actions)==n+1 and s.actions[-1]['side']=='sell_all'
        assert not any(a['type']=='PROMOTED' for a in b.audit);assert b.snapshot(ds[3],'OPEN').nav is None;b.close_phase(ds[3]);assert b.snapshot(ds[3],'CLOSE').certified
    run('resumed_whole_exit_cannot_fund_same_OPEN_other_stock_initial',cross_stock_resume)
    def other_CP_expires():
        b,st,ds=fix(False);other=add_other(b,ds,ds[0]);b.open_phase(ds[1]);b.close_phase(ds[1]);evidence(b,ds[2]);missing(ds[2]);s.raw[other['sid']][ds[2]]['raw_open']=112.;b.open_phase(ds[2]);b.close_phase(ds[2]);assert other['addpending'] is not None
        s.raw[other['sid']][ds[3]]['raw_open']=112.;b.open_phase(ds[3]);assert not other['added'] and other['addpending'] is None and b.pools[other['round_id']]=='probe';s.cp[other['sid']][ds[3]]['receipt']=False;b.close_phase(ds[3]);b.open_phase(ds[4]);assert not other['added']
    run('other_stock_CP_on_halt_CLOSE_consumed_not_deferred_at_locked_resume_OPEN',other_CP_expires)
    def valid_halt():
        b,st,ds=fix();evidence(b,ds[2]);missing(ds[2]);before=(b.cash(),st['core'],st['add'],st['spent'],b.pools[st['round_id']]);n=len(s.actions)
        a=b.open_phase(ds[2])['reconciliation'];c=b.close_phase(ds[2])
        assert st['state']==E.HALT and st['addpending'] is None and b.pending_cp.get(st['round_id']) is None
        assert (b.cash(),st['core'],st['add'],st['spent'],b.pools[st['round_id']])==before and len(s.actions)==n
        assert a['NAV'] is None and c['NAV'] is None and a['NAV_stale'] and not a['new_risk_allowed']
        snap=b.snapshot(ds[2],'CLOSE');assert snap.stale_marks[0]['source_day']==ds[1] and snap.holdings[0].qty==st['core']
        assert snap.holdings[0].capital>0 and snap.holdings[0].nominal_risk>0
        op=b.open_phase(ds[3])['reconciliation'];assert st['state']=='HELD' and not op['certified'] and not st['added']
        assert b.snapshot(ds[3],'OPEN').holdings[0].floor==E.D('100')
        cl=b.close_phase(ds[3]);assert cl['certified'] and not b.risk_recovery_pending
        assert not any(a['type']=='PROMOTED' for a in b.audit)
    run('known_halt_retains_assets_risk_stale_information_and_locks_until_resume_CLOSE',valid_halt)
    def invalid():
        for key,value in [('known_at','2022-01-07T09:30:00+08:00'),('known_at','2022-01-07T09:31:00+08:00'),('known_at','2022-01-07'),('known_at',None),('session','2022-01-10'),('sid','000001.SZ'),('scope','PART_DAY')]:
            b,st,ds=fix();r=row(ds[2]);r[key]=value;evidence(b,ds[2],r);missing(ds[2]);b.open_phase(ds[2]);assert b.states[SID]['state']=='UNKNOWN' and b.snapshot(ds[2],'OPEN').nav is None
        b,st,ds=fix();missing(ds[2]);b.open_phase(ds[2]);assert b.states[SID]['state']=='UNKNOWN'
    run('late_equal_unknown_clock_wrong_sid_session_scope_and_no_evidence_remain_UNKNOWN',invalid)
    def tz():
        b,st,ds=fix();r=row(ds[2]);r['known_at']='2022-01-06T23:59:00+00:00';evidence(b,ds[2],r);assert b.halts.get(SID,ds[2])
        r['known_at']='2022-01-07T01:30:00+00:00';evidence(b,ds[2],r);assert b.halts.get(SID,ds[2]) is None
    run('explicit_market_timezone_strict_preopen',tz)
    def initial():
        b,st,ds=fix(False);evidence(b,ds[1]);missing(ds[1]);b.open_phase(ds[1]);b.close_phase(ds[1]);assert SID not in b.states and not s.actions and not b.risk_recovery_pending and b.snapshot(ds[1],'CLOSE').certified
        b.open_phase(ds[2]);assert not s.actions and SID not in b.states
    run('initial_ticket_expires_without_global_liability_lock_or_resume_replay',initial)
    def exit_retained():
        b,st,ds=fix();st['exitpending']='SYNTHETIC_EXIT';evidence(b,ds[2]);missing(ds[2]);b.open_phase(ds[2]);b.close_phase(ds[2]);assert st['exitpending']=='SYNTHETIC_EXIT'
        n=len(s.actions);r=b.open_phase(ds[3]);assert len(s.actions)==n+1 and s.actions[-1]['side']=='sell_all' and st['core']==0
        assert r['reconciliation']['NAV'] is None and b.risk_recovery_pending
        assert b.close_phase(ds[3])['certified']
    run('pending_whole_sell_persists_resume_sale_does_not_unlock_same_OPEN',exit_retained)
    def add_sell():
        b,st,ds=fix();b.open_phase(ds[2]);b.close_phase(ds[2]);assert st['add']>0
        st['addexitpending']=True;q=st['add'];evidence(b,ds[3]);missing(ds[3]);b.open_phase(ds[3]);b.close_phase(ds[3]);assert st['add']==q
        b.open_phase(ds[4]);assert st['add']==0 and s.actions[-1]['side']=='sell_add'
    run('existing_ADD_layer_and_pending_ADD_sell_survive_halt',add_sell)
    def missing_resume():
        b,st,ds=fix();evidence(b,ds[2]);missing(ds[2]);b.open_phase(ds[2]);b.close_phase(ds[2]);missing(ds[3]);b.open_phase(ds[3]);assert b.states[SID]['state']=='UNKNOWN'
    run('late_resume_without_new_supported_session_or_legal_OPEN_is_UNKNOWN',missing_resume)
    def conflict():
        b,st,ds=fix();evidence(b,ds[2]);b.open_phase(ds[2]);assert b.states[SID]['state']=='UNKNOWN' and not st['added']
        b,st,ds=fix();evidence(b,ds[2]);missing(ds[2]);b.open_phase(ds[2]);s.raw[SID][ds[2]]=dict(s.raw[SID][ds[1]]);b.close_phase(ds[2]);assert b.states[SID]['state']=='UNKNOWN'
    run('resume_earlier_than_supported_full_day_or_conflicting_CLOSE_is_UNKNOWN',conflict)
    def factor():
        b,st,ds=fix();evidence(b,ds[2]);missing(ds[2]);b.open_phase(ds[2]);b.close_phase(ds[2]);s.raw[SID][ds[3]]['adjustment_factor']=2.;b.open_phase(ds[3]);assert b.states[SID]['state']=='UNKNOWN'
    run('halt_does_not_waive_resume_factor_unknown',factor)
    def equity():
        b,st,ds=fix();evidence(b,ds[2]);missing(ds[2]);s.EVENT_AT[(SID,ds[2])]={'synthetic':True};b.open_phase(ds[2]);assert b.states[SID]['state']=='UNKNOWN' and st['core']>0
        b,st,ds=fix();evidence(b,ds[2]);missing(ds[2]);s.local_actions=lambda sid:{'events':[{'effective_date':str(ds[2].date())}]};b.open_phase(ds[2]);assert b.states[SID]['state']=='UNKNOWN'
    run('admitted_or_local_equity_coordinate_on_halt_still_UNKNOWN',equity)
    def claims():
        b,st,ds=fix();evidence(b,ds[2]);missing(ds[2]);q=st['core'];d=ds[2]
        ev=dict(sid=SID,economic_event_id='SYNTHETIC_OWNERSHIP',evidence_version='SYNTHETIC',record_date=d,coordinate_snapshot_day=d,ex_date=ds[3],pay_date=ds[3],entitlement_verified=True,d_cash=E.D(1))
        s.BY_RECORD={d:[ev]};b.open_phase(d);b.close_phase(d);claim=next(iter(s.claims.values()));assert claim['record_q']==q and claim['owner_round_id']==st['round_id']
        # Already adjudicated money transfer independent from coordinate bridge.
        # This is not a claim that a missing raw ex-date bridge is supported.
        s.BY_EX={ds[3]:[ev]};s.BY_PAY={ds[3]:[ev]};cash=b.cash();b.open_phase(ds[3]);assert st['receivable']==E.D(q)*E.D('.8') and b.cash()==cash
        b.close_phase(ds[3]);assert claim['settled'] and b.cash()==cash+E.D(q)*E.D('.8') and not st['receivable']
        assert s.claim_ledger[-1]['available_from']==ds[4]
    run('halt_registration_preserves_owner_quantity_and_recognized_ex_pay_clock',claims)
    def pay_halt():
        b,st,ds=fix();d=ds[2];evidence(b,d);missing(d)
        ev=dict(sid=SID,economic_event_id='SYNTHETIC_PAID',evidence_version='SYNTHETIC',record_date=ds[1],coordinate_snapshot_day=ds[1],ex_date=d,pay_date=d,entitlement_verified=True,d_cash=E.D(1))
        s.BY_RECORD={ds[1]:[ev]};s.register(b.states,E.ARM,ds[1]);s.BY_EX={d:[ev]};s.BY_PAY={d:[ev]};cash=b.cash();b.open_phase(d);recv=b.receivable();assert recv>0 and b.cash()==cash
        c=b.close_phase(d);assert c['NAV'] is None and b.cash()==cash+recv and b.receivable()==0 and st['state']==E.HALT
    run('recognized_claim_transfer_continues_while_market_NAV_locked',pay_halt)
    def pollution():
        b,st,ds=fix();evidence(b,ds[2]);missing(ds[2]);b.open_phase(ds[2]);b.close_phase(ds[2]);saved=b.capture_runtime();r=b.open_phase(ds[3]);a=copy.deepcopy(s.actions);b.restore_runtime(saved)
        s.raw[SID][ds[3]]['raw_close']=1e8;s.facts[SID][ds[3]]={'i_target':False,'i_floor':1e8};s.cp[SID][ds[3]]={'receipt':True,'candidate':1e8};s.sector[st['sector']][ds[3]]=-1
        r2=b.open_phase(ds[3]);assert s.actions==a and r['reconciliation']==r2['reconciliation']
        b.close_phase(ds[3]);assert s.archives[st['round_id']]['exitpending']=='I_STRUCTURE_EXIT'
    run('resume_OPEN_cannot_read_current_CLOSE_I_CP_or_M3_then_CLOSE_consumes_current_I',pollution)
    def noffill():
        b,st,ds=fix();s.facts[SID].pop(ds[1]);assert b.snapshot(ds[2],'OPEN').nav is None
    run('ordinary_missing_previous_common_I_is_not_forward_filled',noffill)
    def multi():
        b,st,ds=fix();b.halts=HaltEvidence([row(ds[2]),dict(row(ds[3]),evidence_id='SYNTHETIC_HALT_2')],synthetic=True);missing(ds[2]);missing(ds[3]);b.open_phase(ds[2]);b.close_phase(ds[2]);b.open_phase(ds[3]);b.close_phase(ds[3]);assert st['state']==E.HALT;b.open_phase(ds[4]);assert b.snapshot(ds[4],'OPEN').holdings[0].floor==E.D(100);assert b.close_phase(ds[4])['certified']
    run('multiple_precisely_covered_sessions_resume_without_gap_fill',multi)
    def fresh_after_resume():
        b,st,ds=fix();evidence(b,ds[2],row(ds[2],planned_resume_session=str(ds[4].date())));missing(ds[2]);b.open_phase(ds[2]);b.close_phase(ds[2]);b.open_phase(ds[3]);assert st['state']=='HELD' and not st['added']
        s.raw[SID][ds[3]]['raw_close']=120.;s.facts[SID][ds[3]]=dict(i_target=True,i_floor=115.);s.cp[SID][ds[3]]=dict(receipt=True,candidate=118.);s.raw[SID][ds[4]]['raw_open']=120.
        b.close_phase(ds[3]);assert st['addpending']==E.D(118) and b.pending_cp[st['round_id']]['signal_day']==ds[3]
        b.open_phase(ds[4]);assert st['added'] and b.pools[st['round_id']]=='confirmed'
    run('actual_resume_not_planned_date_and_new_resume_CLOSE_CP_can_execute_next_OPEN',fresh_after_resume)
    def invalid_resume_close():
        b,st,ds=fix();evidence(b,ds[2]);missing(ds[2]);b.open_phase(ds[2]);b.close_phase(ds[2]);b.open_phase(ds[3]);s.facts[SID][ds[3]]={};r=b.close_phase(ds[3]);assert b.states[SID]['state']=='UNKNOWN' and r['NAV'] is None and b.risk_recovery_pending
    run('invalid_current_resume_CLOSE_I_cannot_unlock_or_reuse_old_signal',invalid_resume_close)
    s.local_actions=original_local
    return out
