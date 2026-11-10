"""Synthetic native-interface tests. No Data() and no real account history."""
from pathlib import Path
from types import SimpleNamespace
import copy
import importlib.util
import json
import sys
sys.dont_write_bytecode = True
P = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('v12_synthetic_engine', P / 'engine.py')
e = importlib.util.module_from_spec(spec); sys.modules[spec.name] = e; spec.loader.exec_module(e)
D,pd,Z=e.D,e.pd,e.ZERO
CAL=pd.bdate_range('2001-01-01',periods=45)
dt,nxt,later=CAL[7],CAL[8],CAL[9]
ORIGIN=('synthetic','memory://fixture','0')
CHECKS=[]
def check(name,condition=True):
    assert condition,name
    CHECKS.append(name)
def raises(kind,call):
    try:call()
    except kind:return True
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


def hold(x, s='old', qty=10000, role='EXPANSION'):
    a = dict(id=s+'|fixture', sid=s, signal_day=e.day(CAL[3]), birth_type='B', nav0=D(1200000),
             seed_day=e.day(CAL[4]), cashflow=-D(qty)*D(9), dividend=Z, fees=D(5), ifloor=D(5),
             factor=D(1), origin=ORIGIN, exit=None, plan=None, cp=None, add_count=0,
             confirmed_history=True, lots=[dict(id=s+'|lot', kind='SEED', q=qty, bought=e.day(CAL[4]),
                                                  floor=D(5), cp_id=None, capital_role=role)])
    x.active[s] = a; x.archive[a['id']] = a
    x.orders.append(dict(day=e.day(CAL[4]),sid=s,side='BUY_SEED', round_id=a['id'], lot_id=s+'|lot', qty=qty, order_seq=1,cash_delta=str(a['cashflow'])))
    x.confirmations.append(dict(day=e.day(CAL[6]),phase='OPEN',sid=s,round_id=a['id'],proof_id='historical-proof',cp_id='historical-postseed-cp',decision='INFORMATION_CONFIRMED'))
    return a



def setup(phase='MATURE',cls=e.Engine):
    x=cls(SyntheticData())
    x.sync_events(CAL[6])
    for ev in x.events.values():ev['cold_start']=False
    if phase!='EVENT':x.events[x.current_event['A']]['priority_attempted']=True
    if phase=='RESIDUAL':x.d.main_rows[('a',dt)]={'M':0,'E':0}
    return x

def planned(x,rows=None):
    rows=[seed()] if rows is None else rows
    for r in rows:x.decorate(r,dt)
    x.plan_transfers(dt,rows)
    return rows

def open_only(x,rows,when=nxt):
    x.economic_preflight(when,rows);x.accrue(when)
    decision=x.select_open(when,rows)
    x.execute_selected(when,rows,decision)
    return decision

def snap(x):return e.digest({k:v for k,v in vars(x).items() if k!='d'})
def economy(x):
    return {k:copy.deepcopy(getattr(x,k)) for k in ('cash','receivable','active','archive','seq','orders','tickets','events','current_event','transfer_plan','reference','_donor_sectors','_probe_receiver_sectors','candidates','transfers','confirmations','cp_log','event_log','event_plans','reference_log','reference_requests','capital_lots','floor_risk','seed_floor_risk','seed_execution_cost','ticket_log')}

def test_native_noN_and_nonbinding():
    for phase in ('EVENT','RESIDUAL','MATURE'):
        x,y=setup(phase),setup(phase,e.base.Engine)
        rx,ry=planned(x),planned(y)
        check('native_'+phase+'_close_equality',economy(x)==economy(y))
        before=snap(x);decision=x.select_open(nxt,rx)
        check('conditional_choice_no_account_effect_'+phase, all(getattr(x,k)==v for k,v in economy(y).items()))
        check('one_original_branch_'+phase,decision['selected_index']==0)
        # select_open is pure except its explicit decision audit.
        x.funding_decisions.pop()
        check('selection_audit_only_'+phase,snap(x)==before)
        open_only(x,rx)
        y.economic_preflight(nxt,ry);y.accrue(nxt);y.exit_open(nxt);y.alloc_open(nxt,ry)
        check('native_'+phase+'_open_equality',economy(x)==economy(y))
        for a in x.active.values():check('native_alias_'+phase,x.archive[a['id']] is a)

def test_binding_H_wait():
    x=setup();a=hold(x,qty=110000);x.cash=D(20000)
    x.d.main_rows[('old',dt)]={'M':0,'E':0,'W':True}
    rows=planned(x)
    book=x.funding_book
    check('H_non_mainline_true',book['H']['old|lot']['H'])
    check('binding_deletes_seed',book['selected_close_index']==1)
    check('full_increases_healthy_donor',book['branches'][0]['close_comparison']['healthy_donor_increase']==['old|lot'])
    check('shadow_zero_D_and_independent_targets',book['branches'][1]['plan']['reference']['D']['A']==0 and book['branches'][0]['plan']['reference']['D']['A']>0)
    check('original_pending_retained_for_preflight',len(rows)==1 and not x.tickets)
    before=snap(x);z=e.scratch(x)
    check('scratch_data_matrices_shared',z.d.prices is x.d.prices and z.d is not x.d)
    check('scratch_round_alias',z.active['old'] is z.archive[a['id']] and z.active['old'] is not a)
    z.active['old']['lots'][0]['q']-=1
    check('scratch_state_isolation',snap(x)==before)
    dec=open_only(x,rows)
    t=x.tickets['a'];identity=e.rules.immutable_identity(t)
    check('explicit_wait_no_forged_reference_cap',t['reason']==e.WAIT and t['first_reject_caps']==['funding_nondisplacement'])
    check('wait_original_budget',t['signal_day']==rows[0]['signal_day'] and t['nav0']==rows[0]['nav0'] and t['budget']==rows[0]['budget'])
    check('wait_no_orders_or_new_round',len(x.orders)==1 and 'a' not in x.active)
    check('stable_request_id_before_after_ticket',e.request_id(rows[0])==e.request_id(dict(rows[0],ticket_id=t['ticket_id'])))
    x.d.stock.at[nxt,'a']=-1;x.d.fact_rows[('a',nxt)]={'i_floor':6}
    x.refresh_tickets(nxt)
    check('wait_unknown_pauses_identity_and_ratchets',t['status']=='PAUSED' and t['ifloor']==6 and e.rules.immutable_identity(t)==identity)
    x.d.stock.at[nxt,'a']=0;x.refresh_tickets(nxt)
    check('wait_known_false_cancels',t['status']=='CANCELLED' and t['reason']=='RETRY_STOCK_M3_FALSE')

def test_open_health_new_confirmation():
    x=setup();a=hold(x,qty=110000);x.cash=D(20000)
    x.d.main_rows[('old',dt)]={'M':0,'E':0,'W':True}
    a['confirmed_history']=False
    a['cp']=dict(id='post_seed',date=e.day(dt),floor=D(7),origin=ORIGIN,consumed=False,invalid=False)
    a['information_pending']=dict(cp_id='post_seed',proof_id='p',close_day=e.day(dt),close_net='10000')
    rows=planned(x)
    check('H_close_false_before_real_confirmation',not x.funding_book['H']['old|lot']['H'])
    check('close_full_pass_before_confirmation',x.funding_book['selected_close_index']==0)
    before=snap(x);dec=x.select_open(nxt,rows)
    check('H_open_new_confirmation_shared',dec['H']['old|lot']['H'] and dec['selected_index']==1)
    check('real_proof_not_consumed_by_projection',a.get('information_pending') and not a['confirmed_history'])
    x.execute_selected(nxt,rows,dec)
    check('real_confirmation_once',a['confirmed_history'] and sum(r['decision']=='INFORMATION_CONFIRMED' and r['day']==e.day(nxt) for r in x.confirmations)==1)

def test_future_poison_and_phase():
    x=setup();a=hold(x,qty=110000);x.cash=D(20000)
    x.d.main_rows[('old',dt)]={'M':0,'E':0,'W':True}
    a['exit']='I_CLOSE_PROTECTION'
    rows=planned(x)
    original=x.d.z
    def poison(s,d):
        z=original(s,d)
        if d==nxt:z.update(raw_close='POISON',raw_high='POISON',raw_low='POISON',raw_volume='POISON')
        return z
    x.d.z=poison
    # The projection view's access is strict; even attempting f/m/c/raw fails.
    view=e.QuoteView(x.d,nxt)
    check('projection_forbids_signal_and_bar_access',all(raises(AssertionError,lambda k=k:getattr(view,k)) for k in ('raw','f','c','m','stock','main','sectors','cap')))
    decision=x.select_open(nxt,rows)
    check('forced_prefix_projection_has_no_full_day_read',decision['common_conditional_prefix']['predicted_prefix_orders'] and decision['selected_index']==0)
    check('forced_exit_lot_absent_H',not decision['H'])
    calls=[]
    def actual_nofill(s,d,side):
        calls.append((s,side));return s=='old' and side=='sell'
    x.no_fill=actual_nofill
    x.execute_selected(nxt,rows,decision)
    check('actual_exit_nofill_runs_only_after_choice',calls and 'old' in x.active and x.funding_actual[-1]['no_fill_events'])
    check('no_reselect_after_actual_nofill',len(x.funding_decisions)==1 and not x.funding_actual[-1]['reselected'])
    check('actual_prediction_deviation_recorded',e.dec(x.funding_actual[-1]['prefix_cash_deviation']) != 0)

def test_per_lot_and_protection_health():
    x=setup();a=hold(x,qty=20000)
    a['lots'].append(dict(id='add|lot',kind='ADD',q=1000,bought=e.day(CAL[5]),floor=D(11),cp_id='oldcp',capital_role='EXPANSION'))
    x.freeze_knowledge(dt);H=x.health(dt,'CLOSE')
    check('H_per_lot_CP_breach',H['old|lot']['H'] and not H['add|lot']['H'])
    a['confirmed_history']=False
    check('H_unconfirmed_false',not any(r['H'] for r in x.health(dt,'CLOSE').values()))
    a['confirmed_history']=True;a['cashflow']=-D(10000000)
    check('H_current_net_not_historical_winner',not any(r['H'] for r in x.health(dt,'CLOSE').values()))
    check('numpy_boolean_accepted',e.boolean(e.np.bool_(True)) is True and e.boolean(e.np.bool_(False)) is False)
    check('non_boolean_not_promoted',all(e.boolean(v) is None for v in (0,1,None,'False','unknown')))

def test_preflight_atomic():
    x=setup();a=hold(x,qty=110000);x.cash=D(20000);x.d.main_rows[('old',dt)]={'M':0,'E':0,'W':True}
    rows=planned(x);before=snap(x);saved=copy.deepcopy(rows)
    x.d.actions[('a',nxt)]=[{'unadmitted':True}]
    check('deleted_N_still_original_bridge_block',raises(e.Blocked,lambda:x.atomic_step(nxt,rows,dt)))
    check('atomic_all_state_and_pending_rollback',snap(x)==before and rows==saved)
    check('atomic_alias_preserved',x.active['old'] is x.archive[a['id']])
    x.d.actions.clear()
    # Successful single synthetic atomic day checks integration into original close.
    out=x.atomic_step(nxt,rows,dt)
    check('atomic_synthetic_day_completed',len(x.ledger)==1 and x.ledger[0]['day']==e.day(nxt))
    check('preflight_full_original_target_logged','a' in x.funding_preflight[-1]['original_targets'])

def setup_add_competition(cash=50000,old_weight=9,planned_q=2000):
    d=SyntheticData();d.sid_sector['b']='B';d.sector_ids=['A','B','OLD'];d.sectors['B']=d.sectors['A'].copy()
    x=e.Engine(d);x.sync_events(CAL[6])
    for ev in x.events.values():ev.update(cold_start=False,priority_attempted=True)
    a=hold(x,s='a',qty=10000);old=hold(x,qty=100000);old['confirmed_history']=False;x.cash=D(cash)
    for symbol,weight in [('a',1),('b',100),('old',old_weight)]:
        for when in [dt,CAL[6]]:d.main_rows[(symbol,when)]={'M':1,'E':weight}
    a['cp']=dict(id='cpA',date=e.day(dt),floor=D(7),origin=ORIGIN,consumed=False,invalid=False)
    a['plan']=dict(kind='ADD',sid='a',signal_day=e.day(dt),cp_date=e.day(dt),cp_id='cpA',budget=D(24000),
                   planned_q=planned_q,capacity=100000,close_net='10000',origin=ORIGIN,factor=D(1))
    x.decorate(a['plan'],dt)
    rows=planned(x,[seed('b')]);return x,rows

def test_real_ADD_floor_and_OPEN_recheck():
    x,rows=setup_add_competition()
    full,shadow=x.funding_book['branches'];add=next(e.request_id(r) for r in full['requests'] if r['kind']=='ADD')
    check('native_ADD_floor_binding_not_H',not full['close_comparison']['healthy_donor_increase'] and full['close_comparison']['add_event_reduction']==[add])
    check('native_ADD_200_vs_300',full['close_projection']['q'][add]==200 and shadow['close_projection']['q'][add]==300)
    check('branch_reference_independently_recomputed',full['plan']['reference']['T']['A']!=shadow['plan']['reference']['T']['A'])
    check('branch_donor_fields_not_union',full['plan']['transfer_plan']!=shadow['plan']['transfer_plan'])
    open_only(x,rows)
    check('native_ADD_commit_once',sum(o['side']=='BUY_ADD' for o in x.orders)==1 and x.active['a']['add_count']==1 and x.active['a']['cp'] is None)
    check('withdrawn_MATURE_no_role_rewrite','b' in x.tickets and x.funding_wait_log[-1]['original_request']['allocation_phase']=='MATURE')
    x,rows=setup_add_competition(cash=0,old_weight=8.75,planned_q=100)
    full,shadow=x.funding_book['branches'];add=next(e.request_id(r) for r in shadow['requests'] if r['kind']=='ADD')
    check('shadow_CLOSE_q0_is_not_permission0',shadow['bar_q_C'][add]==100 and shadow['close_projection']['q'][add]==0)
    check('full_cannot_borrow_shadow_receiver_cap',full['bar_q_C'][add]==0 and x.funding_book['selected_close_index']==0)
    x.d.prices[('old',nxt)]={'raw_open':10.1}
    dec=x.select_open(nxt,rows)
    check('shadow_OPEN_positive_existing_permission',dec['shadow_projection']['q'][add]==100)
    check('OPEN_rejects_full_missing_ADD',dec['selected_index']==1 and dec['evaluated'][0]['comparison']['add_event_reduction']==[add])
    check('CLOSE_qhat_not_new_OPEN_hard_cap',dec['chosen_projection']['q'][add]>shadow['close_projection']['q'][add])
    check('phantom_original_sale_and_residual_preserved',shadow['close_projection']['q'][add]==0 and sum(shadow['close_projection']['y'].values())>0)
    clean=e.clean(x.funding_book)
    check('serialized_book_hash_reconstructible',clean['book_id']==e.digest({k:v for k,v in clean.items() if k!='book_id'}))
    check('serialized_branch_hash_reconstructible',all(b['branch_id']==e.digest(e.branch_hash_payload(b)) for b in clean['branches']))

def test_multiple_N_and_layers():
    x=setup();a=hold(x,qty=110000);x.cash=D(20000);x.d.main_rows[('old',dt)]={'M':0,'E':0,'W':True}
    a['lots'][0]['q']=55000;a['lots'].append(dict(id='old|layer2',kind='ADD',q=55000,bought=e.day(CAL[5]),floor=D(5),cp_id='priorCP',capital_role='EXPANSION'))
    rows=planned(x,[seed('a'),seed('b')]);book=x.funding_book
    check('native_fixed_two_N_chain',len(book['branches'])==3 and all(b['retained']==book['N_priority'][:2-i] for i,b in enumerate(book['branches'])))
    check('same_round_two_lots_shared_H',set(book['H'])=={'old|lot','old|layer2'} and all(v['H'] for v in book['H'].values()))
    check('same_round_first_layer_y_comparison',book['branches'][0]['close_comparison']['healthy_donor_increase']==['old|lot'])
    check('CLOSE_binding_all_N_removed',book['selected_close_index']==2)
    x.cash+=D(1000000) # known OPEN actual cash change, deliberately favorable.
    dec=x.select_open(nxt,rows)
    check('CLOSE_deleted_N_never_revives_when_OPEN_favorable',dec['selected_index']==2 and len(dec['evaluated'])==1)

def test_wait_original_failures_and_Q0():
    x=setup();hold(x,qty=110000);x.cash=D(20000);x.d.main_rows[('old',dt)]={'M':0,'E':0,'W':True};rows=planned(x)
    dec=x.select_open(nxt,rows);x.d.prices[('a',nxt)]={'raw_open':1000}
    x.execute_selected(nxt,rows,dec)
    check('attempt_budget_failure_no_new_WAIT_ticket','a' not in x.tickets and x.funding_wait_log[-1]['status']=='ORIGINAL_REJECT_NO_TICKET')
    x=setup();hold(x,qty=110000);x.cash=D(20000);x.d.main_rows[('old',dt)]={'M':0,'E':0,'W':True};rows=planned(x);open_only(x,rows)
    t=x.tickets['a'];identity=e.rules.immutable_identity(t)
    x.d.prices[('a',later)]={'raw_open':None,'adjustment_factor':None}
    saved=copy.deepcopy(rows);x.economic_preflight(later,saved)
    check('waiting_Q0_unknown_preserves_ticket',not saved and t['status']=='PAUSED_NO_QUOTE' and e.rules.immutable_identity(t)==identity)
    x.d.stock.at[later,'a']=0;x.refresh_tickets(later)
    check('waiting_Q0_known_false_original_cancel',t['status']=='CANCELLED' and t['reason']=='RETRY_STOCK_M3_FALSE')
    x=setup();hold(x,qty=110000);x.cash=D(20000);x.d.main_rows[('old',dt)]={'M':0,'E':0,'W':True};rows=planned(x)
    x.d.prices[('a',nxt)]={'raw_open':5}
    dec=x.select_open(nxt,rows);x.execute_selected(nxt,rows,dec)
    check('withdrawn_OPEN_I_breach_not_funding_WAIT','a' not in x.tickets and x.funding_wait_log[-1]['reason']=='OPEN_BELOW_PROTECTION')

def test_EVENT_attempt_no_fill_and_metadata():
    x=setup('EVENT');rows=planned(x);eid=rows[0]['event_id'];before=snap(x)
    dec=x.select_open(nxt,rows)
    check('scratch_EVENT_never_consumes_attempt_or_spent',not x.events[eid]['priority_attempted'] and x.events[eid]['spent']==0)
    # Test-only no-fill matcher exercises the native reservation/attempt point.
    x.no_fill=lambda s,d,side: side=='buy'
    x.buy_nofill=lambda d,r,q,p,cost: True
    x.execute_selected(nxt,rows,dec)
    check('actual_EVENT_attempt_consumed_without_fill',x.events[eid]['priority_attempted'] and x.events[eid]['spent']==0 and not x.active)
    x=setup();hold(x,qty=110000);x.cash=D(20000);x.d.main_rows[('old',dt)]={'M':0,'E':0,'W':True};rows=planned(x)
    dec=x.select_open(nxt,rows);x.funding_decisions.pop()
    x.d.prices[('old',nxt)]={'volume_eligible':False,'observed_bar':False,'source_invalid':True,'price_eligible':False,'synthetic_event_bar':True,'raw_volume':None}
    again=x.select_open(nxt,rows)
    check('OPEN_H_ignores_later_bar_qualification_flags',again['H']==dec['H'] and again['selected_index']==dec['selected_index'])
    x.d.cap['a'].loc[nxt]=0
    third=x.select_open(nxt,rows)
    check('OPEN_capacity_from_CLOSED_request_only',third['chosen_projection']==again['chosen_projection'])

def test_synthetic_scale():
    import time
    x=setup();d=x.d
    names=['n'+str(i).zfill(2) for i in range(30)]
    for s in names:d.ids.append(s);d.names[s]=s;d.sid_sector[s]='A';d.stock[s]=1;d.cap[s]=pd.Series(100000,index=CAL)
    hold(x,qty=110000);x.cash=D(20000);d.main_rows[('old',dt)]={'M':0,'E':0,'W':True}
    started=time.perf_counter();rows=planned(x,[seed(s) for s in names]);dec=x.select_open(nxt,rows)
    elapsed=time.perf_counter()-started;size=len(json.dumps(e.clean(x.funding_book)).encode())
    check('30N_31_native_branches',len(x.funding_book['branches'])==31)
    check('30N_finite_terminal_shadow',dec['selected_index']==30)
    scale=dict(synthetic_N=30,branches=31,seconds=elapsed,serialized_book_bytes=size,history_run=False)
    (P/'SYNTHETIC_SCALE.json').write_text(json.dumps(scale,indent=2)+'\n')


def test_contract_19():
    c=e.module('frozen_contract_selector',e.ROOT/'mainline_winner_funding_review_v1/contract_selector.py')
    result=c.run_synthetics()
    for name in result['checks']:check('contract_'+name)

def run():
    e.self_check()
    for fn in (test_native_noN_and_nonbinding,test_binding_H_wait,test_open_health_new_confirmation,
               test_future_poison_and_phase,test_per_lot_and_protection_health,test_preflight_atomic,
               test_real_ADD_floor_and_OPEN_recheck,test_multiple_N_and_layers,test_wait_original_failures_and_Q0,
               test_EVENT_attempt_no_fill_and_metadata,test_synthetic_scale,test_contract_19):fn()
    result=dict(result='PASS',assertions=len(CHECKS),checks=CHECKS,history_run=False,real_Data_constructed=False,
                python=sys.executable,numpy=e.np.__version__,pandas=pd.__version__,engine_sha256=e.sha(P/'engine.py'),tests_sha256=e.sha(P/'synthetic_tests.py'))
    (P/'SYNTHETIC_QA.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':run()
