"""Import-safe PRICE execution responsibility book. No broker or market I/O.

Only PROXY and SYNTHETIC_TEST evidence is accepted. Caller owns market/root
facts, common calendar, dated sizing, fees, budgets, risk and industry gates.
An OpenPermission asserts those checks; this module never derives them from OHLC.
Clock sequences: precheck=10, target/order=20, fill=30, complete=40, close=100.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
import math
from typing import Any

RootId = tuple[str, str, str]

class EvidenceDomain(str, Enum):
    PROXY = "PROXY"
    SYNTHETIC_TEST = "SYNTHETIC_TEST"

class Role(str, Enum):
    PROBE = "PROBE"
    ADD = "ADD"

class ExecutionRejected(ValueError):
    pass

@dataclass(frozen=True, order=True)
class Clock:
    day: str
    sequence: int

    def __post_init__(self):
        if date.fromisoformat(self.day).isoformat() != self.day:
            raise ValueError("day must be canonical ISO date")
        if type(self.sequence) is not int or self.sequence < 0:
            raise ValueError("sequence must be a nonnegative integer")

@dataclass(frozen=True)
class Receipt:
    root_id: RootId
    frontier_day: str
    known_at: Clock
    eligible_open: str

    def __post_init__(self):
        date.fromisoformat(self.frontier_day)
        date.fromisoformat(self.eligible_open)
        if self.known_at.day < self.frontier_day or self.eligible_open <= self.frontier_day:
            raise ValueError("invalid receipt chronology")

    @property
    def receipt_id(self):
        return (self.root_id, self.frontier_day)

@dataclass(frozen=True)
class OpenPermission:
    receipt: Receipt
    decision_open: str
    known_at: Clock
    raw_open: float
    protection_raw: float
    feasible_qty: int
    budget: float
    evidence_version: str
    checks_passed: bool
    confirmed: bool = False
    close_net_positive: bool = False
    open_net_positive: bool = False

@dataclass(frozen=True)
class Target:
    parent_id: str
    root_id: RootId
    role: Role
    target_Q: int
    budget: float
    signal_receipt_id: tuple
    decision_open: str
    protection_raw: float
    registered_known_at: Clock
    evidence_version: str
    evidence_domain: EvidenceDomain

@dataclass
class Parent:
    target: Target
    filled_F: int = 0
    unlock_known_at: Clock | None = None
    complete_known_at: Clock | None = None
    retired: bool = False

    @property
    def target_Q(self):
        return self.target.target_Q

    @property
    def parent_id(self):
        return self.target.parent_id

@dataclass
class Order:
    order_id: str
    parent_id: str | None
    side: str
    quantity: int
    decision_open: str
    registered_known_at: Clock
    evidence_domain: EvidenceDomain
    live_leaves: int
    cancel_pending: bool = False
    terminal_filled: int | None = None
    terminal_known_at: Clock | None = None
    allocations: tuple[tuple[str, int], ...] = ()

@dataclass(frozen=True)
class Fill:
    fill_id: str
    order_id: str
    quantity: int
    price: float
    fee: float
    trade_day: str
    known_at: Clock
    evidence_domain: EvidenceDomain

    def economic_identity(self):
        return (self.order_id, self.quantity, self.price, self.fee, self.trade_day, self.evidence_domain)

@dataclass
class Lot:
    lot_id: str
    parent_id: str
    role: Role
    buy_day: str
    quantity: int
    remaining: int
    price: float
    fee: float
    known_at: Clock

@dataclass
class ExecutionBook:
    root_id: RootId
    evidence_domain: EvidenceDomain
    parents: dict[Role, Parent] = field(default_factory=dict, init=False)
    orders: dict[str, Order] = field(default_factory=dict, init=False)
    fills: dict[str, Fill] = field(default_factory=dict, init=False)
    lots: dict[str, Lot] = field(default_factory=dict, init=False)
    events: list[dict[str, Any]] = field(default_factory=list, init=False)
    unknown_reasons: list[str] = field(default_factory=list, init=False)
    retired: bool = field(default=False, init=False)
    exit_pending: bool = field(default=False, init=False)
    _receipts: dict[tuple, Receipt] = field(default_factory=dict, init=False)
    _consumed: set[tuple] = field(default_factory=set, init=False)
    _expired: set[tuple] = field(default_factory=set, init=False)
    _latest_frontier: str | None = field(default=None, init=False)
    _last_known_at: Clock | None = field(default=None, init=False)

    def __post_init__(self):
        self.evidence_domain = EvidenceDomain(self.evidence_domain)
        if not isinstance(self.root_id, tuple) or len(self.root_id) != 3 or not all(isinstance(x, str) and x for x in self.root_id):
            raise ValueError("root_id must be (sid, source_identity, root_birth_day)")
        date.fromisoformat(self.root_id[2])

    @property
    def unknown(self):
        return bool(self.unknown_reasons)

    @property
    def inventory(self):
        """Quantity alias for consumer assertions; no economic valuation."""
        return self.held_qty

    @property
    def held_qty(self):
        return sum(lot.remaining for lot in self.lots.values())

    def parent(self, role):
        return self.parents.get(Role(role))

    def _parent_by_id(self, parent_id):
        return next(parent for parent in self.parents.values() if parent.parent_id == parent_id)

    def remaining(self, role):
        parent = self.parents[Role(role)]
        return max(0, parent.target_Q - parent.filled_F)

    def complete(self, role):
        parent = self.parent(role)
        return bool(parent and not self.unknown and parent.complete_known_at is not None
                    and parent.filled_F == parent.target_Q and self.live_leaves(role) == 0
                    and self._all_settled() and not self.exit_pending and not parent.retired)

    def live_leaves(self, role=None):
        parent_id = self.parents[Role(role)].parent_id if role is not None else None
        return sum(o.live_leaves for o in self.orders.values() if role is None or o.parent_id == parent_id)

    def spent(self, role):
        parent_id = self.parents[Role(role)].parent_id
        return sum(f.quantity * f.price + f.fee for f in self.fills.values()
                   if self.orders[f.order_id].side == "BUY" and self.orders[f.order_id].parent_id == parent_id)

    def _event(self, name, known_at, **payload):
        self.events.append({"event": self.evidence_domain.value.lower() + "_" + name,
                            "known_at": known_at, "root_id": self.root_id,
                            "evidence_domain": self.evidence_domain.value, **payload})

    def _clock(self, known_at):
        if not isinstance(known_at, Clock):
            raise TypeError("explicit Clock required")
        if self._last_known_at is not None and known_at < self._last_known_at:
            raise ExecutionRejected("observation clock moved backwards")
        self._last_known_at = known_at

    def freeze_unknown(self, reason, known_at):
        self._clock(known_at)
        if reason not in self.unknown_reasons:
            self.unknown_reasons.append(reason)
            self._event("unknown", known_at, reason=reason)
        for parent in self.parents.values():
            parent.unlock_known_at = parent.complete_known_at = None

    def _fail(self, reason, known_at):
        self.freeze_unknown(reason, known_at)
        raise ExecutionRejected(reason)

    def _healthy(self):
        if self.unknown or self.retired or self.exit_pending:
            raise ExecutionRejected("UNKNOWN, retired root or pending exit blocks buy")

    def _order_filled(self, order):
        return sum(f.quantity for f in self.fills.values() if f.order_id == order.order_id)

    def _aligned(self, order):
        return (order.terminal_known_at is not None and order.live_leaves == 0
                and order.terminal_filled == self._order_filled(order))

    def _all_settled(self):
        return all(self._aligned(order) for order in self.orders.values())

    def validate_receipt(self, receipt, decision_open, known_at, after=None):
        self._healthy()
        if receipt.root_id != self.root_id:
            raise ExecutionRejected("wrong root")
        old = self._receipts.get(receipt.receipt_id)
        if old is not None and old != receipt:
            self._fail("conflicting receipt identity", known_at)
        if receipt.receipt_id in self._consumed or receipt.receipt_id in self._expired:
            raise ExecutionRejected("receipt already consumed or expired")
        if self._latest_frontier is not None and receipt.frontier_day <= self._latest_frontier:
            raise ExecutionRejected("not a strictly new frontier receipt")
        if decision_open != receipt.eligible_open or known_at.day != decision_open:
            raise ExecutionRejected("not immediate eligible common OPEN")
        if receipt.known_at >= known_at:
            raise ExecutionRejected("receipt not known strictly before OPEN")
        if after is not None and receipt.known_at <= after:
            raise ExecutionRejected("receipt not strictly later than unlock/completion")
        return True

    def _consume(self, permission):
        receipt = permission.receipt
        self._receipts[receipt.receipt_id] = receipt
        self._consumed.add(receipt.receipt_id)
        self._latest_frontier = receipt.frontier_day
        self._event("receipt_consumed", permission.known_at, receipt_id=receipt.receipt_id)

    def _expire(self, permission, reason):
        receipt = permission.receipt
        self._receipts[receipt.receipt_id] = receipt
        self._expired.add(receipt.receipt_id)
        self._latest_frontier = receipt.frontier_day
        self._event("receipt_expired_no_submit", permission.known_at,
                    receipt_id=receipt.receipt_id, reason=reason)
        return False

    def _validate_permission(self, permission, after=None):
        self.validate_receipt(permission.receipt, permission.decision_open, permission.known_at, after)
        if not self._all_settled():
            raise ExecutionRejected("unsettled order responsibility")
        if type(permission.feasible_qty) is not int or permission.feasible_qty < 0:
            raise ValueError("feasible_qty must be a nonnegative integer")
        if not all(math.isfinite(x) and x > 0 for x in (permission.raw_open, permission.protection_raw)):
            self._fail("unknown or invalid open/protection", permission.known_at)
        if not math.isfinite(permission.budget) or permission.budget < 0 or not permission.evidence_version:
            raise ValueError("explicit nonnegative budget and evidence version required")
        self._clock(permission.known_at)
        if permission.checks_passed is not True:
            return self._expire(permission, "CALLER_CHECKS_NOT_PASSED")
        if permission.raw_open <= permission.protection_raw:
            return self._expire(permission, "OPEN_AT_OR_BELOW_S")
        if permission.feasible_qty == 0:
            return self._expire(permission, "Q0")
        return True

    @staticmethod
    def _add_permission(permission):
        return (permission.confirmed is True and permission.close_net_positive is True
                and permission.open_net_positive is True)

    def open_target(self, role, permission):
        role = Role(role)
        self._healthy()
        if role in self.parents:
            raise ExecutionRejected("parent already exists; use submit_remaining")
        after = None
        if role == Role.ADD:
            if not self.complete(Role.PROBE):
                raise ExecutionRejected("probe not completely reconciled")
            after = self.parents[Role.PROBE].complete_known_at
        elif self.parents:
            raise ExecutionRejected("one probe parent per root")
        if not self._validate_permission(permission, after):
            return None
        if role == Role.ADD and not self._add_permission(permission):
            self._expire(permission, "ADD_PERMISSION_NOT_PASSED")
            return None
        parent_id = f"{self.root_id!r}:{role.value}"
        target = Target(parent_id, self.root_id, role, permission.feasible_qty, permission.budget,
                        permission.receipt.receipt_id, permission.decision_open, permission.protection_raw,
                        permission.known_at, permission.evidence_version, self.evidence_domain)
        parent = Parent(target)
        self.parents[role] = parent
        self._event("target_registered", permission.known_at, parent_id=parent_id, target_Q=target.target_Q)
        return self._new_order(parent, permission)

    # Explicit alias: never creates a target from a fill or a CLOSE reservation.
    register_target = open_target

    def submit_remaining(self, role, permission):
        role = Role(role)
        self._healthy()
        parent = self.parents[role]
        if parent.retired or parent.unlock_known_at is None or self.remaining(role) == 0:
            raise ExecutionRejected("no unlocked remainder")
        if not self._validate_permission(permission, parent.unlock_known_at):
            return None
        if role == Role.ADD and not self._add_permission(permission):
            self._expire(permission, "ADD_PERMISSION_NOT_PASSED")
            return None
        if permission.feasible_qty < self.remaining(role):
            self._expire(permission, "WHOLE_REMAINDER_NOT_FEASIBLE")
            return None
        return self._new_order(parent, permission)

    def _new_order(self, parent, permission):
        self._consume(permission)
        qty = parent.target_Q - parent.filled_F
        order_id = f"{self.root_id!r}:{self.evidence_domain.value}:{len(self.orders) + 1}"
        order = Order(order_id, parent.parent_id, "BUY", qty, permission.decision_open,
                      permission.known_at, self.evidence_domain, qty)
        self.orders[order_id] = order
        parent.unlock_known_at = parent.complete_known_at = None
        self._event("order_registered", permission.known_at, order_id=order_id, quantity=qty)
        self._reconcile(permission.known_at)
        return order

    def _lookup(self, order_id, known_at):
        if order_id not in self.orders:
            self._fail("unknown order", known_at)
        return self.orders[order_id]

    def _synthetic(self):
        if self.evidence_domain != EvidenceDomain.SYNTHETIC_TEST:
            raise ExecutionRejected("synthetic evidence cannot enter PROXY book")

    def request_cancel(self, order_id, known_at):
        self._synthetic()
        order = self._lookup(order_id, known_at)
        self._clock(known_at)
        if order.terminal_known_at is not None:
            raise ExecutionRejected("order already terminal")
        order.cancel_pending = True
        self._event("cancel_requested", known_at, order_id=order_id)
        # Leaves and unlock remain unchanged until terminal reconciliation.

    def synthetic_ack(self, order_id, *, leaves, known_at):
        self._synthetic()
        order = self._lookup(order_id, known_at)
        self._clock(known_at)
        if type(leaves) is not int or leaves < 0:
            raise ValueError("leaves must be nonnegative integer")
        if order.terminal_known_at is not None:
            self._fail("active ACK after terminal", known_at)
        order.live_leaves = leaves
        self._event("active_ack", known_at, order_id=order_id, leaves=leaves)
        self._reconcile(known_at)

    def terminal_ack(self, order_id, *, cumulative_filled, known_at):
        self._synthetic()
        self._terminal(order_id, cumulative_filled, known_at)

    def _terminal(self, order_id, cumulative_filled, known_at):
        order = self._lookup(order_id, known_at)
        if order.terminal_known_at is not None:
            if order.terminal_filled == cumulative_filled:
                return
            self._fail("conflicting terminal ACK", known_at)
        self._clock(known_at)
        if type(cumulative_filled) is not int or not 0 <= cumulative_filled <= order.quantity:
            self._fail("invalid terminal cumulative quantity", known_at)
        order.terminal_filled = cumulative_filled
        order.terminal_known_at = known_at
        order.cancel_pending = False
        order.live_leaves = 0
        self._event("terminal_reconciled" if self.evidence_domain == EvidenceDomain.PROXY else "terminal_ack",
                    known_at, order_id=order_id, cumulative_filled=cumulative_filled)
        self._reconcile(known_at)

    def synthetic_fill(self, order_id, *, fill_id, quantity, price, fee, trade_day, known_at):
        self._synthetic()
        return self._fill(order_id, fill_id, quantity, price, fee, trade_day, known_at)

    def _fill(self, order_id, fill_id, quantity, price, fee, trade_day, known_at):
        order = self._lookup(order_id, known_at)
        fill = Fill(fill_id, order_id, quantity, price, fee, trade_day, known_at, self.evidence_domain)
        old = self.fills.get(fill_id)
        if old is not None:
            if old.economic_identity() != fill.economic_identity():
                self._fail("conflicting duplicate fill", known_at)
            return old
        if type(quantity) is not int or quantity <= 0 or not fill_id:
            raise ValueError("positive integer fill quantity and fill id required")
        if not math.isfinite(price) or price <= 0 or not math.isfinite(fee) or fee < 0:
            raise ValueError("finite positive fill price and nonnegative fee required")
        date.fromisoformat(trade_day)
        if not order.decision_open <= trade_day <= known_at.day or known_at < order.registered_known_at:
            raise ExecutionRejected("invalid fill chronology")
        self._clock(known_at)
        was_aligned = self._aligned(order)
        self.fills[fill_id] = fill
        if order.terminal_known_at is None:
            order.live_leaves = max(0, order.live_leaves - quantity)
        if order.side == "BUY":
            parent = self._parent_by_id(order.parent_id)
            parent.filled_F += quantity
            self.lots[fill_id] = Lot(fill_id, parent.parent_id, parent.target.role, trade_day,
                                    quantity, quantity, price, fee, known_at)
            parent.unlock_known_at = parent.complete_known_at = None
        else:
            self._apply_sell_fill(order, quantity, trade_day, known_at)
        self._event("fill", known_at, fill_id=fill_id, order_id=order_id, quantity=quantity)
        if was_aligned:
            self.freeze_unknown("late fill after reconciled terminal/unlock", known_at)
        if self._order_filled(order) > order.quantity:
            self.freeze_unknown("order overfill", known_at)
        self._reconcile(known_at)
        return fill

    def proxy_full_fill(self, order_id, *, fill_known_at, complete_known_at, price, fee):
        if self.evidence_domain != EvidenceDomain.PROXY:
            raise ExecutionRejected("proxy completion cannot enter SYNTHETIC_TEST book")
        order = self._lookup(order_id, fill_known_at)
        if not (order.registered_known_at < fill_known_at < complete_known_at
                and fill_known_at.day == complete_known_at.day == order.decision_open):
            raise ExecutionRejected("proxy register < fill < complete at same OPEN required")
        if order.terminal_known_at is not None or self._order_filled(order):
            raise ExecutionRejected("proxy full fill is one atomic simulated completion")
        self._fill(order_id, f"{order_id}:FULL", order.quantity, price, fee, order.decision_open, fill_known_at)
        self._terminal(order_id, order.quantity, complete_known_at)
        return self._parent_by_id(order.parent_id) if order.parent_id is not None else None

    def proxy_exit_all(self, *, trade_day, submission_known_at, fill_known_at,
                       completion_known_at, price, fee, reason="PRICE_FAILED"):
        """Explicit proxy all-inventory exit, with per-lot T+1 and reconciliation.

        Prefer retiring at the actual signal CLOSE; if not already retired this
        explicit exit request retires the root at submission_known_at. Nothing
        here interprets a daily low or source change as an exit signal.
        """
        if self.evidence_domain != EvidenceDomain.PROXY:
            raise ExecutionRejected("proxy exit requires PROXY domain")
        if self.unknown:
            raise ExecutionRejected("UNKNOWN cannot manufacture a known exit")
        if not self.retired:
            self.retire_root(submission_known_at, reason)
        order = self.submit_exit(decision_open=trade_day, known_at=submission_known_at)
        self.proxy_full_fill(order.order_id, fill_known_at=fill_known_at,
                             complete_known_at=completion_known_at, price=price, fee=fee)
        return order.quantity

    def _reconcile(self, known_at):
        for order in self.orders.values():
            if order.terminal_filled is not None and self._order_filled(order) > order.terminal_filled:
                self.freeze_unknown("fill ledger exceeds terminal cumulative", known_at)
            if self._order_filled(order) + order.live_leaves > order.quantity:
                self.freeze_unknown("order F plus leaves exceeds quantity", known_at)
        for role, parent in self.parents.items():
            if parent.filled_F + self.live_leaves(role) > parent.target_Q:
                self.freeze_unknown("parent F plus leaves exceeds fixed Q", known_at)
        if self.unknown:
            return
        if self._all_settled():
            if self.retired and self.held_qty == 0:
                self.exit_pending = False
            for role, parent in self.parents.items():
                if not parent.retired and not self.exit_pending:
                    if parent.unlock_known_at is None:
                        parent.unlock_known_at = known_at
                    if parent.filled_F == parent.target_Q and parent.complete_known_at is None:
                        parent.complete_known_at = known_at

    def retire_root(self, known_at, reason="PRICE_FAILED"):
        self._clock(known_at)
        self.retired = True
        self.exit_pending = self.held_qty > 0 or not self._all_settled()
        for parent in self.parents.values():
            parent.retired = True
            parent.unlock_known_at = parent.complete_known_at = None
        for order in self.orders.values():
            if order.terminal_known_at is None:
                order.cancel_pending = True
        self._event("root_retired", known_at, reason=reason)
        # Retirement alone never reduces leaves or inventory, or clears UNKNOWN.

    def sellable_qty(self, day):
        date.fromisoformat(day)
        reserved = {}
        for order in self.orders.values():
            if order.side == "SELL" and order.terminal_known_at is None:
                for lot_id, qty in order.allocations:
                    reserved[lot_id] = reserved.get(lot_id, 0) + qty
        return sum(max(0, lot.remaining - reserved.get(lot.lot_id, 0))
                   for lot in self.lots.values() if lot.buy_day < day)

    def submit_exit(self, *, decision_open, known_at, quantity=None):
        if self.unknown:
            raise ExecutionRejected("UNKNOWN cannot manufacture a known exit")
        if not self.retired or not self._all_settled():
            raise ExecutionRejected("root must be retired and all prior orders reconciled")
        if known_at.day != decision_open:
            raise ExecutionRejected("exit clock must match decision OPEN")
        qty = self.held_qty if quantity is None else quantity
        if type(qty) is not int or qty <= 0 or qty > self.sellable_qty(decision_open):
            raise ExecutionRejected("quantity unavailable under per-lot T+1")
        self._clock(known_at)
        allocations = []
        needed = qty
        for lot in sorted(self.lots.values(), key=lambda x: (x.known_at, x.lot_id)):
            if lot.buy_day < decision_open and lot.remaining and needed:
                take = min(needed, lot.remaining)
                allocations.append((lot.lot_id, take))
                needed -= take
        order_id = f"{self.root_id!r}:{self.evidence_domain.value}:{len(self.orders) + 1}"
        order = Order(order_id, None, "SELL", qty, decision_open, known_at,
                      self.evidence_domain, qty, allocations=tuple(allocations))
        self.orders[order_id] = order
        self.exit_pending = True
        self._event("exit_registered", known_at, order_id=order_id, quantity=qty)
        return order

    def _apply_sell_fill(self, order, quantity, trade_day, known_at):
        previous = self._order_filled(order) - quantity
        remaining = quantity
        for lot_id, allocated in order.allocations:
            skip = min(previous, allocated)
            previous -= skip
            take = min(remaining, allocated - skip)
            if take:
                lot = self.lots[lot_id]
                if lot.buy_day >= trade_day or take > lot.remaining:
                    self.freeze_unknown("invalid per-lot sell fill", known_at)
                    return
                lot.remaining -= take
                remaining -= take
        if remaining:
            self.freeze_unknown("sell exceeds reserved lots", known_at)

    def responsibility(self):
        return {"root_id": self.root_id, "evidence_domain": self.evidence_domain.value,
                "unknown": self.unknown, "unknown_reasons": tuple(self.unknown_reasons),
                "retired": self.retired, "held_qty": self.held_qty,
                "live_leaves": self.live_leaves(), "all_orders_reconciled": self._all_settled(),
                "exit_pending": self.exit_pending,
                "owner_locked": bool(self.unknown or self.held_qty or not self._all_settled()
                                     or self.exit_pending or (self.parents and not self.retired)),
                "actual_order_id": "NOT_PROVIDED", "actual_ack": "NOT_PROVIDED",
                "actual_fill": "NOT_PROVIDED", "historical_tradability": "UNKNOWN"}
