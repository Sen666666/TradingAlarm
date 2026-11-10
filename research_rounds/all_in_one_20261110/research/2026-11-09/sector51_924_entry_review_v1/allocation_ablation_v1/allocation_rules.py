"""Pure policy helpers for the approved-scope A/B/D/E/F design review.
No market-data loading, history execution, network, or external writes.
C is explicitly withdrawn and cannot be selected.
"""
from dataclasses import dataclass
from decimal import Decimal as D
import copy
import hashlib
import json

ZERO = D(0)
TOL = D('1e-11')

@dataclass(frozen=True)
class Arm:
    name: str
    progressive_add: bool = False
    retry_capital_seed: bool = False
    exit_unconfirmed_m3_false: bool = False
    sector_cap: D | None = D('.10')

ARMS = {
    'A': Arm('A'),
    'B': Arm('B', progressive_add=True),
    'D': Arm('D', retry_capital_seed=True),
    'E': Arm('E', exit_unconfirmed_m3_false=True),
    'F': Arm('F', sector_cap=None),
}

def arm_config(name):
    if name == 'C':
        raise ValueError('C_WITHDRAWN_PENDING_NEW_MAINLINE_DESIGN')
    if name not in ARMS:
        raise ValueError('NOT_AN_AUTHORIZED_SINGLE_FACTOR_ARM')
    return ARMS[name]


def add_quantity_limit(arm, quantity_rule, baseline_quantity, current_round_quantity):
    """Call independently at CLOSE planning and OPEN actual reservation.

    baseline_quantity already satisfies the unchanged dated quantity/capacity,
    budget, and for OPEN the prior CLOSE plan quantity. Never enlarges it.
    """
    assert baseline_quantity >= 0 and current_round_quantity >= 0
    if not arm.progressive_add:
        return baseline_quantity
    return quantity_rule.buy_floor(min(baseline_quantity, current_round_quantity))


def buy_capital_limits(arm, *, budget, nav, stock_value, sector_value, cash):
    """Exact inherited conservative all-in reservation caps, except F.

    Omitting the sector cap in F (rather than huge numeric replacement) is
    intentional. Caller retains every other gate and allocation ordering.
    """
    caps = {
        'attempt_budget': budget,
        'stock_cap': max(ZERO, D('.10') * nav - stock_value),
    }
    if arm.sector_cap is not None:
        caps['sector_cap'] = max(ZERO, arm.sector_cap * nav - sector_value)
    caps['cash_reserve'] = max(ZERO, cash - D('.10') * nav)
    return caps


def seed_capital_failure(kind, structural_pass, all_in_cost, caps):
    """All violated caps matter. A lone baseline minimum label is insufficient."""
    violated = sorted(k for k, v in caps.items() if all_in_cost > v)
    retain = (
        kind == 'SEED' and structural_pass and bool(violated)
        and set(violated) <= {'cash_reserve', 'sector_cap'}
    )
    return {'retain': retain, 'violated': violated}


class MissingBridge(RuntimeError):
    pass


def ticket_from_seed(request, all_in_cost, caps, *, structural_pass=True):
    eligibility = seed_capital_failure(request['kind'], structural_pass, all_in_cost, caps)
    if not eligibility['retain']:
        return None
    origin = tuple(request['origin'])
    identity = [request['sid'], request['birth_type'], request['signal_day'], origin]
    ticket_id = hashlib.sha256(json.dumps(identity).encode()).hexdigest()[:24]
    return {
        'ticket_id': ticket_id,
        'sid': request['sid'],
        'birth_type': request['birth_type'],
        'signal_day': request['signal_day'],
        'nav0': request['nav0'],
        'budget': D('.02') * request['nav0'],
        'origin': origin,
        'original_factor': request['factor'],
        'current_factor': request['factor'],
        'original_ifloor': request['ifloor'],
        'ifloor': request['ifloor'],
        'status': 'RETAINED',
        'ever_seeded': False,
        'plan': None,
        'first_reject_caps': eligibility['violated'],
        'last_verified_day': None,
    }


def immutable_identity(ticket):
    return tuple(ticket[k] for k in (
        'ticket_id', 'sid', 'birth_type', 'signal_day', 'nav0', 'budget',
        'origin', 'original_factor', 'original_ifloor'))


def cancel(ticket, reason):
    ticket['status'] = 'CANCELLED'
    ticket['plan'] = None
    ticket['reason'] = reason
    return 'CANCELLED'


def retained_ticket_preflight(ticket, *, date, origin, factor, action_present=False, admitted_event=None):
    """Mandatory even while paused; execute before that day's CLOSE signals.

    Source changes cancel D tickets. Same-source unknown action/factor bridges
    block the atomic day. A reviewed pending-entry bridge grants zero entitlement.
    """
    if ticket['status'] in ('CANCELLED', 'CONSUMED'):
        return ticket['status']
    if tuple(origin) != ticket['origin']:
        return cancel(ticket, 'RETRY_SOURCE_CHANGED')
    if not factor.is_finite() or factor <= 0:
        raise MissingBridge('RETRY_PENDING_FACTOR_INVALID')
    old = ticket['current_factor']
    changed = abs(factor / old - 1) > TOL
    if admitted_event is None and (changed or action_present):
        raise MissingBridge('RETRY_PENDING_UNADMITTED_EQUITY_OR_FACTOR')
    if admitted_event is not None:
        assert admitted_event.get('reviewed') is True
        if (abs(old / admitted_event['factor_old'] - 1) > TOL
                or abs(factor / admitted_event['factor_new'] - 1) > TOL):
            raise MissingBridge('RETRY_PENDING_FACTOR_BRIDGE_MISMATCH')
    ticket['current_factor'] = factor
    ticket['last_verified_day'] = date
    return {'status': ticket['status'], 'record_qty': 0, 'dividend_accrual': ZERO}


def refresh_retained_ticket(ticket, *, date, sector_state, stock_state, i_state,
                            current_ifloor, raw_close, capacity, buy_minimum,
                            all_in_min_cost, source_valid=True):
    """Return PLAN/PAUSED/CANCELLED; no new ticket, NAV, queue age, or CP.

    Caller has run daily preflight for every retained ticket, even paused tickets.
    Unknown executable inputs pause at CLOSE. Explicit false/protection cancels.
    A subsequent OPEN failure is handled separately below.
    """
    if ticket['status'] in ('CANCELLED', 'CONSUMED'):
        return ticket['status']
    assert ticket['last_verified_day'] == date, 'PENDING_DAILY_PREFLIGHT_REQUIRED'
    assert sector_state in (-1, 0, 1) and stock_state in (-1, 0, 1) and i_state in (-1, 0, 1)
    if i_state == 0:
        return cancel(ticket, 'RETRY_I_FALSE')
    if sector_state == 0:
        return cancel(ticket, 'RETRY_SECTOR_FALSE')
    if stock_state == 0:
        return cancel(ticket, 'RETRY_STOCK_M3_FALSE')
    # Positive current I can ratchet even when sector/stock is UNKNOWN.
    current_i_known = (i_state == 1 and current_ifloor is not None
                       and current_ifloor.is_finite() and current_ifloor > 0)
    if current_i_known:
        ticket['ifloor'] = max(ticket['ifloor'], current_ifloor)
    price_known = (source_valid and raw_close is not None
                   and raw_close.is_finite() and raw_close > 0)
    if price_known and raw_close * ticket['current_factor'] <= ticket['ifloor']:
        return cancel(ticket, 'RETRY_I_PROTECTION_BREACHED')
    reason = None
    if sector_state == -1:
        reason = 'RETRY_SECTOR_UNKNOWN'
    elif stock_state == -1:
        reason = 'RETRY_STOCK_UNKNOWN'
    elif not current_i_known:
        reason = 'RETRY_I_UNKNOWN'
    elif not price_known:
        reason = 'RETRY_PRICE_SOURCE_UNKNOWN'
    elif capacity is None:
        reason = 'RETRY_CAPACITY_UNKNOWN'
    elif buy_minimum > capacity:
        reason = 'RETRY_CURRENT_MIN_LOT_CAPACITY'
    elif all_in_min_cost > ticket['budget']:
        reason = 'RETRY_ORIGINAL_NAV_MIN_LOT_BUDGET'
    if reason:
        ticket['status'] = 'PAUSED'
        ticket['reason'] = reason
        ticket['plan'] = None
        return 'PAUSED'
    ticket['status'] = 'RETAINED'
    ticket['reason'] = 'RETRY_PLANNED'
    ticket['plan'] = {
        'kind': 'SEED', 'sid': ticket['sid'], 'birth_type': ticket['birth_type'],
        'signal_day': ticket['signal_day'], 'plan_day': date,
        'nav0': ticket['nav0'], 'budget': ticket['budget'],
        'ifloor': ticket['ifloor'], 'factor': ticket['current_factor'],
        'origin': ticket['origin'], 'planned_q': buy_minimum,
        'capacity': capacity, 'ticket_id': ticket['ticket_id'],
    }
    return 'PLAN'


def retry_open_outcome(ticket, *, filled, structural_pass, all_in_cost, caps):
    assert ticket['status'] not in ('CANCELLED', 'CONSUMED'), 'OLD_TICKET_CANNOT_REPLAY'
    ticket['plan'] = None
    if filled:
        assert not ticket['ever_seeded'], 'SEED_ONCE'
        ticket['ever_seeded'] = True
        ticket['status'] = 'CONSUMED'
        ticket['reason'] = 'SEED_ACTUALLY_FILLED'
        return 'CONSUMED'
    result = seed_capital_failure('SEED', structural_pass, all_in_cost, caps)
    if result['retain']:
        ticket['status'] = 'RETAINED'
        ticket['reason'] = 'RETRY_CAPITAL_ONLY_REJECT'
        return 'RETAINED'
    return cancel(ticket, 'RETRY_NON_CAPITAL_OPEN_REJECTION')


def m3_seed_exit(arm, *, historical_actual_add_count, stock_state, prior_exit_reason):
    assert stock_state in (-1, 0, 1)
    new_condition = (arm.exit_unconfirmed_m3_false
                     and historical_actual_add_count == 0 and stock_state == 0)
    if prior_exit_reason:
        return {'exit_reason': prior_exit_reason, 'new_condition': new_condition,
                'incremental_exit': False}
    return {'exit_reason': 'UNCONFIRMED_STOCK_M3_FALSE' if new_condition else None,
            'new_condition': new_condition, 'incremental_exit': new_condition}


def cohort_tags(*, signal_day, source_sector_name):
    tags = []
    if '2024-09-02' <= signal_day <= '2024-09-13':
        tags.append('ALL_SIGNALS_0902_0913')
    if signal_day in ('2024-09-06', '2024-09-09') and source_sector_name == '证券':
        tags.append('SECURITIES_SIGNALS_0906_0909')
    if '2024-10-22' <= signal_day <= '2024-10-25':
        tags.append('ALL_SIGNALS_1022_1025')
    return tags


def drawdown_path(nav_values, initial=D(1200000)):
    peak = initial
    result = []
    for nav in nav_values:
        peak = max(peak, nav)
        result.append(nav / peak - 1)
    return result
