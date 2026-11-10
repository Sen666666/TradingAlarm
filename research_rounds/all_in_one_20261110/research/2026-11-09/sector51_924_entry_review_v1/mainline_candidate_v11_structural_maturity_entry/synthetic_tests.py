"""27 contract groups, synthetic prices only. Never instantiate Data or call a history runner."""
from pathlib import Path
from types import SimpleNamespace
import copy
import importlib.util
import json
import sys
import traceback

sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('v11_synthetic_engine', P / 'engine.py')
e = importlib.util.module_from_spec(spec); sys.modules[spec.name] = e; spec.loader.exec_module(e)
sh, D, pd, Z = e.sh, e.D, e.pd, e.ZERO
CAL = pd.bdate_range('2001-01-01', periods=45)
dt, nxt, later = CAL[7], CAL[8], CAL[9]
ORIGIN = ('synthetic', 'memory://fixture', '0')
CHECKS = []


def check(name, condition=True):
    assert condition, name
    CHECKS.append(name)


def raises(kind, call):
    try:
        call()
    except kind:
        return True
    return False


class Fee:
    components = [SimpleNamespace(name='net_brokerage', side='both')]
    def incremental(self, side, value, *a, **kw):
        return {'net_brokerage': max(D(5), value * D('.0002'))}
    def rate_accrual(self, side, value, *a, **kw):
        return {'net_brokerage': value * D('.0002')}


class SyntheticData:
    def __init__(self):
        self.cal = CAL
        self.days = CAL[6:20]
        self.ids = ['a', 'b', 'old']
        self.names = {s: s for s in self.ids}
        self.sid_sector = {'a': 'A', 'b': 'A', 'old': 'OLD'}
        self.sector_ids = ['A', 'OLD']
        self.events = {}; self.hashes = {}; self.manifest = {}; self.admission = []; self.excluded = []
        self.prices = {}; self.fact_rows = {}; self.cp_rows = {}; self.main_rows = {}; self.actions = {}
        self.stock = pd.DataFrame(1, index=CAL, columns=self.ids)
        self.cap = {s: pd.Series(100000, index=CAL) for s in self.ids}
        self.sectors = {s: pd.DataFrame(dict(state=1, N=3, K=3, n=3, U=0, paired_K=3,
                       entered3=0, left3=0, diff=1, strength=True), index=CAL) for s in self.sector_ids}
        for fr in self.sectors.values(): fr.iloc[0, fr.columns.get_loc('state')] = 0
    def z(self, s, d):
        base = dict(raw_open=10., raw_high=10.1, raw_low=9.9, raw_close=10., raw_volume=10000000.,
                    close=10., adjustment_factor=1., source_kind='synthetic', source_path='memory://fixture',
                    segment_id=0, observed_bar=True, price_eligible=True, volume_eligible=True,
                    source_invalid=False, synthetic_event_bar=False)
        base.update(self.prices.get((s, d), {}))
        return base
    @property
    def raw(self):
        return {s: pd.DataFrame([self.z(s, d) for d in CAL], index=CAL) for s in self.ids}
    def f(self, s, d):
        return dict(i_target=True, i_floor=5.) | self.fact_rows.get((s, d), {})
    def c(self, s, d):
        return self.cp_rows.get((s, d), dict(ready=True, receipt=False, candidate=None))
    def m(self, s, d):
        defaults = dict(M=1, E=1., M_streak=2, W=False, S=1, F=0, Q=1, rs5=.1,
                        rs10=.1, rs20=.1, return5_median=0., return10_median=.1, breakout20_count=0)
        return SimpleNamespace(**(defaults | self.main_rows.get((s, d), {})))
    @property
    def main(self):
        return {sec: pd.DataFrame([vars(self.m(next(s for s in self.ids if self.sid_sector[s] == sec), d))
                                  for d in CAL], index=CAL) for sec in self.sector_ids}
    def getmeta(self, s, d):
        return (e.m4.b.QuantityRule('synthetic', 100, 100, 100, True, 1), Fee(), D(1))
    def fee(self, s, d, q, p, side):
        return max(D(5), q * p * D('.0002')) if q else Z
    def size(self, s, d, p, budget, cap):
        qr = self.getmeta(s, d)[0]
        q = qr.buy_floor(max(0, min(int(budget / p), int(cap))))
        while q and q*p + self.fee(s, d, q, p, 'buy') > budget: q = qr.buy_floor(q-1)
        return q
    def action(self, s, d):
        return self.actions.get((s, d), [])


def seed(s='a', when=dt, nav=D(1200000)):
    return dict(kind='SEED', sid=s, birth_type='B', signal_day=e.day(when), plan_day=e.day(when),
                budget=D('.02')*nav, planned_q=100, capacity=100000, ifloor=D(5), factor=D(1),
                origin=ORIGIN, nav0=nav, M=1, E=D(1), M_streak=2)


def setup(*, fast=0, receipt=False, candidate=8, phase='MATURE', enabled=True):
    x = e.Engine(SyntheticData(), enabled=enabled)
    x.d.main_rows[('a', dt)] = {'F': fast}
    x.d.cp_rows[('a', dt)] = dict(receipt=receipt, candidate=candidate, ready=True)
    x.sync_events(CAL[6])
    for event in x.events.values(): event['cold_start'] = False
    if phase != 'EVENT': x.events[x.current_event['A']]['priority_attempted'] = True
    if phase == 'RESIDUAL': x.d.main_rows[('a', dt)].update(M=0, E=0)
    r = seed(); x.decorate(r, dt); x.plan_transfers(dt, [r])
    return x, r


def open_at(x, r, when=nxt):
    pending = [r]
    x.economic_preflight(when, pending)
    x.accrue(when); x.exit_open(when); x.alloc_open(when, pending)
    return pending


def next_plan(x, when=nxt):
    rows = x.refresh_tickets(when)
    x.plan_transfers(when, rows)
    return rows


def pure(receipt=False, floor=8):
    log = []; s = sh.new_shadow(seed(), e.MODEL_SHA)
    sh.observe_close(s, e.day(dt), raw_open=10, raw_close=10, factor=1, origin=ORIGIN,
                     receipt=receipt, candidate=floor, log=log)
    return s, log


def close_pure(s, log, when=nxt, *, op=10, cl=10, receipt=False, candidate=None, **kw):
    return sh.observe_close(s, e.day(when), raw_open=op, raw_close=cl, factor=kw.get('factor',1),
             origin=kw.get('origin',ORIGIN), receipt=receipt, candidate=candidate,
             source_valid=kw.get('source_valid',True), log=log)


def hold(x, s='old', qty=10000, role='EXPANSION'):
    a = dict(id=s+'|fixture', sid=s, signal_day=e.day(CAL[3]), birth_type='B', nav0=D(1200000),
             seed_day=e.day(CAL[4]), cashflow=-D(qty)*D(9), dividend=Z, fees=D(5), ifloor=D(5),
             factor=D(1), origin=ORIGIN, exit=None, plan=None, cp=None, add_count=0,
             confirmed_history=True, lots=[dict(id=s+'|lot', kind='SEED', q=qty, bought=e.day(CAL[4]),
                                                  floor=D(5), cp_id=None, capital_role=role)])
    x.active[s] = a; x.archive[a['id']] = a
    x.orders.append(dict(side='BUY_SEED', round_id=a['id'], lot_id=s+'|lot', qty=qty, order_seq=1))
    return a


def test_01_truth_table():
    expected = [[1,1,1],[1,0,-1],[1,-1,-1]]
    for i,a in enumerate([1,0,-1]):
        for j,b in enumerate([1,0,-1]): check(f'01_or_{a}_{b}', sh.tri_or(a,b)==expected[i][j])
    check('01_F_unknown_CP_false_pauses', sh.gate('MATURE','SEED',1,1,True,True,-1,0)==-1)
    for args in [(0,1,True,True),(1,0,True,True),(1,1,False,True),(1,1,True,False)]:
        check('01_invalid_mature_never_passes_'+str(args), raises(AssertionError,lambda:sh.gate('MATURE','SEED',*args,1,1)))


def test_02_bypass():
    for phase in ['EVENT','RESIDUAL']:
        x,r=setup(phase=phase); y,q=setup(phase=phase,enabled=False)
        check('02_'+phase+'_same_plan', r['_ref_q']==q['_ref_q'] and r['econ_q']==q['econ_q'] and r['budget']==q['budget'])
        open_at(x,r);open_at(y,q)
        clean=lambda rows:[{k:v for k,v in row.items() if k!='entry_evidence_id'} for row in rows]
        check('02_'+phase+'_same_orders',clean(x.orders)==clean(y.orders))
    check('02_ADD_bypass',sh.gate('MATURE','ADD',-1,0,False,False,-1,-1)==1)


def test_03_signal_boundary():
    s=sh.new_shadow(seed(),e.MODEL_SHA);log=[]
    close_pure(s,log,CAL[6],receipt=True,candidate=8)
    check('03_pre_signal_rejected',s['slot'] is None)
    close_pure(s,log,dt,receipt=True,candidate=8)
    check('03_same_signal_accepted',sh.state(s)==1 and s['slot']['receipt_day']==e.day(dt))


def test_04_receipt_open_time():
    s=sh.new_shadow(seed(),e.MODEL_SHA);log=[]
    close_pure(s,log,dt,op=7,cl=10,receipt=True,candidate=8)
    check('04_birth_open_not_retroactive',sh.state(s)==1)
    sh.observe_open(s,e.day(nxt),raw=8,factor=1,origin=ORIGIN,log=log)
    check('04_next_open_checked',sh.state(s)==0)


def test_05_absorbing_breach():
    for phase in ['OPEN','CLOSE']:
        s,log=pure(True)
        if phase=='OPEN':sh.observe_open(s,e.day(nxt),raw=8,factor=1,origin=ORIGIN,log=log)
        else:close_pure(s,log,nxt,op=10,cl=8)
        close_pure(s,log,later,op=12,cl=12)
        check('05_equal_'+phase+'_permanent',sh.state(s)==0 and s['slot']['invalid'])


def test_06_single_slot():
    s,log=pure(True,9);old=s['slot']['id'];close_pure(s,log,nxt,receipt=True,candidate=8)
    check('06_lower_new_floor_replaces',s['slot']['floor']==8 and s['slot']['id']!=old and any(r['event']=='SUPERSEDED' for r in log))
    close_pure(s,log,later,receipt=True,candidate=9)
    close_pure(s,log,CAL[10],op=8.5,cl=10)
    check('06_no_older_lower_rescue',sh.state(s)==0)


def test_07_anomalous_receipt():
    s,log=pure(True,8);old=s['slot']['id'];close_pure(s,log,nxt,receipt=True,candidate=10)
    check('07_breached_receipt_preserves_old',s['slot']['id']==old and sh.state(s)==1)
    close_pure(s,log,later,receipt=True,candidate=float('nan'))
    check('07_invalid_candidate_unknown',sh.state(s)==-1 and s['slot']['id']==old)
    close_pure(s,log,CAL[10],receipt=False)
    check('07_invalid_candidate_gap_persistent',sh.state(s)==-1)


def test_08_false_missing_unready():
    s,log=pure(True);old=s['slot']['id'];close_pure(s,log,nxt,receipt=False)
    check('08_explicit_false_preserves',s['slot']['id']==old and sh.state(s)==1)
    close_pure(s,log,later,receipt=None);check('08_missing_is_unknown',sh.state(s)==-1)
    close_pure(s,log,CAL[10],receipt=False);check('08_false_cannot_erase_gap',sh.state(s)==-1)
    x,r=setup(receipt=True);open_at(x,r) # separate pure boolean source assertion
    s,log=pure(False);check('08_known_unprepared_false_is_false',sh.state(s)==0)
    check('08_nonboolean_receipt_unknown',all(sh.bool_state(v)==-1 for v in [0,1,'False','True',None]))


def test_09_unknown_suffix():
    s,log=pure(True);close_pure(s,log,nxt,op=None,cl=10)
    check('09_unknown_price_gap',sh.state(s)==-1)
    close_pure(s,log,later);check('09_recovery_no_retroactive_proof',sh.state(s)==-1)
    close_pure(s,log,CAL[10],receipt=True,candidate=9)
    check('09_new_receipt_resets_suffix',sh.state(s)==1)
    s,log=pure(True);close_pure(s,log,nxt,origin=('synthetic',None,0))
    check('09_unknown_origin_not_known_change',sh.state(s)==-1)


def test_10_false_and_unknown():
    for which in ['i','stock','sector']:
        x,r=setup();open_at(x,r)
        if which=='i':x.d.fact_rows[('a',nxt)]={'i_target':False}
        if which=='stock':x.d.stock.at[nxt,'a']=0
        if which=='sector':x.d.sectors['A'].at[nxt,'state']=0
        x.d.main_rows[('a',nxt)]={'F':1};x.d.cp_rows[('a',nxt)]={'receipt':True,'candidate':8}
        rows=next_plan(x)
        check('10_'+which+'_false_cancels_even_F_CP',x.tickets['a']['status']=='CANCELLED' and 'a' not in x.entry_shadows and not rows)
    x,r=setup();open_at(x,r);identity=e.rules.immutable_identity(x.tickets['a'])
    x.d.stock.at[nxt,'a']=-1;x.d.fact_rows[('a',nxt)]={'i_floor':6}
    rows=next_plan(x)
    check('10_unknown_preserves_ratchets',not rows and x.tickets['a']['ifloor']==6 and e.rules.immutable_identity(x.tickets['a'])==identity)
    x.d.stock.at[nxt,'a']=1;x.d.fact_rows[('a',nxt)]={'i_target':True,'i_floor':None}
    rows=next_plan(x);check('10_current_I_floor_unknown_pauses',not rows and x.tickets['a']['status']=='PAUSED')


def test_11_event_retention_observation():
    x,r=setup(phase='EVENT',receipt=True)
    old=x.entry_shadows['a']['slot']['id'];hold(x,qty=110000);x.cash=D(100)
    open_at(x,r)
    check('11_event_capital_retained',x.tickets['a']['status']=='RETAINED' and x.entry_shadows['a']['slot']['id']==old)
    rows=next_plan(x)
    check('11_mature_uses_signal_cp',rows[0]['allocation_phase']=='MATURE' and rows[0]['_entry_gate_close']==1 and rows[0]['_entry_plan_cp_id']==old)


def test_12_phase_downshift():
    x,r=setup();open_at(x,r)
    x.d.main_rows[('a',nxt)]={'M':0,'E':0,'F':0};rows=next_plan(x)
    check('12_residual_small_only',rows[0]['allocation_phase']=='RESIDUAL' and rows[0]['_entry_gate_close']==1 and x.reference['D']['A']==0)
    x.economic_preflight(later,[]);x.d.main_rows[('a',later)]={'M':1,'E':1,'F':0};rows=next_plan(x,later)
    check('12_mature_rechecks',rows[0]['allocation_phase']=='MATURE' and rows[0]['_entry_gate_close']==0 and x.reference['D']['A']==0)


def test_13_cash_bridge():
    x,r=setup(receipt=True);x.create_structure_wait(r,dt,0);t=x.tickets['a'];floor=x.entry_shadows['a']['slot']['floor']
    ev=dict(record_date=e.day(dt),ex_date=e.day(nxt),pay_date=e.day(later),factor_old='1',factor_new='1.1',d_cash='1',event_type='PURE_CASH',economic_event_id_candidate='synthetic-cash')
    x.d.events[('a',nxt)]=ev;x.d.actions[('a',nxt)]=[{'type':'synthetic_cash'}]
    x.d.prices[('a',nxt)]={'raw_open':9.5,'raw_close':9.5,'close':10.45,'adjustment_factor':1.1}
    x.register_pay(dt);x.economic_preflight(nxt,[]);x.accrue(nxt);x.register_pay(later)
    check('13_verified_bridge_floor_not_rescaled',x.entry_shadows['a']['slot']['floor']==floor and t['current_factor']==D('1.1'))
    check('13_zero_position_entitlement_zero',x.snapshots[('a',e.day(dt))]['q']==0 and x.receivable==0 and not x.claims and x.cash==D(1200000))
    bad=copy.deepcopy(x.entry_shadows['a']);bad['current_factor']=D('1.21')
    check('13_double_factor_rejected',raises(ValueError,lambda:sh.observe_open(bad,e.day(later),raw=9.5,factor=1.1,origin=ORIGIN,log=[])))
    # Model the verified ticket produced by the inherited ST CLOSE bridge validator.
    x.entry_shadows['a']['current_factor']=D(1)
    t['last_verified_day']=e.day(nxt);t['current_factor']=D('1.1');t['status']='RETAINED'
    x.d.cp_rows[('a',nxt)]={'receipt':True,'candidate':9}
    x.observe_shadow_close('a',nxt)
    check('13_verified_close_bridge_sync_allows_same_close_receipt',x.entry_shadows['a']['current_factor']==D('1.1') and x.entry_shadows['a']['slot']['receipt_day']==e.day(nxt))



def test_14_actions_source():
    for mode in ['unadmitted','factor','badbridge']:
        x,r=setup()
        if mode=='unadmitted':x.d.actions[('a',nxt)]=[{'type':'cash'}]
        if mode=='factor':x.d.prices[('a',nxt)]={'adjustment_factor':1.1}
        if mode=='badbridge':
            x.d.prices[('a',nxt)]={'adjustment_factor':1.1}
            x.d.events[('a',nxt)]=dict(factor_old='2',factor_new='1.1')
        before=copy.deepcopy({k:v for k,v in vars(x).items() if k!='d'});pending=[]
        check('14_'+mode+'_atomic_block',raises(e.Blocked,lambda:x.atomic_step(nxt,pending,dt)))
        check('14_'+mode+'_all_state_rollback',{k:v for k,v in vars(x).items() if k!='d'}==before)
    x,r=setup(receipt=True);x.create_structure_wait(r,dt,0);x.d.prices[('a',nxt)]={'segment_id':1};p=[r];x.economic_preflight(nxt,p)
    check('14_known_source_cancel_clears_slot',not p and 'a' not in x.entry_shadows and x.tickets['a']['status']=='CANCELLED')
    x,r=setup();x.d.prices[('a',nxt)]={'source_path':'unknown'};p=[r];x.economic_preflight(nxt,p)
    check('14_unknown_string_pauses_not_cancels',not p and x.tickets['a']['status']=='PAUSED_NO_QUOTE' and 'a' in x.entry_shadows)
    x.economic_preflight(later,[])
    check('14_unknown_string_gap_recovery_not_source_cancel',x.tickets['a']['status']=='RETAINED' and 'a' in x.entry_shadows and 'a' not in x.quote_gaps and sh.state(x.entry_shadows['a'])==-1)
    check('14_integer_segment_canonicalizes',e.origin(x.d.z('b',dt))==ORIGIN)


def test_15_quote_gap_recovery():
    x,r=setup();x.d.prices[('a',nxt)]={'raw_open':None,'raw_close':None};p=open_at(x,r)
    check('15_missing_quote_pauses',not p and x.tickets['a']['status']=='PAUSED_NO_QUOTE')
    p=[r];x.economic_preflight(later,p);x.alloc_open(later,p)
    check('15_recovery_open_no_old_fill',not p and not x.orders and sh.state(x.entry_shadows['a'])==-1)
    x.d.cp_rows[('a',later)]={'receipt':True,'candidate':8};rows=next_plan(x,later)
    check('15_recovery_close_new_plan',len(rows)==1 and rows[0]['plan_day']==e.day(later) and rows[0]['_entry_gate_close']==1)
    open_at(x,rows[0],CAL[10]);check('15_original_missing_lookback_still_blocks',not x.orders and rows[0]['score_known'] is False)
    for k in range(10,16):
        if 'a' in x.active: break
        rows=next_plan(x,CAL[k])
        if rows: open_at(x,rows[0],CAL[k+1])
    check('15_fills_only_after_original_lookback_recovers',len(x.orders)==1)
    x,r=setup();x.d.prices[('a',nxt)]={'raw_open':None};x.d.actions[('a',nxt)]=[{'type':'cash'}]
    x.economic_preflight(nxt,[r]);check('15_Q0_action_inventory_preserved',bool(x.quote_gaps['a']['action_inventory']))
    check('15_recovery_unadmitted_blocks',raises(e.Blocked,lambda:x.economic_preflight(later,[])))


def test_16_open_gate():
    for fast,price,expected in [(0,8,'STRUCTURE_WAIT'),(-1,8,'STRUCTURE_PAUSED_UNKNOWN'),(0,5,'CANCELLED')]:
        x,r=setup(fast=fast,receipt=True);x.d.prices[('a',nxt)]={'raw_open':price};open_at(x,r)
        check('16_OPEN_'+str((fast,price)),(x.tickets['a']['status']==expected if expected!='CANCELLED' else 'a' not in x.live_tickets() and 'a' not in x.entry_shadows) and not x.orders)
    x,r=setup(fast=1,receipt=True);x.d.prices[('a',nxt)]={'raw_open':8};open_at(x,r)
    check('16_F_true_bypasses_cp',len(x.orders)==1)
    x,r=setup(fast=1,receipt=True);x.d.prices[('a',nxt)]={'raw_open':5};open_at(x,r)
    check('16_F_true_does_not_bypass_I',not x.orders and 'a' not in x.entry_shadows)
    x,r=setup(receipt=True);x.d.prices[('a',nxt)]={'raw_open':8};x.alloc_open(nxt,[r])
    check('16_call_level_alloc_same_wait',x.tickets['a']['status']=='STRUCTURE_WAIT')


def test_17_original_execution_failures():
    for mode in ['budget','capacity','dated']:
        x,r=setup(receipt=True);y,q=setup(receipt=True,enabled=False)
        for eng,req in [(x,r),(y,q)]:
            if mode=='budget':eng.d.prices[('a',nxt)]={'raw_open':100}
            if mode=='capacity':req['capacity']=700
            if mode=='dated':
                old=eng.d.getmeta;eng.d.getmeta=lambda s,d,old=old:(e.m4.b.QuantityRule('changed',1000,100,100,True,1),Fee(),D(1)) if d==nxt else old(s,d)
        open_at(x,r);open_at(y,q)
        check('17_'+mode+'_unchanged_reject',not x.orders and not y.orders and x.candidates[-1]['decision']==y.candidates[-1]['decision'])
    check('17_ST_limit_methods_exact',e.Engine.no_fill is e.base.Engine.no_fill and e.Engine.buy_nofill is e.base.Engine.buy_nofill)
    # The date is required to trigger the frozen ST adapter, but all prices are artificial.
    x=e.Engine(SyntheticData());sid=e.base.v.SID;signal=pd.Timestamp('2024-11-06');halt=pd.Timestamp('2024-11-07')
    event=x.create_event('A',signal,signal,D(1200000));event['priority_attempted']=True;event['spent']=D(123)
    r=seed(sid,signal);r['event_id']=event['event_id'];x.ensure_shadow(r);x.create_structure_wait(r,signal,0)
    identity=e.rules.immutable_identity(x.tickets[sid]);event_before=copy.deepcopy(event)
    x.d.prices[(sid,halt)]={'raw_open':None,'raw_close':None};pending=[r]
    x.economic_preflight(halt,pending)
    check('17_ST_halt_existing_structure_ticket_Q0_no_assert_no_fill',not pending and not x.orders and x.tickets[sid]['status']=='PAUSED_NO_QUOTE' and sid in x.quote_gaps and any(v['event']=='EXISTING_TICKET_NO_FILL_PRESERVED' for v in x.execution_boundary_log))
    check('17_ST_halt_no_identity_cash_entitlement_priority_change',len(x.tickets)==1 and e.rules.immutable_identity(x.tickets[sid])==identity and x.events[event['event_id']]==event_before and x.cash==1200000 and x.receivable==0 and not x.claims and not x.paused_new_requests)
    for status in ['CANCELLED','CONSUMED']:
        y=e.Engine(SyntheticData());rr=seed(sid,signal);y.ensure_shadow(rr);y.create_structure_wait(rr,signal,0);y.tickets[sid]['status']=status
        stale=[rr];y.economic_preflight(halt,stale)
        check('17_ST_terminal_'+status+'_not_resurrected',not stale and not y.paused_new_requests and not y.live_tickets() and sid not in y.entry_shadows)


    for mode in ['attempt','stock']:
        x=e.Engine(SyntheticData());x.sync_events(CAL[6]);x.events[x.current_event['A']]['priority_attempted']=True
        r=seed(nav=D(100000) if mode=='attempt' else D(1200000))
        if mode=='stock':x.cash=D(10000)
        x.decorate(r,dt);x.plan_transfers(dt,[r]);open_at(x,r)
        check('17_original_'+mode+'_reject_not_structure_retained','a' not in x.live_tickets() and not x.orders and 'a' not in x.entry_shadows)



def test_18_demand_and_donor():
    x,r=setup();check('18_wait_zero_D_q_cost',x.reference['D']['A']==0 and r['_ref_q']==0 and r['_reference_close_cost']==0 and not x.transfer_plan)
    x,r=setup(fast=-1);check('18_unknown_zero_D',x.reference['D']['A']==0)
    x=e.Engine(SyntheticData());a=hold(x,qty=110000);x.cash=D(100);x.d.main_rows[('old',dt)]={'M':0,'E':0};x.d.main_rows[('old',nxt)]={'M':0,'E':0};x.d.cp_rows[('a',dt)]={'receipt':True,'candidate':8}
    x.sync_events(CAL[6]);x.events[x.current_event['A']]['priority_attempted']=True;r=seed(nav=x.nav(dt,'raw_close'));x.decorate(r,dt);x.plan_transfers(dt,[r])
    check('18_donor_plan_exists_for_legal_receiver',bool(x.transfer_plan))
    oldorders=len(x.orders);x.d.prices[('a',nxt)]={'raw_open':8};open_at(x,r)
    check('18_failed_receiver_no_donor_sale',len(x.orders)==oldorders and any(row.get('decision')=='RECEIVER_GAP_ZERO' for row in x.transfers))


def test_19_real_structure_ticket():
    x,r=setup();t=x.tickets['a'];check('19_cash_abundant_structure_ticket',x.cash==1200000 and t['status']=='STRUCTURE_WAIT' and t['first_reject_caps']==[] and t['creation_reason']=='STRUCTURE_GATE')
    check('19_helper_meaning_not_changed',e.rules.ticket_from_seed(r,D(100),dict(cash_reserve=D(1000))) is None)


def test_20_identity_and_repeat():
    x,r=setup();t=x.tickets['a'];identity=e.rules.immutable_identity(t);ev=copy.deepcopy(x.events[r['event_id']]);born=sum(v['event']=='BORN_WITH_ORIGINAL_A_B' for v in x.entry_log)
    x.prepare_requests(dt,[r]);check('20_repeated_prepare_no_new_ticket',len(x.tickets)==1 and sum(v['event']=='BORN_WITH_ORIGINAL_A_B' for v in x.entry_log)==born and e.rules.immutable_identity(t)==identity)
    open_at(x,r);rows=next_plan(x);check('20_identity_budget_event_preserved',e.rules.immutable_identity(t)==identity and t['event_id']==r['event_id'] and x.events[r['event_id']]['spent']==ev['spent'] and x.events[r['event_id']]['priority_attempted']==ev['priority_attempted'])
    check('20_original_sort_exact',e.Engine.stock_key is e.base.Engine.stock_key and e.Engine.request_key_groups is e.base.Engine.request_key_groups)


def test_21_duplicate_and_rebirth():
    x,r=setup(receipt=True);x.create_structure_wait(r,dt,0);old=x.entry_shadows['a']['slot']['id'];x.economic_preflight(nxt,[])
    x.d.stock.at[dt,'a']=0;x.d.stock.at[nxt,'a']=1
    rows=x.close(nxt,dt)
    check('21_second_AB_no_parallel_ticket',len([r for r in rows if r['sid']=='a'])==1 and len(x.entry_shadows)==1 and x.tickets['a']['signal_day']==e.day(dt))
    e.rules.cancel(x.tickets['a'],'TEST_OLD_CANCEL');x.sync_terminal(later)
    new=seed(when=later);s=x.ensure_shadow(new);x.observe_shadow_close('a',later)
    check('21_rebirth_no_pre_signal_cp',s['identity']['ticket_id']!=x.tickets['a']['ticket_id'] and s['slot'] is None)
    x.d.cp_rows[('a',later)]={'receipt':True,'candidate':8}
    # Fresh knowledge is formed in a new object at the new signal CLOSE; no old receipt copied.
    x.entry_shadows.pop('a');x.ensure_shadow(new);x.decorate(new,later);x.plan_transfers(later,[new])
    check('21_old_cancelled_ticket_not_overwritten_by_ready',x.tickets['a']['status']=='CANCELLED' and new['_entry_gate_close']==1)
    open_at(x,new,CAL[10])
    check('21_old_cancelled_identity_cannot_cancel_new_ready',bool(x.orders) and x.orders[-1]['signal_day']==e.day(later))


def test_22_postseed_isolation():
    x,r=setup(receipt=True);entryid=x.entry_shadows['a']['slot']['id'];open_at(x,r);a=x.active['a']
    check('22_entry_only_order_audit',a['cp'] is None and a['confirmed_history'] is False and a['add_count']==0 and x.orders[-1]['entry_evidence_id']==entryid and 'a' not in x.entry_shadows)
    x.d.cp_rows[('a',nxt)]={'receipt':True,'candidate':8};x.d.prices[('a',nxt)]={'raw_open':10,'raw_close':12,'close':12,'raw_high':12.1};x.close(nxt,dt)
    check('22_actual_seed_day_close_CP_allowed',a['cp'] is not None and a['cp']['id']!=entryid and a['cp']['date']==e.day(nxt) and not a['cp']['consumed'])
    check('22_postseed_original_methods',e.Engine.close is e.base.Engine.close and e.Engine.info_close is e.base.Engine.info_close and e.Engine.info_open is e.base.Engine.info_open)


def test_23_atomic_all_state():
    class Forced(e.Engine):
        def close(self,d,prev):
            self.entry_shadows['new']={'future':True};self.entry_archive.append({'future':True})
            self.entry_log.append({'future':True});self.entry_decisions.append({'future':True})
            self._entry_preflight_excluded.add('bad');self._score_cache['new']=True
            self.future_attr='must vanish';raise e.Blocked('SYNTHETIC_AFTER_OPEN_BUY')
    x,r=setup(receipt=True);y=Forced(x.d);vars(y).update(copy.deepcopy({k:v for k,v in vars(x).items() if k!='d'}))
    before=copy.deepcopy({k:v for k,v in vars(y).items() if k!='d'});p=[r];prior=copy.deepcopy(p)
    for attempt in range(2):
        check('23_blocked_'+str(attempt),raises(e.Blocked,lambda:y.atomic_step(nxt,p,dt)))
        check('23_complete_state_log_rollback_'+str(attempt),{k:v for k,v in vars(y).items() if k!='d'}==before and p==prior)
    x,r=setup(receipt=True);state0=copy.deepcopy({k:v for k,v in vars(x).items() if k!='d'});p=[r];p0=copy.deepcopy(p);x.atomic_step(nxt,p,dt);result1=copy.deepcopy({k:v for k,v in vars(x).items() if k!='d'})
    for k in list(vars(x)):
        if k!='d':delattr(x,k)
    vars(x).update(copy.deepcopy(state0));p=copy.deepcopy(p0);x.atomic_step(nxt,p,dt)
    check('23_reapply_from_same_checkpoint_deterministic',{k:v for k,v in vars(x).items() if k!='d'}==result1)


def test_24_market_model_synthetic_paths():
    import numpy as np
    model=e.module('v11_actual_CP_model',e.MODEL)
    idx=pd.bdate_range('2000-01-03',periods=180)
    paths={'slow':np.r_[np.full(70,10.),10*np.exp(np.arange(110)*.0005)],
           'jump_flat':np.r_[np.full(70,10.),np.full(110,12.)],
           'never':np.full(180,10.)}
    outputs={}
    for name,prices in paths.items():
        f=pd.DataFrame(dict(close=prices,amount=1e8,segment_id=0,e0_valid=True,e0_down=False,i_floor=5.),index=idx)
        z=model.calculate(f);outputs[name]=z
        check('24_'+name+'_market_only_prefix',model.calculate(f.iloc[:110]).equals(z.iloc[:110]))
        request=seed(when=idx[70]);s=sh.new_shadow(request,e.MODEL_SHA);log=[]
        for date,row in z.iloc[70:].iterrows():
            close_pure(s,log,date,op=float(f.at[date,'close']),cl=float(f.at[date,'close']),receipt=bool(row.receipt),candidate=row.candidate)
        if name=='never':check('24_no_timeout_or_hold_dependency',sh.state(s)==0 and s['slot'] is None and s['status']=='LIVE')
    check('24_slow_and_jump_generate_market_receipts',outputs['slow'].receipt.sum()>0 and outputs['jump_flat'].receipt.sum()==1)


def test_25_prefix_and_clock():
    prefix=[]
    for suffix in [True,False]:
        x,r=setup(receipt=True)
        x.d.cp_rows[('a',later)]={'receipt':suffix,'candidate':9}
        x.d.prices[('a',later)]={'raw_close':100 if suffix else 1}
        prefix.append((copy.deepcopy(x.entry_shadows),copy.deepcopy(x.entry_decisions)))
    check('25_different_futures_same_prefix',prefix[0]==prefix[1])
    x,r=setup();x.d.cp_rows[('a',nxt)]={'receipt':True,'candidate':8};open_at(x,r)
    check('25_today_close_receipt_not_used_open',not x.orders and x.tickets['a']['status']=='STRUCTURE_WAIT')
    check('25_same_day_open_rejected',raises(AssertionError,lambda:x.entry_gate_open(r,dt)))


def test_26_append_only_provenance():
    states=[]
    for provenance in [{'cp_file_sha256':'old'},{'cp_file_sha256':'future_rows_appended'}]:
        s=sh.new_shadow(seed(),e.MODEL_SHA,provenance);log=[];close_pure(s,log,dt,receipt=True,candidate=8);states.append(s)
    check('26_future_hash_not_identity',states[0]['slot']['id']==states[1]['slot']['id'] and sh.state(states[0])==sh.state(states[1]))
    other=sh.new_shadow(seed(),'a'*64);close_pure(other,[],dt,receipt=True,candidate=8)
    check('26_actual_model_version_changes_id',other['slot']['id']!=states[0]['slot']['id'] and states[0]['slot']['model_version']==e.sha(e.MODEL))


def test_27_noop_and_scope():
    qa=e.self_check();check('27_static_original_methods_and_loader',qa['result']=='PASS')
    d1=SyntheticData();d2=copy.deepcopy(d1);x=e.Engine(d1,enabled=False);y=e.base.Engine(d2)
    for obj in [x,y]:
        obj.sync_events(CAL[6]);obj.events[obj.current_event['A']]['priority_attempted']=True
    r=seed();q=copy.deepcopy(r)
    for obj,req in [(x,r),(y,q)]:obj.decorate(req,dt);obj.plan_transfers(dt,[req]);obj.economic_preflight(nxt,[req]);obj.alloc_open(nxt,[req]);obj.close(nxt,dt)
    for k in vars(y):
        if k=='d':continue
        check('27_noop_exact_'+k,getattr(x,k)==getattr(y,k))
    check('27_no_history_entrypoint',raises(RuntimeError,lambda:x.run()))
    check('27_no_run_started',not(P/'RUN_STARTED.json').exists())


def main():
    groups=[]
    for name,fn in sorted(globals().copy().items()):
        if not name.startswith('test_') or not callable(fn):continue
        before=len(CHECKS)
        try:
            fn();groups.append(dict(group=name,result='PASS',checks=len(CHECKS)-before))
        except Exception as ex:
            groups.append(dict(group=name,result='FAIL',checks=len(CHECKS)-before,error=repr(ex),traceback=traceback.format_exc()))
    passed=all(g['result']=='PASS' for g in groups)
    out=dict(result='PASS' if passed else 'FAIL',contract_groups=len(groups),passed_groups=sum(g['result']=='PASS' for g in groups),
             assertions=len(CHECKS),checks=CHECKS,groups=groups,history_run=False,historical_Data_instantiated=False,
             no_network=True,only_synthetic_prices=True,engine_sha256=e.sha(P/'engine.py'),shadow_sha256=e.sha(P/'shadow.py'),
             tests_sha256=e.sha(P/'synthetic_tests.py'),design_sha256=e.DESIGN_SHA,model_sha256=e.MODEL_SHA)
    (P/'SYNTHETIC_QA.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
    (P/'STATIC_QA.json').write_text(json.dumps(e.self_check(),ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:out[k] for k in ['result','contract_groups','passed_groups','assertions','history_run']}))
    for g in groups:
        if g['result']=='FAIL':print(g['group'],g['traceback'])
    return 0 if passed else 1


if __name__=='__main__':raise SystemExit(main())
