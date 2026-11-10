"""Deterministic synthetic policy checks only. No historical account run."""
from decimal import Decimal as D
from pathlib import Path
import copy
import importlib.util
import json
import hashlib
import sys
sys.dont_write_bytecode = True
from allocation_rules import *

O = Path(__file__).resolve().parent
BASE = O.parent / 'joint51_candidate_v6_facts'
sys.path.insert(0, str(BASE))
spec = importlib.util.spec_from_file_location('engine', BASE / 'engine.py')
base = importlib.util.module_from_spec(spec)
sys.modules['engine'] = base
spec.loader.exec_module(base)
spec2 = importlib.util.spec_from_file_location('synthetic_joint', BASE / 'synthetic_joint.py')
joint = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(joint)
Q = base.QuantityRule('synthetic', 100, 100, 100, True, 1)
checks = []

def check(name, condition):
    assert condition, name
    checks.append(name)


def seed():
    return dict(kind='SEED', sid='TEST', birth_type='A', signal_day='2024-09-06',
                nav0=D(1200000), budget=D(24000), ifloor=D(5), factor=D(1),
                origin=('source', 'path', 'segment'), planned_q=100, capacity=100)

CAPS = {'attempt_budget': D(24000), 'stock_cap': D(120000),
        'sector_cap': D(0), 'cash_reserve': D(0)}

def ticket():
    return ticket_from_seed(seed(), D(1005), CAPS)


def preflight(t, date='2024-09-09', **kwargs):
    defaults = dict(date=date, origin=t['origin'], factor=t['current_factor'])
    defaults.update(kwargs)
    return retained_ticket_preflight(t, **defaults)


def refresh(t, date='2024-09-09', **kwargs):
    defaults = dict(date=date, sector_state=1, stock_state=1, i_state=1,
                    current_ifloor=D(6), raw_close=D(10), capacity=1000,
                    buy_minimum=100, all_in_min_cost=D(1005))
    defaults.update(kwargs)
    return refresh_retained_ticket(t, **defaults)


def raises(cls, fn):
    try:
        fn()
    except cls:
        return True
    return False


def run():
    # Existing economic/T+1/CP/equity tests operate on stubs, not historical Data.
    old = base.synthetic()
    oldchecks = old['checks'] + joint.run()
    check('baseline_original_synthetic_suite_unchanged', old['result'] == 'PASS' and len(oldchecks) >= 15)
    check('only_five_effective_arms', set(ARMS) == {'A', 'B', 'D', 'E', 'F'})
    check('C_explicitly_withdrawn_and_disabled', raises(ValueError, lambda: arm_config('C')))
    check('no_combined_or_grid_arms', raises(ValueError, lambda: arm_config('BF')))
    fields = ('progressive_add', 'retry_capital_seed', 'exit_unconfirmed_m3_false', 'sector_cap')
    check('B_D_E_F_each_exactly_one_config_delta', all(sum(getattr(ARMS[x], k) != getattr(ARMS['A'], k) for k in fields) == 1 for x in 'BDEF'))
    b = arm_config('B')
    check('B_CLOSE_plan_cannot_exceed_current_round_shares', add_quantity_limit(b, Q, 2400, 100) == 100)
    check('B_OPEN_rechecks_after_changed_round_shares', add_quantity_limit(b, Q, 200, 100) == 100)
    check('B_never_increases_prior_plan', add_quantity_limit(b, Q, 100, 200) == 100)
    check('B_minimum_lot_blocks_odd_small_round', add_quantity_limit(b, Q, 100, 99) == 0)
    check('B_round_quantity_all_layers_not_seed_only', add_quantity_limit(b, Q, 2400, 700) == 700)
    check('B_non_round_multiple_floors', add_quantity_limit(b, Q, 700, 199) == 100)
    check('B_zero_slot_remains_zero', add_quantity_limit(b, Q, 0, 100) == 0)
    check('other_arms_add_quantity_unchanged', all(add_quantity_limit(arm_config(x), Q, 2400, 100) == 2400 for x in 'ADEF'))
    kw = dict(budget=D(24000), nav=D(1200000), stock_value=D(0), sector_value=D(119500), cash=D(121000))
    ca, cf = (buy_capital_limits(arm_config(x), **kw) for x in 'AF')
    check('F_only_sector_cap_removed', set(ca) - set(cf) == {'sector_cap'} and all(cf[k] == ca[k] for k in cf))
    check('F_preserves_stock_cash_attempt_limits', cf == {'attempt_budget': D(24000), 'stock_cap': D(120000), 'cash_reserve': D(1000)})
    check('D_cash_and_sector_only_eligible', seed_capital_failure('SEED', True, D(1005), CAPS)['retain'])
    check('D_only_cash_eligible', seed_capital_failure('SEED', True, D(1005), dict(CAPS, sector_cap=D(120000)))['retain'])
    check('D_only_sector_eligible', seed_capital_failure('SEED', True, D(1005), dict(CAPS, cash_reserve=D(120000)))['retain'])
    check('D_hidden_attempt_shortage_not_retried', not seed_capital_failure('SEED', True, D(1005), dict(CAPS, attempt_budget=D(900)))['retain'])
    check('D_hidden_stock_shortage_not_retried', not seed_capital_failure('SEED', True, D(1005), dict(CAPS, stock_cap=D(900)))['retain'])
    check('D_noncapital_structural_rejection_not_retried', not seed_capital_failure('SEED', False, D(1005), CAPS)['retain'])
    check('D_ADD_never_enters_seed_retry_queue', not seed_capital_failure('ADD', True, D(1005), CAPS)['retain'])
    check('D_fully_funded_ticket_not_retained', not seed_capital_failure('SEED', True, D(1005), {k: D(1005) for k in CAPS})['retain'])
    t = ticket(); ident = immutable_identity(t); preflight(t); status = refresh(t)
    check('D_original_identity_and_NAV_preserved', status == 'PLAN' and immutable_identity(t) == ident and t['plan']['nav0'] == D(1200000) and t['plan']['signal_day'] == '2024-09-06')
    check('D_current_plan_day_is_separate', t['plan']['plan_day'] == '2024-09-09')
    check('D_current_I_ratchets', t['ifloor'] == D(6) and t['original_ifloor'] == D(5))
    preflight(t, '2024-09-10'); refresh(t, '2024-09-10', current_ifloor=D(4))
    check('D_I_never_reverts_to_original_lower_floor', t['ifloor'] == D(6))
    for field in ('sector_state', 'stock_state', 'i_state'):
        t = ticket(); preflight(t); status = refresh(t, **{field: -1})
        check('D_' + field + '_UNKNOWN_pauses_not_FALSE', status == 'PAUSED' and t['plan'] is None)
        t = ticket(); preflight(t); status = refresh(t, **{field: 0})
        check('D_' + field + '_FALSE_cancels', status == 'CANCELLED')
    t = ticket(); preflight(t); check('D_I_breach_cancels_even_other_unknown', refresh(t, sector_state=-1, raw_close=D(6)) == 'CANCELLED')
    t = ticket(); check('D_source_change_cancels_without_splice', preflight(t, origin=('different', 'path', 'segment')) == 'CANCELLED')
    t = ticket(); preflight(t); refresh(t, stock_state=-1)
    check('D_paused_missing_bridge_still_blocks', raises(MissingBridge, lambda: preflight(t, '2024-09-10', factor=D('1.1'))))
    check('D_action_requires_bridge_even_constant_factor', raises(MissingBridge, lambda: preflight(t, '2024-09-10', action_present=True)))
    before = immutable_identity(t)
    bridge = {'reviewed': True, 'factor_old': D(1), 'factor_new': D('1.1')}
    result = preflight(t, '2024-09-10', factor=D('1.1'), action_present=True, admitted_event=bridge)
    check('D_verified_bridge_zero_entitlement', result['record_qty'] == 0 and result['dividend_accrual'] == 0)
    check('D_bridge_preserves_original_identity_factor', immutable_identity(t) == before and t['original_factor'] == 1 and t['current_factor'] == D('1.1'))
    refresh(t, '2024-09-10', raw_close=D('9.09'))
    check('D_new_plan_current_factor_not_original_factor', t['plan']['factor'] == D('1.1'))
    t = ticket(); check('D_cannot_skip_daily_preflight', raises(AssertionError, lambda: refresh(t)))
    t = ticket(); preflight(t); check('D_current_lot_exceeds_original_2pct_pauses', refresh(t, all_in_min_cost=D(24001)) == 'PAUSED')
    t = ticket(); preflight(t); check('D_capacity_failure_pauses_at_CLOSE', refresh(t, capacity=99) == 'PAUSED')
    t = ticket(); preflight(t); refresh(t)
    check('D_capital_only_OPEN_rejection_retains', retry_open_outcome(t, filled=False, structural_pass=True, all_in_cost=D(1005), caps=CAPS) == 'RETAINED')
    check('D_noncapital_OPEN_failure_cancels', retry_open_outcome(t, filled=False, structural_pass=False, all_in_cost=D(1005), caps=CAPS) == 'CANCELLED')
    t = ticket(); preflight(t); refresh(t)
    check('D_actual_seed_consumes_once', retry_open_outcome(t, filled=True, structural_pass=True, all_in_cost=D(1005), caps=CAPS) == 'CONSUMED' and t['ever_seeded'])
    check('D_consumed_ticket_cannot_seed_twice', raises(AssertionError, lambda: retry_open_outcome(t, filled=True, structural_pass=True, all_in_cost=D(1005), caps=CAPS)))
    check('D_consumed_ticket_never_replans', refresh(t) == 'CONSUMED')
    e = arm_config('E')
    check('E_known_FALSE_unconfirmed_adds_exit', m3_seed_exit(e, historical_actual_add_count=0, stock_state=0, prior_exit_reason=None)['incremental_exit'])
    check('E_UNKNOWN_does_not_exit', m3_seed_exit(e, historical_actual_add_count=0, stock_state=-1, prior_exit_reason=None)['exit_reason'] is None)
    check('E_TRUE_does_not_exit', m3_seed_exit(e, historical_actual_add_count=0, stock_state=1, prior_exit_reason=None)['exit_reason'] is None)
    check('E_historical_ADD_mature_even_zero_current_ADD_inventory', m3_seed_exit(e, historical_actual_add_count=1, stock_state=0, prior_exit_reason=None)['exit_reason'] is None)
    prior = m3_seed_exit(e, historical_actual_add_count=0, stock_state=0, prior_exit_reason='TRIAL_SECTOR_FALSE')
    check('E_original_exit_not_double_counted', prior['exit_reason'] == 'TRIAL_SECTOR_FALSE' and not prior['incremental_exit'] and prior['new_condition'])
    check('other_arms_M3_FALSE_no_new_exit', all(m3_seed_exit(arm_config(x), historical_actual_add_count=0, stock_state=0, prior_exit_reason=None)['exit_reason'] is None for x in 'ABDF'))
    # Dispatch the newly locked E reason through the unchanged real exit engine.
    stub = joint.Stub(); eng = base.Engine(stub); a = joint.attempt('a')
    a['exit'] = 'UNCONFIRMED_STOCK_M3_FALSE'; a['lots'][0]['bought'] = '2024-09-03'
    eng.active['a'] = a; eng.archive[a['id']] = a
    eng.exit_open(base.pd.Timestamp('2024-09-03'))
    check('E_existing_execution_keeps_T1_lock', bool(eng.active) and a['lots'][0]['exit'] == 'T1_LOCKED_EXIT')
    eng.exit_open(base.pd.Timestamp('2024-09-04'))
    check('E_next_legal_OPEN_exits_with_fee', not eng.active and eng.orders[-1]['reason'] == 'UNCONFIRMED_STOCK_M3_FALSE' and D(eng.orders[-1]['fee']) == 5)
    check('cohorts_all_signals_not_only_losing_rounds', cohort_tags(signal_day='2024-09-06', source_sector_name='证券') == ['ALL_SIGNALS_0902_0913', 'SECURITIES_SIGNALS_0906_0909'])
    check('cohort_insurance_not_mislabeled_securities', cohort_tags(signal_day='2024-09-06', source_sector_name='保险') == ['ALL_SIGNALS_0902_0913'])
    check('restart_cohort_1022_to1025_inclusive', cohort_tags(signal_day='2024-10-25', source_sector_name='软件') == ['ALL_SIGNALS_1022_1025'] and not cohort_tags(signal_day='2024-10-28', source_sector_name='软件'))
    check('drawdown_includes_initial_capital', drawdown_path([D(1100000), D(1300000), D(1200000)])[0] < 0)
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [O/'allocation_rules.py', O/'synthetic_allocation.py', O/'FROZEN_CONTRACT_DRAFT.md', O/'DESIGN_IMPACT.csv']}
    return dict(result='PASS_POLICY_SYNTHETIC_ONLY', checks=checks, checks_count=len(checks), baseline_original_checks=oldchecks, baseline_original_checks_count=len(oldchecks), effective_arms=list(ARMS), disabled_arms=['C'], historical_data_loaded=False, historical_accounts_run=0, full_engine_integration='NOT_IMPLEMENTED_PENDING_DESIGN_APPROVAL', hashes=hashes)

if __name__ == '__main__':
    result = run()
    (O/'SYNTHETIC_POLICY_QA.json').write_text(json.dumps(result, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ['checks','baseline_original_checks','hashes']}, ensure_ascii=False))
