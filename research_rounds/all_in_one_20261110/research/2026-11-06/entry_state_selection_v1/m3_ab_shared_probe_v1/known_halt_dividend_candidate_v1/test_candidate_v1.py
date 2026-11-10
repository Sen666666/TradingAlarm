"""Source-definition synthetic tests for the new, isolated adapter."""
from pathlib import Path
import copy,sys
import candidate_bridge_v1 as E
sys.path.insert(0,str(E.HERE.parent/'indexed_execution_v1'))
import test_execution_indexed as old
D=E.D;SID=old.SID

def daily(day):return dict(kind='OFFICIAL_PUBLICATION_DATE',timezone='Asia/Shanghai',publication_date=day,date_basis='OFFICIAL_ISSUE_DATE',publication_date_verified=True)
def event(ds,**kw):
    c=dict(sid=SID,economic_event_id='SYNTHETIC|DISTRIBUTION',event_type='PURE_CASH',record_date=str(ds[2].date()),ex_date=str(ds[3].date()),pay_date=str(ds[3].date()),d_cash='1',d_source='1',split_ratio='1',clock=daily('2022-01-04'));c.update(kw);return c

def suite(s):
    out=[];native_local=s.local_actions;old.E=E
    def run(name,fn):
        fn();out.append(dict(name=name,status='PASS',domain='SYNTHETIC_SOURCE_DEFINITION'));print('PASS',name,flush=True)
    def fix(buy=True):
        b,st,ds=old.fixture(s);s.local_actions=lambda sid:{'events':[]}
        ds += [s.pd.Timestamp('2022-01-11'),s.pd.Timestamp('2022-01-12')]
        for day in ds[4:]:
            s.raw[SID][day]=copy.deepcopy(s.raw[SID][ds[3]]);s.facts[SID][day]=dict(i_target=True,i_floor=95.);s.cp[SID][day]=dict(receipt=False,candidate=95.);s.capacity[SID][day]=100000;s.sector[st['sector']][day]=1
        if buy:b.open_phase(ds[1]);b.close_phase(ds[1])
        return b,st,ds
    def candidate(b,c):b.candidate_tape=E.CandidateTape(s,[c],synthetic=True)
    def halt(b,d,clock=None,**kw):
        r=dict(evidence_id='SYNTHETIC_HALT',sid=SID,session=str(d.date()),scope='FULL_DAY',clock=clock or daily('2022-01-05'));r.update(kw)
        b.halts=E.HaltEvidence([r],synthetic=True)
    def missing(d):s.raw[SID].pop(d,None);s.facts[SID].pop(d,None);s.cp[SID].pop(d,None)
    def expect_unknown(p):
        b,st,ds=fix();halt(b,ds[2],p);missing(ds[2]);b.open_phase(ds[2]);assert b.states[SID]['state']=='UNKNOWN' and b.snapshot(ds[2],'OPEN').nav is None and st['core']==200
    for name,p in [
        ('official_same_session_date_rejected',daily('2022-01-07')),
        ('official_future_date_rejected',daily('2022-01-08')),
        ('effective_halt_interval_is_not_known_at',dict(kind='HALT_INTERVAL',timezone='Asia/Shanghai',start='2022-01-07',end='2022-01-10')),
        ('URL_date_is_not_publication',dict(daily('2022-01-05'),date_basis='URL_PATH')),
        ('unverified_official_date_rejected',dict(daily('2022-01-05'),publication_date_verified=False)),
        ('missing_clock_rejected',{}),
        ('missing_timezone_rejected',dict(daily('2022-01-05'),timezone=None)),
        ('conflicting_timezone_rejected',dict(daily('2022-01-05'),timezone='UTC')),
    ]:run(name,lambda p=p:expect_unknown(p) if p else expect_unknown(dict(kind='MISSING')))
    def news():
        p=dict(kind='RELIABLE_NEWS_PAIRED_FACTS',timezone='Asia/Shanghai',published_at='2022-01-05T19:00:00+08:00',updated_at='2022-01-07T09:30:00+08:00',clock_verified=True,exact_fact_pair_verified=True,paired_facts=['full-day halt'])
        assert E.clock_bound(p)[0].date().isoformat()=='2022-01-07';expect_unknown(p)
        p['updated_at']='2022-01-06T20:00:00+08:00';assert E.known_for_session(p,'2022-01-07')[0]
        p['body_local_time']='2022-01-05T19:00:00+08:00';assert E.clock_bound(p)[0] is None
        p.pop('body_local_time');p['published_at']='2022-01-05T19:00:00';assert E.clock_bound(p)[0] is None
        p['published_at']='2022-01-05T19:00:00+08:00';p['exact_fact_pair_verified']=False;assert E.clock_bound(p)[0] is None
    run('news_update_upper_bound_missing_zone_conflict_and_pair_required',news)
    def same_session_news():
        p=dict(kind='RELIABLE_NEWS_PAIRED_FACTS',timezone='Asia/Shanghai',published_at='2022-01-07T08:59:00+08:00',clock_verified=True,exact_fact_pair_verified=True,paired_facts=['full-day halt'])
        b,st,ds=fix();halt(b,ds[2],p);missing(ds[2]);b.open_phase(ds[2]);assert st['state']==E.HALT
        assert not E.known_for_session(p,'2022-01-06')[0]
        for stamp in ['2022-01-07T09:30:00+08:00','2022-01-07T09:30:01+08:00']:
            expect_unknown(dict(p,published_at=stamp))
        prior=dict(p,published_at='2022-01-06T19:28:57+08:00');assert E.known_for_session(prior,'2022-01-07')[0] and not E.known_for_session(prior,'2022-01-06')[0]
    run('reliable_news_same_day_0859_accepts_0930_or_later_rejects_no_prior_CLOSE_backdate',same_session_news)
    def eod():
        p=daily('2022-05-05');ok,t,_=E.known_for_session(p,'2022-05-06');assert ok and t.isoformat()=='2022-05-05T23:59:59.999999+08:00';assert not E.known_for_session(p,'2022-05-05')[0]
    run('official_date_conservative_end_of_day_and_next_session_only',eod)
    def responsibilities():
        b,st,ds=fix();st['exitpending']='SYNTHETIC_OLD_EXIT';oldq=st['core'];halt(b,ds[2]);missing(ds[2]);cash=b.cash();b.open_phase(ds[2]);b.close_phase(ds[2])
        assert st['core']==oldq and st['exitpending'] and not st['addpending'] and st['state']==E.HALT and b.cash()==cash
        assert b.snapshot(ds[2],'CLOSE').nav is None and b.snapshot(ds[2],'CLOSE').stale_marks
        r=b.open_phase(ds[3]);assert st['core']==0 and len(r['actions'])==1 and r['actions'][0]['side']=='sell_all'
        assert not r['reconciliation']['certified'] and b.risk_recovery_pending
        assert b.close_phase(ds[3])['certified'] and not b.risk_recovery_pending
    run('halt_retains_qty_sell_expires_ADD_resume_old_sell_and_locks_risk',responsibilities)
    def initial_expiry():
        b,st,ds=fix(False);halt(b,ds[1]);missing(ds[1]);b.open_phase(ds[1]);b.close_phase(ds[1]);b.open_phase(ds[2]);assert not s.actions and SID not in b.states
    run('halt_due_initial_expires_no_makeup_execution',initial_expiry)
    def planned_resume_missing():
        b,st,ds=fix();halt(b,ds[2],planned_resume_session=str(ds[3].date()));missing(ds[2]);b.open_phase(ds[2]);b.close_phase(ds[2]);missing(ds[3]);b.open_phase(ds[3]);assert b.states[SID]['state']=='UNKNOWN' and st['core']>0
    run('planned_resume_not_actual_price_evidence',planned_resume_missing)
    def no_ffill():
        b,st,ds=fix();s.facts[SID].pop(ds[1]);assert b.snapshot(ds[2],'OPEN').nav is None
    run('ordinary_missing_I_not_forward_filled',no_ffill)
    def fresh_unlock():
        b,st,ds=fix();halt(b,ds[2]);missing(ds[2]);b.open_phase(ds[2]);b.close_phase(ds[2]);b.open_phase(ds[3]);assert not st['added'] and b.pools[st['round_id']]=='probe'
        s.raw[SID][ds[3]]['raw_close']=120.;s.facts[SID][ds[3]]=dict(i_target=True,i_floor=115.);s.cp[SID][ds[3]]=dict(receipt=True,candidate=118.);s.raw[SID][ds[4]]['raw_open']=120.
        b.close_phase(ds[3]);assert b.pending_cp[st['round_id']]['signal_day']==ds[3];b.open_phase(ds[4]);assert st['added'] and b.pools[st['round_id']]=='confirmed'
    run('resume_CLOSE_fresh_CP_only_then_next_OPEN_ADD_and_promotion',fresh_unlock)
    def clock_no_future():
        b,st,ds=fix();c=event(ds);candidate(b,c)
        class NoFuture:
            def get(self,*a,**k):raise AssertionError('announcement improperly read market data')
        raw=s.raw[SID];s.raw[SID]=NoFuture()
        try:v=b.candidate_tape.project(ds[1],'OPEN');assert len(v)==1 and not any(k in v[0] for k in ('factor_new','factor_old','previous_close','previous_day'))
        finally:s.raw[SID]=raw
        bad=copy.deepcopy(c);bad['factor_new']='2'
        try:E.CandidateTape(s,[bad],synthetic=True)
        except ValueError:pass
        else:raise AssertionError('future factor admitted into announcement')
    run('announcement_can_be_known_without_any_future_coordinate_read',clock_no_future)
    def layer_entitlement():
        b,st,ds=fix();b.open_phase(ds[2]);q=st['core']+st['add'];assert st['add']>0;c=event(ds);candidate(b,c);b.close_phase(ds[2]);cl=next(iter(s.claims.values()))
        assert cl['record_q']==q and cl['core_record_q']==st['core'] and cl['amount']-cl['core_amount']==D(st['add'])*D('.8')
        oldfloor=st['addfloor'];fn=D(112)/D(111);s.raw[SID][ds[3]]['adjustment_factor']=float(fn);s.raw[SID][ds[4]]['adjustment_factor']=float(fn)
        cash=b.cash();b.open_phase(ds[3]);assert b.cash()==cash and b.receivable()==D(q)*D('.8');assert st['addfloor']==oldfloor/D(str(float(fn)))
        assert s.bridges[-1]['kind']=='HELD_COORDINATE';before=b.cash()+b.receivable();b.close_phase(ds[3]);assert b.cash()+b.receivable()==before and b.receivable()==0 and b.cash()==cash+D(q)*D('.8')
        assert s.claim_ledger[-1]['available_from']==ds[4]
        s.accrue_day(E.ARM,ds[3]);s.pay_day(E.ARM,ds[3]);assert b.cash()==cash+D(q)*D('.8')
    run('original_record_CORE_ADD_ex_coordinate_claim_pay_CLOSE_and_idempotence',layer_entitlement)
    def same_day_unknown():
        b,st,ds=fix();c=event(ds,clock=daily(str(ds[2].date())));candidate(b,c);b.open_phase(ds[2]);b.close_phase(ds[2]);assert not s.claims
        s.raw[SID][ds[3]]['adjustment_factor']=float(D(112)/D(111));b.open_phase(ds[3]);assert b.states[SID]['state']=='UNKNOWN' and st['core']>0 and not s.claims
    run('record_session_same_day_clock_cannot_retroactively_register',same_day_unknown)
    def missing_coordinate():
        b,st,ds=fix();c=event(ds);candidate(b,c);b.open_phase(ds[2]);b.close_phase(ds[2]);q=st['core']+st['add'];s.raw[SID][ds[3]]['adjustment_factor']=1.;b.open_phase(ds[3]);assert b.states[SID]['state']=='UNKNOWN' and b.receivable()==D(q)*D('.8') and b.snapshot(ds[3],'OPEN').nav is None
    run('public_cash_claim_does_not_certify_mismatching_market_factor',missing_coordinate)
    def old_round():
        b,st,ds=fix();c=event(ds,pay_date=str(ds[4].date()));candidate(b,c);b.open_phase(ds[2]);b.close_phase(ds[2]);cl=next(iter(s.claims.values()));rid=st['round_id'];st['exitpending']='SYNTHETIC_EXIT';st['addpending']=None
        fn=float(D(112)/D(111));s.raw[SID][ds[3]]['adjustment_factor']=fn;s.raw[SID][ds[4]]['adjustment_factor']=fn;b.open_phase(ds[3]);assert st['core']==st['add']==0 and st['receivable']>0 and SID not in b.states
        # Native new_state, separate identity, then source mark cannot borrow old claim.
        r=copy.deepcopy(st);r.update(round_id='SYNTHETIC_NEW',core=0,add=0,cash=D(0),receivable=D(0),dividend_total=D(0),dividend_paid=D(0));r.pop('_output_index',None)
        before=s.mark(r,D(100),ds[3]);st['receivable']+=D(999);assert s.mark(r,D(100),ds[3])==before;st['receivable']-=D(999)
        b.close_phase(ds[3]);b.open_phase(ds[4]);before=r['cash'];b.close_phase(ds[4]);assert cl['owner_round_id']==rid and cl['settled'] and r['cash']==before and st['dividend_paid']==cl['amount']
    run('execution_closed_old_round_claim_settles_old_owner_not_new_round_profit',old_round)
    def halt_register():
        b,st,ds=fix();c=event(ds,d_source='0',d_cash='1');candidate(b,c);halt(b,ds[2]);missing(ds[2]);q=st['core'];b.open_phase(ds[2]);b.close_phase(ds[2]);cl=next(iter(s.claims.values()));assert cl['record_q']==q and cl['core_record_q']==q and cl['owner_round_id']==st['round_id']
    run('known_halt_record_CLOSE_retains_actual_owner_quantities',halt_register)
    def q0():
        b,st,ds=fix(False);c=event(ds,record_date=str(ds[0].date()),ex_date=str(ds[1].date()),pay_date=str(ds[1].date()),d_source='10',d_cash='10');candidate(b,c)
        b.candidate_tape.project(ds[0],'CLOSE');s.register(b.states,E.ARM,ds[0]);assert not s.claims
        fn=float(D(100)/D(90));s.raw[SID][ds[1]]['adjustment_factor']=fn;b.open_phase(ds[1]);assert s.bridges[-1]['kind']=='PENDING_COORDINATE_Q0' and not s.claims
    run('native_pending_Q0_coordinate_without_unowned_cash_claim',q0)
    def insufficient_cash():
        from limits_v3 import ReserveBook,Exposure
        b,st,ds=fix();c=event(ds);candidate(b,c);b.open_phase(ds[2]);b.close_phase(ds[2]);q=st['core']+st['add']
        # A finite Decimal seed leaves less than 5 above the native prior-CLOSE reserve.
        prior_inventory=D(q)*D('112');cash=(prior_inventory*D('.1')/D('.9')).to_integral_value(rounding='ROUND_CEILING')+D(2)
        b.seed_cash=cash-st['cash'];b.daily_nav=cash+prior_inventory
        fn=float(D(112)/D(111));s.raw[SID][ds[3]]['adjustment_factor']=fn;s.raw[SID][ds[4]]['adjustment_factor']=fn
        b.open_phase(ds[3]);assert b.cash()==cash and b.receivable()==D(q)*D('.8')
        p=Exposure('SYNTH_OTHER','SYNTH_R','SYNTH_SEC','confirmed',1,D(5),D(5),D(0),'live')
        pre=ReserveBook(b.snapshot(ds[3],'OPEN'));assert 'cash_or_original_reserve' in pre.reasons(p)
        b.close_phase(ds[3]);assert b.cash()==cash+D(q)*D('.8') and b.receivable()==0
        post=ReserveBook(b.snapshot(ds[4],'OPEN'));assert post.reasons(p)==[]
        assert s.claim_ledger[-1]['available_from']==ds[4]
    run('native_claim_cannot_fund_cash_short_order_until_pay_CLOSE_next_OPEN',insufficient_cash)
    def ex_future_pollution():
        b,st,ds=fix();c=event(ds);candidate(b,c);b.open_phase(ds[2]);b.close_phase(ds[2]);s.raw[SID][ds[3]]['adjustment_factor']=float(D(112)/D(111))
        saved=b.capture_runtime();baseline=b.open_phase(ds[3]);actions=copy.deepcopy(s.actions);claims=copy.deepcopy(s.claims);bridges=copy.deepcopy(s.bridges)
        b.restore_runtime(saved)
        s.raw[SID][ds[3]].update(raw_close=1e8,raw_high=1e8,raw_low=.00001,raw_volume=1e15)
        s.facts[SID][ds[3]]=dict(i_target=False,i_floor=1e8);s.cp[SID][ds[3]]=dict(receipt=True,candidate=1e8);s.sector[st['sector']][ds[3]]=-1
        s.raw[SID][ds[4]].update(raw_open=1e8,raw_close=1e8,adjustment_factor=999.)
        poisoned=b.open_phase(ds[3]);assert poisoned==baseline and s.actions==actions and s.claims==claims and s.bridges==bridges
    run('ex_OPEN_unchanged_by_same_day_HLCV_I_CP_M3_and_future_bar_pollution',ex_future_pollution)
    def no_full_release():
        try:E.ExecutionBridge(s,evidence_domain='REAL_FROZEN_SOURCE')
        except E.StateInvariantError:pass
        else:raise AssertionError('candidate accidentally released account domain')
        b=E.ExecutionBridge(s,evidence_domain='REAL_DAILY_CONDITIONAL_FIXTURE')
        try:b._stage(s.pd.Timestamp('2022-05-16'),'OPEN')
        except E.StateInvariantError:pass
        else:raise AssertionError('fixture range expanded')
    run('default_full_account_domain_and_outside_fixture_dates_rejected',no_full_release)
    s.local_actions=native_local
    return out
