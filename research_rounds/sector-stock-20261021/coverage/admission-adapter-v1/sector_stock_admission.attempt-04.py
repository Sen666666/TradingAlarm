"""Pure technical admission adapter. No account, fill, sizing or trend calculation.

Inputs are explicit point-in-time facts; this module does not authenticate them.
Read the frozen scope and INTERFACE.md before integrating with an executor.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from datetime import date, datetime
import math
from typing import Any, Iterable, Literal, Mapping, Sequence

import numpy as np

Variant = Literal['T0', 'T1', 'S0']


def _aware(t: datetime) -> None:
    if t.tzinfo is None or t.utcoffset() is None:
        raise ValueError('Timezone-aware timestamps are required')


@dataclass(frozen=True)
class Clock:
    decision_at: datetime
    earliest_execution_at: datetime
    session_date: date

    def __post_init__(self):
        _aware(self.decision_at)
        _aware(self.earliest_execution_at)
        if self.earliest_execution_at <= self.decision_at:
            raise ValueError('Execution must be strictly after the decision cutoff')
        if self.session_date > self.decision_at.date():
            raise ValueError('Rank observation session cannot be in the future')


@dataclass(frozen=True)
class Fact:
    value: Any
    known_at: datetime
    valid_from: datetime
    valid_to: datetime | None = None
    source_id: str = ''
    observed_at: datetime | None = None
    basis: str = 'historical'

    def read(self, clock: Clock, *, for_execution: bool = False):
        for t in (self.known_at, self.valid_from, self.valid_to, self.observed_at):
            if t is not None:
                _aware(t)
        if self.valid_to is not None and self.valid_to <= self.valid_from:
            raise ValueError('Invalid historical interval')
        if self.basis not in ('historical', 'snapshot'):
            raise ValueError('Unknown evidence basis')
        at = clock.earliest_execution_at if for_execution else clock.decision_at
        if self.known_at > clock.decision_at or self.valid_from > at:
            return None
        if self.valid_to is not None and at >= self.valid_to:
            return None
        # A current snapshot cannot assert that its contents held in the past.
        if self.basis == 'snapshot':
            if self.observed_at is None or at < self.observed_at:
                return None
        return self.value


@dataclass(frozen=True)
class Rank:
    score: float | None
    observation_at: datetime
    known_at: datetime

    def read(self, clock: Clock) -> float | None:
        _aware(self.observation_at)
        _aware(self.known_at)
        if (self.known_at > clock.decision_at or self.observation_at > clock.decision_at
                or self.observation_at.date() != clock.session_date):
            return None
        if self.score is None or not math.isfinite(self.score):
            return None
        return float(np.round(float(self.score), 12))


@dataclass(frozen=True)
class Sector:
    sector_id: str
    trend_up: Fact
    rank: Rank | None = None


@dataclass(frozen=True)
class Security:
    security_id: str
    issuer_id: Fact
    sector_id: Fact
    common_ready: Fact  # Same historical-data universe for all three variants.
    buy_allowed: Fact  # Listed / southbound buy status resolved by data bridge.
    company_cap_cny: Fact
    trend_up: Fact
    rank: Rank | None = None


@dataclass(frozen=True)
class Occupancy:
    security_id: str
    issuer_id: str
    sector_id: str
    known_at: datetime
    has_position: bool = False
    pending_buy: bool = False
    partial_fill: bool = False
    exit_latched: bool = False


@dataclass(frozen=True)
class ExitCompletion:
    security_id: str
    event_id: str
    completed_at: datetime


@dataclass(frozen=True)
class Memory:
    security_id: str
    last_known_q: bool | None = None
    waiting: bool = False
    created_at: datetime | None = None
    origin: str | None = None
    last_exit_event: str | None = None
    pending_reentry: bool = False


@dataclass(frozen=True)
class Eligibility:
    security_id: str
    issuer_id: str | None
    sector_id: str | None
    q: bool | None
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    variant: Variant
    decision_at: datetime
    eligibility: tuple[Eligibility, ...]
    memories: tuple[Memory, ...]
    selected: tuple[str, ...]  # Slot recommendations, not committed cash/orders.
    waiting: tuple[str, ...]
    continue_buys: tuple[str, ...]
    pause_buys: tuple[str, ...]
    cancel_buys: tuple[str, ...]
    exit_requests: tuple[str, ...]
    ranking_fallbacks: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]


def rs_score(valid_closes: Sequence[float]) -> float | None:
    """Frozen 4x63-observation RS formula; no trend or state inference.

    Caller supplies an increasing, already audited eligible-price clock. No
    filling/filtering of malformed observations is performed in this adapter.
    """
    if any(not math.isfinite(x) or x <= 0 for x in valid_closes):
        raise ValueError('RS requires positive finite eligible closes')
    if len(valid_closes) < 253:
        return None
    c0, c63, c126, c189, c252 = (float(valid_closes[-1-i]) for i in (0, 63, 126, 189, 252))
    value = .4 * (c0/c63-1) + .2 * (c63/c126-1) + .2 * (c126/c189-1) + .2 * (c189/c252-1)
    return value if math.isfinite(value) else None


def _bool_fact(fact: Fact, clock: Clock, *, for_execution=False) -> bool | None:
    value = fact.read(clock, for_execution=for_execution)
    if value is not None and type(value) is not bool:
        raise ValueError('Boolean fact must be bool or None')
    return value


def eligibility(s: Security, sectors: Mapping[str, Sector], clock: Clock,
                variant: Variant) -> Eligibility:
    if variant not in ('T0', 'T1', 'S0'):
        raise ValueError('Unknown strategy variant')
    issuer = s.issuer_id.read(clock, for_execution=True)
    sector = s.sector_id.read(clock, for_execution=True)
    if issuer is not None and (not isinstance(issuer, str) or not issuer):
        raise ValueError('Invalid issuer ID')
    if sector is not None and (not isinstance(sector, str) or not sector):
        raise ValueError('Invalid sector ID')
    common = _bool_fact(s.common_ready, clock)
    buy = _bool_fact(s.buy_allowed, clock, for_execution=True)
    cap = s.company_cap_cny.read(clock)
    if cap is not None and (isinstance(cap, bool) or not isinstance(cap, (int, float))
                            or not math.isfinite(cap) or cap < 0):
        raise ValueError('Invalid company market cap')
    stock_up = _bool_fact(s.trend_up, clock)
    checks = {'common_ready': common, 'buy_allowed': buy,
              'cap_above_10bn': None if cap is None else cap > 10_000_000_000,
              'stock_up': stock_up,
              'issuer_known': True if issuer is not None else None,
              'sector_known': True if sector is not None and sector in sectors else None}
    if variant != 'T0':
        checks['sector_up'] = (None if sector not in sectors
                               else _bool_fact(sectors[sector].trend_up, clock))
    unknown = tuple(k + ':unknown' for k, v in checks.items() if v is None)
    failed = tuple(k + ':false' for k, v in checks.items() if v is False)
    # Unknown is retained even if a separate known component is false.
    q = None if unknown else not failed
    return Eligibility(s.security_id, issuer, sector, q, unknown + failed)


def _ordered(ids: Iterable[str], scores: Mapping[str, float | None], batch: str,
             fallbacks: list[str]) -> list[str]:
    ids = sorted(ids)
    if any(scores.get(i) is None for i in ids):
        fallbacks.append(batch)
        return ids
    return sorted(ids, key=lambda i: (-scores[i], i))


def _priority(ids: Iterable[str], securities: Mapping[str, Security],
              sectors: Mapping[str, Sector], resolved: Mapping[str, Eligibility],
              clock: Clock, variant: Variant, fallbacks: list[str], batch: str) -> list[str]:
    ids = sorted(ids)
    stock_scores = {i: securities[i].rank.read(clock) if securities[i].rank else None for i in ids}
    if variant != 'S0':
        return _ordered(ids, stock_scores, batch + ':stocks', fallbacks)
    groups: dict[str, list[str]] = defaultdict(list)
    for i in ids:
        groups[resolved[i].sector_id].append(i)
    sector_scores = {g: sectors[g].rank.read(clock) if sectors[g].rank else None for g in groups}
    sector_order = _ordered(groups, sector_scores, batch + ':sectors', fallbacks)
    queues = {g: _ordered(groups[g], stock_scores, batch + ':stocks:' + g, fallbacks)
              for g in sector_order}
    result = []
    # First stock from each sector, then second; capacity is applied separately.
    for n in range(max((len(v) for v in queues.values()), default=0)):
        result.extend(queues[g][n] for g in sector_order if n < len(queues[g]))
    return result


def decide(*, clock: Clock, variant: Variant, securities: Sequence[Security],
           sectors: Sequence[Sector], previous: Sequence[Memory] = (),
           occupied: Sequence[Occupancy] = (), bootstrap: bool = False,
           completed_exits: Sequence[ExitCompletion] = ()) -> Decision:
    """Return a deterministic next state without mutating inputs.

    `bootstrap` is explicitly permitted only at the caller's account start.
    `completed_exits` are executor acknowledgements known by the cutoff, not
    inferred from trend recovery. Missing security observations preserve waiting
    memory and pause orders. New admissions are capacity recommendations only.
    """
    if variant not in ('T0', 'T1', 'S0'):
        raise ValueError('Unknown strategy variant')
    if bootstrap and previous:
        raise ValueError('Bootstrap cannot be replayed over existing memory')
    stock = {s.security_id: s for s in securities}
    sect = {s.sector_id: s for s in sectors}
    old = {m.security_id: m for m in previous}
    occ = {o.security_id: o for o in occupied}
    if any(len(xs) != len(ys) for xs, ys in ((stock, securities), (sect, sectors),
                                            (old, previous), (occ, occupied))):
        raise ValueError('Duplicate stable ID')
    if len({o.issuer_id for o in occupied}) != len(occupied):
        raise ValueError('Portfolio already contains duplicate issuer lines')
    for o in occupied:
        _aware(o.known_at)
        if o.known_at > clock.decision_at:
            raise ValueError('Future portfolio snapshot')
        if not (o.has_position or o.pending_buy or o.exit_latched):
            raise ValueError('Empty occupancy cannot reserve a slot')
        if o.partial_fill and not (o.has_position and o.pending_buy):
            raise ValueError('Partial fill requires both holdings and a pending buy')
    completions = {e.security_id: e for e in completed_exits}
    if len(completions) != len(completed_exits):
        raise ValueError('Duplicate exit-completion security')
    for e in completed_exits:
        _aware(e.completed_at)
        if e.completed_at > clock.decision_at or not e.event_id:
            raise ValueError('Future or unidentified exit completion')
    if set(completions) & set(occ):
        raise ValueError('Completed exit still occupies the portfolio')
    resolved = {i: eligibility(s, sect, clock, variant) for i, s in stock.items()}
    for o in occupied:
        e = resolved.get(o.security_id)
        if e is not None:
            if e.issuer_id is not None and e.issuer_id != o.issuer_id:
                raise ValueError('Portfolio issuer identity must be reconciled at cutoff')
            if e.sector_id is not None and e.sector_id != o.sector_id:
                raise ValueError('Portfolio classification must be updated at cutoff')
    all_ids = set(stock) | set(old) | set(occ) | set(completions)
    for i in all_ids - set(stock):
        resolved[i] = Eligibility(i, None, None, None, ('observation:unknown',))
    memories = {}
    for i in sorted(all_ids):
        m = old.get(i, Memory(i))
        if m.created_at is not None:
            _aware(m.created_at)
            if m.created_at > clock.decision_at:
                raise ValueError('Future candidate memory')
        completion = completions.get(i)
        if completion is not None and completion.event_id != m.last_exit_event:
            m = replace(m, last_exit_event=completion.event_id, pending_reentry=True)
        q = resolved[i].q
        if q is False:
            m = replace(m, last_known_q=False, waiting=False, pending_reentry=False)
        elif q is True:
            origin = ('completed_exit_reentry' if m.pending_reentry else
                      'eligibility_rising_edge' if m.last_known_q is False else
                      'initial_carry_in' if bootstrap and i not in old else None)
            if origin is not None:
                m = replace(m, waiting=True, created_at=clock.decision_at, origin=origin, pending_reentry=False)
            m = replace(m, last_known_q=True)
        if i in occ:
            # Acknowledged reservation/holding consumes the waiting candidate.
            # It cannot reappear merely because an occupancy row disappears.
            m = replace(m, waiting=False)
        memories[i] = m
    continuing, paused, cancelled, exits = [], [], [], []
    active_occupants = []
    for o in occupied:
        q = resolved[o.security_id].q
        stock_up = _bool_fact(stock[o.security_id].trend_up, clock) if o.security_id in stock else None
        exiting = o.exit_latched or (o.has_position and stock_up is False)
        if exiting:
            exits.append(o.security_id)
        cancel = o.pending_buy and (q is False or exiting)
        if cancel:
            cancelled.append(o.security_id)
        elif o.pending_buy:
            (paused if q is None else continuing).append(o.security_id)
        # Cancellation only frees an unfilled reservation, never an actual holding.
        if o.has_position or o.exit_latched or (o.pending_buy and not cancel):
            active_occupants.append(o)
    fallbacks = []
    partial = sorted(i for i in continuing if occ[i].partial_fill)
    unstarted = [i for i in continuing if not occ[i].partial_fill]
    continue_order = partial + _priority(unstarted, stock, sect, resolved, clock, variant,
                                         fallbacks, 'continuing')
    occupied_ids = {o.security_id for o in active_occupants}
    occupied_issuers = {o.issuer_id for o in active_occupants}
    counts = Counter(o.sector_id for o in active_occupants)
    eligible_wait = [i for i, m in memories.items() if m.waiting and resolved[i].q is True
                     and i not in occupied_ids]
    priority = _priority(eligible_wait, stock, sect, resolved, clock, variant, fallbacks, 'waiting')
    selected, rejected = [], []
    # Skip a duplicate issuer / blocked line inside the same sector turn. A
    # rejected A/H alias must not consume that sector's one successful admission.
    queues: dict[str, list[str]] = {}
    for i in priority:
        group = resolved[i].sector_id if variant == 'S0' else 'global'
        queues.setdefault(group, []).append(i)
    while any(queues.values()):
        for queue in queues.values():
            while queue:
                i = queue.pop(0)
                e = resolved[i]
                if e.issuer_id in occupied_issuers:
                    reason = 'issuer_already_occupied'
                elif len(occupied_issuers) >= 6:
                    reason = 'total_slots_full'
                elif counts[e.sector_id] >= 2:
                    reason = 'sector_issuer_slots_full'
                elif e.sector_id not in counts and len(counts) >= 3:
                    reason = 'sector_slots_full'
                else:
                    selected.append(i)
                    occupied_issuers.add(e.issuer_id)
                    counts[e.sector_id] += 1
                    break
                rejected.append((i, reason))
    waiting = tuple(sorted(i for i, m in memories.items() if m.waiting and i not in occupied_ids
                           and i not in selected))
    return Decision(variant, clock.decision_at, tuple(resolved[i] for i in sorted(resolved)),
                    tuple(memories[i] for i in sorted(memories)), tuple(selected), waiting,
                    tuple(continue_order), tuple(sorted(paused)), tuple(sorted(cancelled)),
                    tuple(sorted(exits)), tuple(fallbacks), tuple(rejected))
