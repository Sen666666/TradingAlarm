"""Cost-cap admission observer over the original authoritative native account.

No strategy/exit/price model is defined here. Filled cost is actual buy gross
plus buy fees, reduced only by actual sell allocation. Native CA quantities
are authoritative; surviving split batches retain their monetary cost.
"""
from decimal import Decimal as D

ZERO = D(0)


def init(account, alpha, release=True):
    account.capacity_alpha = D(str(alpha))
    account.capacity_release = bool(release)
    account.capacity_basis = {}
    account.capacity_entry = {}
    account.capacity_events = []
    account.capacity_in_callback = False
    account.capacity_legacy_ids = {x['id'] for x in account.layers if x['qty']}


def context(a, at, slip):
    assert not a.capacity_in_callback, 'cannot inspect/admit inside a half-applied native callback'
    marks = a.market.marks(at, a.positions)
    native = a.balance(at, marks)
    used = protected_cost = ZERO
    unknown = []
    details = []
    counts = dict(unprotected=0, protected=0, qualification_protected=0, released=0, locked=0, breached=0)
    for layer in a.layers:
        q = layer['qty']
        if not q:
            continue
        key, sid = layer['id'], layer['sid']
        # A pre-existing live batch is grandfathered. All new native fills
        # acquire an observer basis in the same callback below.
        if key not in a.capacity_basis:
            assert key in a.capacity_legacy_ids, ('new live batch missing cost basis', key)
            continue
        basis = a.capacity_basis[key]
        assert basis.is_finite() and basis >= 0, ('invalid actual cost basis', key)
        assert key in a.capacity_entry, ('new live batch missing entry observer', key)
        try:
            meta = a.jmeta[key]
            factor = a.facts.factor(sid, at)
            floor = D(str(meta['last_core_line'])) if layer['kind'] == 'core' else layer['floor']
            floor = floor / factor
            entry = a.capacity_entry[key]
            price = marks[sid].cny_price(at)
            known = all(v.is_finite() for v in (floor, entry, price, factor)) and factor > 0 and entry > 0 and price > 0 and floor >= 0
        except (KeyError, ValueError, ArithmeticError, TypeError):
            known = False
        locked = sid in a.exits
        hit = known and floor >= entry and price > floor and not locked
        protected = bool(a.capacity_release and hit)
        counts['qualification_protected'] += int(hit)
        counts['released'] += int(protected)
        if not known:
            unknown.append(key)
        counts['locked'] += int(locked)
        counts['breached'] += int(known and price <= floor)
        counts['protected' if protected else 'unprotected'] += 1
        if protected:
            protected_cost += basis
        else:
            used += basis
        details.append(dict(layer=key, sid=sid, qty=q, basis=basis, floor=floor if known else None,
                            entry=entry if known else None, mark=price if known else None,
                            protected=protected, known=known, exit_locked=locked))
    pending = drag = ZERO
    orders = {}
    for sid, order in a.buys.items():
        cost = order.remaining_budget_cny + order.fee_reserved_cny
        # A full pending execution can debit fees and execution-vs-mark
        # slippage. Reserve this NAV drag before any order is admitted.
        loss = order.fee_reserved_cny + order.remaining_budget_cny * slip / (D(1) + slip)
        pending += cost
        drag += loss
        orders[sid] = dict(cost=cost, drag=loss, remaining_gross=order.remaining_budget_cny,
                           remaining_fee=order.fee_reserved_cny, remaining_qty=order.remaining_shares,
                           order_id=order.order_id)
    return dict(at=at, NAV=native['nav'], used_cost=used, protected_cost=protected_cost,
                pending_cost=pending, pending_drag=drag, guard_NAV=native['nav']-drag,
                unknown_layers=unknown, counts=counts, orders=orders, layers=details)


def reserve_allowed(a, c, q, execution_price, mark, fee):
    cost = D(q) * execution_price + fee
    nav = c['guard_NAV'] - fee - D(q) * max(ZERO, execution_price-mark)
    # Unknown protection qualifies for no release; its known monetary basis
    # remains fully charged. Unknown basis/NAV is a hard integrity failure.
    return nav.is_finite() and nav > 0 and c['used_cost'] + c['pending_cost'] + cost <= a.capacity_alpha * nav


def snapshot(a, c, kind, **extra):
    value = {k: c[k] for k in ('at', 'NAV', 'used_cost', 'protected_cost', 'pending_cost', 'pending_drag', 'guard_NAV', 'unknown_layers', 'counts')}
    value.update(kind=kind, alpha=a.capacity_alpha, release=a.capacity_release, **extra)
    value['sequence'] = len(a.capacity_events)
    value['native_audit_count'] = len(a.audit_log)
    value['native_trade_count'] = len(a.trades)
    value['native_journal_count'] = len(a.journal)
    if kind in ('actual_reserve', 'actual_buy_fill', 'fill_cost_cap_cancel'):
        value['layers'] = c['layers']
        value['orders'] = c['orders']
    a.capacity_events.append(value)
    return value


def after_buy(a, receipt, layer):
    key = layer['id']
    assert key not in a.capacity_basis
    a.capacity_basis[key] = receipt.gross_cny + receipt.fees_cny
    a.capacity_entry[key] = receipt.gross_cny / D(receipt.shares)


def after_sell(a, before, parts, at):
    for part in parts:
        key = part['layer']
        if key in a.capacity_basis:
            q = before[key]
            amount = a.capacity_basis[key] * D(part['shares']) / D(q)
            a.capacity_basis[key] -= amount
            a.capacity_events.append(dict(kind='actual_sell_basis_removed', at=at, layer=key, shares=part['shares'], before_qty=q, removed_basis=amount))


def after_split(a, before, ratio, at):
    current = {x['id']: x['qty'] for x in a.layers}
    for key in before:
        if key not in a.capacity_basis:
            continue
        a.capacity_entry[key] /= ratio
        if not current[key]:
            amount = a.capacity_basis[key]
            a.capacity_basis[key] = ZERO
            a.capacity_events.append(dict(kind='native_fraction_zero_batch_cost_writeoff', at=at, layer=key, amount=amount))
    a.capacity_events.append(dict(kind='native_split_cost_preserved', at=at, ratio=ratio,
                                  before_qty=before, after_qty={k: current[k] for k in before}))
