"""Source-definition synthetic tests. No original-data economic replay."""
from pathlib import Path
from decimal import Decimal as D
import ast,copy,json,types
import engine_v2 as E
SID='000876.SZ'
def fixture(s):
    b=E.ExecutionBridge(s,evidence_domain='SYNTHETIC_SOURCE_DEFINITION',
        cp_provider=lambda st,d:dict(consumption_id='SYNTHETIC|'+st['round_id']+'|'+str(d.date()),known_at=(d,'CLOSE'),identity_kind='SYNTHETIC_PROOF'))
    b.groups={};s.load(SID)
    days=[s.pd.Timestamp(x) for x in ['2022-01-05','2022-01-06','2022-01-07','2022-01-10']]
    raw={};facts={};cp={}
    for d in days:
        raw[d]=dict(raw_open=100.,raw_close=100.,adjustment_factor=1.,source_kind='SYNTHETIC',source_path='SYNTHETIC',segment_id='SYNTHETIC',observed_bar=True,price_eligible=True,volume_eligible=True,source_invalid=False,synthetic_event_bar=False)
        facts[d]=dict(i_target=True,i_floor=95.)
        cp[d]=dict(receipt=False,candidate=95.)
    raw[days[1]]['raw_close']=110.;facts[days[1]]['i_floor']=100.;cp[days[1]]=dict(receipt=True,candidate=108.)
    raw[days[2]].update(raw_open=112.,raw_close=112.);facts[days[2]]['i_floor']=100.
    s.raw[SID]=raw;s.facts[SID]=facts;s.cp[SID]=cp;s.capacity[SID]={d:100000 for d in days}
    r=s.ev[s.ev.sid.eq(SID)].iloc[0].to_dict();r.update(day=days[0],i_floor=95.,event_id='SYNTHETIC_BIRTH',PVR_score=1.,I_qualified=True,PVR_known=True)
    s.sector[r['sector']]={d:1 for d in days}
    s.EVENT_AT={};s.BY_RECORD={};s.BY_EX={};s.BY_PAY={}
    rid='SYNTHETIC|'+SID+'|1'
    st=s.new_state(r,E.ARM,rid,dict(close_q=200,prior20_capacity=100000))
    b.states[SID]=st;b.caps[rid]=D('1200000');b.seq[SID]=1;b.last_close=days[0]
    return b,st,days
def buy_and_close(s):
    b,st,ds=fixture(s);b.open_phase(ds[1]);b.close_phase(ds[1]);return b,st,ds
def test_suite(s):
    results=[]
    def run(name,fn):
        fn();results.append(dict(name=name,status='PASS',domain='SYNTHETIC_SOURCE_DEFINITION'))
    def phase_add_commit():
        b,st,ds=buy_and_close(s)
        assert b.pending_cp[st['round_id']]['first_fill_day']==ds[1]
        out=b.open_phase(ds[2]);assert st['added'] and st['add']>0 and b.pools[st['round_id']]=='confirmed'
        n=len(s.actions);cash=b.cash();order=next(o for o in b.orders.values() if o['kind']=='ADD')
        b.commit(order['order_id']);assert len(s.actions)==n and b.cash()==cash
        assert [a['side'] for a in s.actions]==['buy_core','buy_add']
        assert out['reconciliation']['cash_and_qty_reconciled']
        # An already used receipt cannot authorize another ADD.
        st['addpending']=D('108');p,reason=b._proof(st,ds[2]);assert p is None and reason=='CP_already_attempted'
    run('phase_aware_same_day_CP_single_ADD_and_idempotent_commit',phase_add_commit)
    def boundary():
        for op,expected in [('107.99',False),('108',False),('108.01',True)]:
            b,st,ds=buy_and_close(s);s.raw[SID][ds[2]]['raw_open']=float(op)
            b.open_phase(ds[2]);assert (b.pools[st['round_id']]=='confirmed')==expected
            if not expected:assert not st['added']
    run('promotion_O_below_equal_above_effective_CP_line',boundary)
    def zero_quantity():
        b,st,ds=buy_and_close(s);s.capacity[SID][ds[1]]=0
        b.open_phase(ds[2]);assert not st['added'] and b.pools[st['round_id']]=='confirmed'
        assert st['add_size_rejects']==1
    run('valid_proof_promotes_even_when_original_ADD_size_zero',zero_quantity)
    def unknown_preflight():
        b,st,ds=buy_and_close(s);s.capacity[SID][ds[1]]=s.np.nan
        b.open_phase(ds[2]);assert b.states[SID]['state']=='UNKNOWN'
        assert b.pools[st['round_id']]=='probe' and not any(a['type']=='PROMOTED' for a in b.audit)
        assert b.snapshot(ds[2],'OPEN').nav is None and st['core']==200
    run('ADD_unknown_preflight_blocks_all_promotion_before_commit',unknown_preflight)
    def negative_stale():
        b,st,ds=buy_and_close(s);s.raw[SID][ds[2]]['raw_open']=99.
        b.open_phase(ds[2]);assert not st['added'] and b.pools[st['round_id']]=='probe'
        b,st,ds=buy_and_close(s);b.pending_cp[st['round_id']]['signal_day']=ds[0]
        b.open_phase(ds[2]);assert not st['added'] and b.pools[st['round_id']]=='probe'
        b,st,ds=buy_and_close(s);b.pending_cp[st['round_id']]['round_id']='OLD_ROUND'
        b.open_phase(ds[2]);assert not st['added']
    run('negative_OPEN_stale_and_old_round_CP_reject',negative_stale)
    def source_equivalence():
        b,st,ds=buy_and_close(s);saved=b.capture_runtime();rid=st['round_id']
        s.held_open(b.states,SID,st,ds[2],ds[1])
        expected=copy.deepcopy(dict(st=st,actions=s.actions))
        b.restore_runtime(saved);st=s.archives[rid]
        b._callback('source_exit_only')(b.states,SID,st,ds[2],ds[1])
        p=b._callback('source_prepare_add',INIT=s.INIT,SLOT=s.SLOT,RISK=s.RISK)(b.states,SID,st,ds[2],ds[1],s.raw[SID][ds[2]])
        assert p is not None
        b._callback('source_commit_add')(st,ds[2],p['q'],p['fee'],p['price'],p['floor'],p['prior_net'])
        assert st==expected['st'] and s.actions==expected['actions']
    run('whole_source_held_OPEN_equals_split_exit_prepare_commit_no_shared_shrink',source_equivalence)
    def t1_and_fee():
        b,st,ds=buy_and_close(s);b.open_phase(ds[2]);st['exitpending']='SYNTHETIC_EXIT'
        before=(b.cash(),st['core'],st['add'],len(s.actions))
        try:b._check_exit_t1(st,ds[2])
        except E.StateInvariantError:pass
        else:raise AssertionError('same-day layer was sold')
        assert before==(b.cash(),st['core'],st['add'],len(s.actions))
        q=st['core']+st['add'];_,fs,par=s.getmeta(SID,ds[3]);px=D('100')*(1-s.SLIP);onefee=s.fee(q,px,fs,'sell',par)
        n=len(s.actions);b.last_close=ds[2];b.open_phase(ds[3])
        sell=s.actions[n:];assert len(sell)==1 and sell[0]['side']=='sell_all' and D(str(sell[0]['fee']))==onefee
        assert not b._active_layers(st['round_id']) and SID not in b.states
    run('per_fill_T1_reject_whole_illegal_exit_and_single_whole_order_fee',t1_and_fee)
    def unknown_liability():
        b,st,ds=fixture(s);s.raw[SID][ds[1]]['raw_open']=s.np.nan
        b.open_phase(ds[1]);assert b.states[SID]['state']=='UNKNOWN' and b.snapshot(ds[1],'OPEN').certified
        b,st,ds=buy_and_close(s);s.raw[SID][ds[2]]['raw_open']=s.np.nan
        b.open_phase(ds[2]);assert not b.snapshot(ds[2],'OPEN').certified and st['core']==200
    run('initial_no_liability_UNKNOWN_vs_owned_UNKNOWN',unknown_liability)
    def q0_and_tolerance():
        b,st,ds=fixture(s);d=ds[1];fn=D(100)/D(90)
        ev=dict(sid=SID,economic_event_id='SYNTHETIC_Q0',evidence_version='SYNTHETIC',record_date=ds[0],coordinate_snapshot_day=ds[0],ex_date=d,pay_date=d,entitlement_verified=False,d_cash=None,d_source=D(10),factor_old=D(1),factor_new=fn,previous_day=ds[0])
        s.EVENT_AT={(SID,d):ev};s.BY_RECORD={ds[0]:[ev]};s.register(b.states,E.ARM,ds[0]);s.raw[SID][d]['adjustment_factor']=float(fn)
        p=b._entry_proposal(st,d);assert p is not None and s.bridges[-1]['kind']=='PENDING_COORDINATE_Q0'
        assert p['floor']==D(95)/D(str(float(fn))) and not s.claims
        b,st,ds=fixture(s);s.raw[SID][ds[1]]['adjustment_factor']=1.+1e-12
        assert b._entry_proposal(st,ds[1]) is not None
    run('original_Q0_pending_bridge_and_factor_tolerance',q0_and_tolerance)
    def entitlement_and_old_round():
        b,st,ds=buy_and_close(s);rid=st['round_id'];q=st['core']
        ev=dict(sid=SID,economic_event_id='SYNTHETIC_ENTITLEMENT',evidence_version='SYNTHETIC',record_date=ds[1],coordinate_snapshot_day=ds[1],ex_date=ds[2],pay_date=ds[2],entitlement_verified=True,d_cash=D(1))
        s.BY_RECORD={ds[1]:[ev]};s.BY_EX={ds[2]:[ev]};s.BY_PAY={ds[2]:[ev]}
        s.register(b.states,E.ARM,ds[1]);cash=b.cash();s.accrue_day(E.ARM,ds[2]);amount=D(q)*D('.8')
        assert b.cash()==cash and st['receivable']==amount
        # Prior round entitlement cannot improve a new round's profit.
        new=copy.deepcopy(st);new.update(round_id='SYNTHETIC_NEW',receivable=D(0))
        baseline=s.mark(new,D('99'),ds[2]);st['receivable']+=D(999)
        assert s.mark(new,D('99'),ds[2])==baseline;st['receivable']-=D(999)
        before=b.cash()+b.receivable();s.pay_day(E.ARM,ds[2])
        assert b.cash()==cash+amount and b.receivable()==0 and before==b.cash()+b.receivable()
        assert s.claim_ledger[-1]['available_from']==ds[3]
        s.pay_day(E.ARM,ds[2]);s.accrue_day(E.ARM,ds[2]);assert b.cash()==cash+amount
    run('NET80_registered_layers_ex_receivable_pay_CLOSE_next_OPEN_old_round_isolation',entitlement_and_old_round)
    def dynamic_cache_reentry():
        b,st,ds=fixture(s);r=dict(st);r['day']=ds[0];r['i_floor']=95.
        b.close_nd=D('1200000');q1=b._checkclose(r)['close_q'];b.close_nd=D('600000');q2=b._checkclose(r)['close_q']
        assert q2<q1 and (s.INIT,s.RISK,s.SLOT,s.NAV)==(D(24000),D(3000),D(48000),D(1200000))
        b,st,ds=buy_and_close(s);st['exitpending']='SYNTHETIC_EXIT';st['addpending']=None;b.open_phase(ds[2])
        assert SID not in b.states
        newr=dict(st);newr.update(day=ds[2],event_id='SYNTHETIC_FRESH_BIRTH',i_floor=95.)
        b.groups={ds[2]:s.pd.DataFrame([newr])};b.close_phase(ds[2])
        assert b.states[SID]['state']=='BUY_PENDING' and b.states[SID]['round_id']!=st['round_id']
        assert st['core']==0 and st['round_id'] in s.archives
    run('per_round_dynamic_CLOSE_cache_and_fresh_signal_reentry',dynamic_cache_reentry)
    def unadmitted2024():
        b,st,ds=fixture(s)
        path=E.bridge.EVENT_ROOT/'cash_equity_baseline_2024_v1/engine.py';text=path.read_text();node=next(n for n in ast.parse(text).body if isinstance(n,ast.FunctionDef) and n.name=='unadmitted_action_at')
        env=dict(s.__dict__);env['local_actions']=lambda sid:dict(events=[dict(effective_date=str(ds[1].date()))])
        ns={};exec(compile(ast.Module(body=[node],type_ignores=[]),str(path)+':synthetic_definition_only','exec'),env,ns)
        s.unadmitted_action_at=types.FunctionType(ns['unadmitted_action_at'].__code__,env)
        try:
            assert b._entry_proposal(st,ds[1]) is None and b.states[SID]['unknown_reason']=='UNADMITTED_ACTION_AT_ENTRY_UNKNOWN'
            b,st,ds=fixture(s);s.raw[SID][ds[1]]['raw_open']=s.np.nan
            assert b._entry_proposal(st,ds[1]) is None and b.states[SID]['unknown_reason']=='MISSING_NEXT_OPEN_UNKNOWN'
        finally:del s.unadmitted_action_at
    run('exact_2024_unadmitted_source_definition_and_entry_validation_order',unadmitted2024)
    return results
