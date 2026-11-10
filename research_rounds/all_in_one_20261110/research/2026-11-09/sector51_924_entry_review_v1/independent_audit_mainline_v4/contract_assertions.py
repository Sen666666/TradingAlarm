"""M4 independent normalized contract assertions; no strategy or historical run.
Real engine adapters must supply observed before/after state, not reimplement it.
Tests below are mutation tests of these assertions, NOT M4 engine integration QA.
"""
from decimal import Decimal as D
import copy,json
from pathlib import Path
Z=D(0)
def dec(x):return D(str(x))
def event_transition(before,after,outcome,cost=0,committed=True):
    immutable=('event_id','birth_day','NAV_anchor_day','NAV_anchor_kind','frozen_NAV','capital_cap')
    assert all(before[k]==after[k] for k in immutable),'EVENT_IDENTITY_MUTATED'
    if not committed:
        assert before==after,'ROLLBACK_CHANGED_EVENT';return
    assert dec(after['spent'])==dec(before['spent'])+(dec(cost) if outcome=='FILLED' else Z),'SPEND_WITHOUT_FILL_OR_WRONG_COST'
    assert Z<=dec(after['spent'])<=dec(after['capital_cap']),'EVENT_OVERSPENT'
    if before['priority_attempted']:assert after['priority_attempted'],'PRIORITY_RESURRECTED'
    if outcome in ('FILLED','CASH_REJECT','REFERENCE_REJECT','REAL_OPEN_OTHER_REJECT'):
        assert after['priority_attempted'],'REAL_ATTEMPT_NOT_CONSUMED'
    elif outcome in ('QUOTE_UNKNOWN','M_UNKNOWN','NO_LEGAL_CLOSE_PLAN'):
        assert after['priority_attempted']==before['priority_attempted'],'UNOBSERVED_ATTEMPT_INVENTED'

def seed_identity(old,new):
    for k in ('sid','signal_type','signal_day','frozen_attempt_NAV','event_id','original_I','original_source'):
        assert old[k]==new[k],f'TICKET_IDENTITY_CHANGED_{k}'

def budget_plan(nav,cash,receivable,reserve,outside_fixed,stress,B,lower_by_sector,event_costs,mature_B,targets):
    values=[nav,cash,receivable,reserve,outside_fixed,stress,B,mature_B]
    nav,cash,receivable,reserve,outside_fixed,stress,B,mature_B=map(dec,values)
    fixed=sum(map(dec,lower_by_sector.values()),Z);er=sum(map(dec,event_costs),Z)
    assert B==nav-reserve-receivable-outside_fixed-stress,'B_FORMULA'
    assert Z<=er<=max(Z,B-fixed),'EVENT_EATS_CORE'
    assert mature_B==B-er,'DOUBLE_ALLOCATED_EVENT_AND_T'
    assert set(targets)==set(lower_by_sector),'TARGET_DOMAIN'
    assert all(dec(targets[s])>=dec(v) for s,v in lower_by_sector.items()),'CORE_LOWER_BOUND'
    if targets and mature_B>=fixed:assert abs(sum(map(dec,targets.values()),Z)-mature_B)<D('1e-16'),'T_NOT_CLOSED'
    # Empty J is legal, including positive event allocation. No fictitious mature targets.

def open_seed(frozen_q,final_q,quantity_cap,noncash_pass,fees_gate_reject=False):
    assert not fees_gate_reject,'ADDED_OPEN_PRICE_FEE_FILTER'
    assert final_q in (0,frozen_q),'ECONOMIC_SEED_PARTIAL_OR_EXPANDED'
    if final_q:assert noncash_pass and final_q<=quantity_cap,'UNSAFE_OPEN_FILL'
    if quantity_cap<frozen_q:assert final_q==0,'CLIPPED_BELOW_ECONOMIC_UNIT'

def financed_orders(cash_before,reserve,mandatory_net,transfer_net,buy_cost,cash_after,receivable=0):
    cb,rs,mn,tn,bc,ca,rv=map(dec,[cash_before,reserve,mandatory_net,transfer_net,buy_cost,cash_after,receivable])
    assert ca==cb+mn+tn-bc,'CASH_NOT_RECONCILED'
    if bc:assert ca>=rs,'RESERVE_BREACH'
    # Receivable is intentionally not added: actual PAY cash must be in cash_before.

def donor(lot,bought,sell_day,qty,core_qty,frozen_qty,actual_qty):
    assert bought<sell_day,'T1_SALE'
    assert 0<qty<=actual_qty-core_qty-frozen_qty,'CORE_OR_FROZEN_SOLD'

def rollback(before,after):assert before==after,'DAY_ATOMIC_STATE_DIVERGED'

def run_selftests():
    passed=[]
    def ok(name,fn):fn();passed.append(name)
    def rejects(name,fn):
        try:fn()
        except AssertionError:passed.append(name);return
        raise AssertionError('ORACLE_ACCEPTED_MUTATION:'+name)
    e=dict(event_id='sector|2024-08-30',birth_day='2024-08-30',NAV_anchor_day='2024-09-02',NAV_anchor_kind='INITIAL_NAV',frozen_NAV='1200000',capital_cap='24000',spent='0',priority_attempted=False)
    filled={**e,'spent':'7505','priority_attempted':True};rejected={**e,'priority_attempted':True}
    ok('fill_spends_all_in',lambda:event_transition(e,filled,'FILLED','7505'))
    ok('cash_reject_consumes_priority_not_cash',lambda:event_transition(e,rejected,'CASH_REJECT'))
    ok('reference_reject_consumes_priority_not_cash',lambda:event_transition(e,rejected,'REFERENCE_REJECT'))
    ok('quote_unknown_pauses',lambda:event_transition(e,e,'QUOTE_UNKNOWN'))
    ok('M_unknown_pauses',lambda:event_transition(e,e,'M_UNKNOWN'))
    ok('no_structural_plan_pauses',lambda:event_transition(e,e,'NO_LEGAL_CLOSE_PLAN'))
    rejects('cash_reject_must_consume_priority',lambda:event_transition(e,e,'CASH_REJECT'))
    rejects('quote_unknown_cannot_consume_priority',lambda:event_transition(e,rejected,'QUOTE_UNKNOWN'))
    rejects('priority_never_resets',lambda:event_transition(rejected,e,'QUOTE_UNKNOWN'))
    rejects('no_phantom_spend',lambda:event_transition(e,filled,'CASH_REJECT'))
    rejects('sale_cannot_replenish_budget',lambda:event_transition(filled,{**filled,'spent':'0'},'QUOTE_UNKNOWN'))
    rejects('daily_NAV_cannot_refresh_cap',lambda:event_transition(e,{**e,'capital_cap':'26000'},'QUOTE_UNKNOWN'))
    ok('rollback_event',lambda:event_transition(e,e,'FILLED',7505,False))
    rejects('rollback_event_mutation',lambda:event_transition(e,filled,'FILLED',7505,False))
    t=dict(sid='x',signal_type='B',signal_day='2024-09-02',frozen_attempt_NAV='1200000',event_id=e['event_id'],original_I='1',original_source='frozen')
    ok('cold_start_keeps_B_and_old_birth',lambda:seed_identity(t,dict(t)))
    rejects('cold_start_not_A',lambda:seed_identity(t,{**t,'signal_type':'A'}))
    rejects('retry_not_new_signal',lambda:seed_identity(t,{**t,'signal_day':'2024-09-03'}))
    args=dict(nav=1000,cash=300,receivable=10,reserve=100,outside_fixed=90,stress=10,B=790,lower_by_sector={'s':200},event_costs=[150],mature_B=640,targets={'s':640})
    ok('deduct_actual_event_from_B',lambda:budget_plan(**args))
    rejects('reject_double_allocation',lambda:budget_plan(**{**args,'mature_B':790,'targets':{'s':790}}))
    rejects('do_not_sell_core_for_event',lambda:budget_plan(**{**args,'event_costs':[591],'mature_B':199,'targets':{'s':199}}))
    ok('empty_J_can_fund_real_event',lambda:budget_plan(**{**args,'lower_by_sector':{},'targets':{},'event_costs':[150]}))
    rejects('receivable_not_spendable_budget',lambda:budget_plan(**{**args,'B':800,'mature_B':650,'targets':{'s':650}}))
    ok('lower_open_same_q_allowed',lambda:open_seed(715,715,715,True,False))
    rejects('hidden_open_fee_gate',lambda:open_seed(715,0,715,True,True))
    ok('capacity_below_econ_cancel',lambda:open_seed(715,0,714,True))
    rejects('no_econ_partial',lambda:open_seed(715,714,714,True))
    rejects('no_open_quantity_increase',lambda:open_seed(715,716,716,True))
    rejects('noncash_gate_stays',lambda:open_seed(715,715,715,False))
    ok('actual_net_cash_then_buy',lambda:financed_orders(100,100,5,105,110,100,20))
    rejects('receivable_not_cash',lambda:financed_orders(100,100,5,105,110,120,20))
    ok('T1_and_core_respected',lambda:donor('lot','2024-09-26','2024-09-27',100,100,0,200))
    rejects('T0_not_sellable',lambda:donor('lot','2024-09-27','2024-09-27',100,100,0,200))
    rejects('core_not_sellable',lambda:donor('lot','2024-09-26','2024-09-27',101,100,0,200))
    state=dict(cash=100,events={'s':e},tickets=[t],reserved=0,logs=[],pending=[1],quote_gaps={})
    ok('whole_day_new_state_rollback',lambda:rollback(state,copy.deepcopy(state)))
    rejects('rollback_new_event_state',lambda:rollback(state,{**state,'events':{'s':filled}}))
    rejects('rollback_new_reservation',lambda:rollback(state,{**state,'reserved':7505}))
    rejects('rollback_new_logs',lambda:rollback(state,{**state,'logs':['attempt']}))
    return dict(status='PASS_ASSERTION_MUTATION_TESTS_ONLY',count=len(passed),tests=passed,engine_integrated=False,historical_runs=0)
if __name__=='__main__':
    q=run_selftests();Path(__file__).with_name('ASSERTION_SELFTEST_QA.json').write_text(json.dumps(q,ensure_ascii=False,indent=2)+'\n');print(json.dumps(q,ensure_ascii=False))
