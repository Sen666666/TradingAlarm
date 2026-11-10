"""Isolated PRICE-only permission prototype. Standard library; no I/O or accounts.

Every returned permission is as of this close, for the next eligible open only.
Pending price failures retain immutable evidence and collect no repair credit.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
from statistics import median
from typing import Literal

Mode = Literal["WAIT", "ACTIVE", "REPAIR", "ENDED"]
WINDOW = 63
A = math.sqrt(5)
K = math.sqrt(21)
S_FLOOR = math.log(1.001)
VERSION = "PRICE-PERMISSION-2-FROZEN-PENDING-FAILURE"


@dataclass(frozen=True)
class Source:
    """Versioned comparable data identity, not a pathname or account identifier."""
    universe: str
    price: str
    breadth: str
    revision: str


@dataclass(frozen=True)
class Observation:
    at: str
    source: Source
    close: float | None
    breadth: float | None


@dataclass(frozen=True)
class PriceFailure:
    sequence: int
    at: str
    source: Source
    close: float
    old_line: float
    breadth_at_failure: float | None
    scale_before_failure: float | None


@dataclass(frozen=True)
class State:
    scope: str
    source: Source | None = None
    mode: Mode = "WAIT"
    last_at: str | None = None
    previous_close: float | None = None
    # Original BREAK high uses 63 preceding observation slots, all known.
    prior_closes: tuple[float | None, ...] = ()
    # Scale uses 63 prior valid, adjacent-observation log returns.
    prior_abs_returns: tuple[float, ...] = ()
    line: float | None = None
    anchor: float | None = None
    frontier: float | None = None
    credit: float = 0.0
    scale: float | None = None
    starts: int = 0
    repairs: int = 0
    failures: int = 0
    source_changes: int = 0
    last_failure_at: str | None = None
    failure_log: tuple[PriceFailure, ...] = ()
    # Unanchored REPAIR storage phase; processed before ordinary REPAIR rules.
    pending_price_failure: PriceFailure | None = None


@dataclass(frozen=True)
class Decision:
    at: str
    scope: str
    mode: Mode
    permit_next_open: bool
    valid_for: str
    original_break: bool
    scale_before_close: float | None
    line_used: float | None
    next_line: float | None
    events: tuple[str, ...]
    unknown: tuple[str, ...]
    effective_status: str
    pending_price_failure: PriceFailure | None


def known_price(x: float | None) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and x > 0


def known_breadth(x: float | None) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) and 0 <= x <= 1


def scale_from_prior(values: tuple[float, ...]) -> float | None:
    """The current return must not be in values. No centered MAD subtraction."""
    if len(values) < WINDOW:
        return None
    if any(not math.isfinite(v) or v < 0 for v in values):
        raise ValueError("scale inputs must be finite absolute log returns")
    return max(1.4826 * median(values[-WINDOW:]), S_FLOOR)


def original_break(state: State, close: float | None, breadth: float | None) -> bool:
    return bool(
        known_price(close) and known_breadth(breadth) and breadth > .6
        and known_price(state.previous_close) and close > state.previous_close
        and len(state.prior_closes) == WINDOW
        and all(known_price(v) for v in state.prior_closes)
        and close > max(state.prior_closes)
    )


def _new_segment(state: State, close: float, scale: float) -> State:
    return replace(state, anchor=close, frontier=close, credit=0.0, scale=scale)


def _end(state: State) -> State:
    return replace(state, mode="ENDED", line=None, anchor=None, frontier=None, credit=0.0,
                   scale=None, pending_price_failure=None)


def _advance(state: State, close: float) -> State:
    assert state.frontier is not None
    if close <= state.frontier:
        return state
    return replace(state, frontier=close, credit=state.credit + math.log(close / state.frontier))


def step(state: State, observation: Observation) -> tuple[State, Decision]:
    """Pure, immutable one-close transition. Strictly ordered observations only.

    `State.line` is already effective at this observation. Updating it changes
    only the returned state, so the new line cannot fail its own creation close.
    """
    if not state.scope:
        raise ValueError("scope must identify one independent global or industry stream")
    if state.last_at is not None and observation.at <= state.last_at:
        raise ValueError("observations must be strictly increasing; no replay or revision in place")
    if not observation.at or not all(asdict(observation.source).values()):
        raise ValueError("time and all source identities are required")
    close = float(observation.close) if known_price(observation.close) else None
    breadth = float(observation.breadth) if known_breadth(observation.breadth) else None
    unknown = tuple(k for k, v in (("price", close), ("breadth", breadth)) if v is None)
    events: list[str] = []
    changed = state.source is not None and state.source != observation.source
    if changed:
        # Never splice credit, highs or scales between incomparable domains.
        state = State(
            scope=state.scope, source=observation.source, mode="ENDED", last_at=state.last_at,
            starts=state.starts, repairs=state.repairs, failures=state.failures,
            last_failure_at=state.last_failure_at, source_changes=state.source_changes + 1,
            failure_log=state.failure_log,
        )
        events.append("source_changed_context_ended")
    else:
        state = replace(state, source=observation.source)

    prior_scale = scale_from_prior(state.prior_abs_returns)
    broke = original_break(state, close, breadth)
    used = state.line
    new = state
    if state.pending_price_failure is not None:
        # Forward classification only. Waiting prices cannot form a repair
        # low/frontier, and this classification observation contributes zero.
        if close is None or breadth is None or prior_scale is None:
            events.append("pending_failure_wait_incomplete_observation")
            if prior_scale is None:
                unknown = unknown + ("scale",)
        elif breadth > .6:
            new = _new_segment(replace(state, mode="REPAIR", pending_price_failure=None),
                               close, prior_scale)
            events.append("pending_failure_classified_repair_anchor")
        else:
            new = _end(state)
            events.append("pending_failure_classified_ended")
    elif state.mode in ("WAIT", "ENDED"):
        if broke and prior_scale is not None:
            new = _new_segment(replace(state, mode="ACTIVE", starts=state.starts + 1,
                                       line=close * math.exp(-K * prior_scale)), close, prior_scale)
            events.append("break_started")
    elif state.mode == "ACTIVE":
        assert state.line is not None and state.scale is not None
        # Latest delegated ruling explicitly includes touching the old line.
        if close is not None and close <= state.line:
            receipt = PriceFailure(state.failures + 1, observation.at, observation.source,
                                   close, state.line, breadth, prior_scale)
            failed = replace(state, failures=state.failures + 1, last_failure_at=observation.at,
                             failure_log=state.failure_log + (receipt,))
            if breadth is None:
                # This has no REPAIR anchor or credit. The flag, not the
                # storage label, defines the operational pending status.
                new = replace(failed, mode="REPAIR", pending_price_failure=receipt,
                              line=None, anchor=None, frontier=None, scale=None, credit=0.0)
                events.append("price_failure_pending_breadth")
            elif breadth > .6:
                assert prior_scale is not None
                new = _new_segment(replace(failed, mode="REPAIR", line=None), close, prior_scale)
                events.append("price_failure_repair_anchor")
            else:
                new = _end(failed)
                events.append("price_failure_ended")
            # Failure dominates BREAK, advance and recovery at this close.
        elif close is not None:
            new = _advance(state, close)
            if new.credit >= A * state.scale:
                assert prior_scale is not None
                candidate = close * math.exp(-K * state.scale)
                new = _new_segment(replace(new, line=max(state.line, candidate)), close, prior_scale)
                events.append("price_advance")
    elif state.mode == "REPAIR":
        assert state.anchor is not None and state.scale is not None
        if breadth is not None and breadth <= .6:
            new = _end(state)
            events.append("repair_breadth_failure_ended")
        elif close is not None:
            if close < state.anchor:
                new = _new_segment(state, close, state.scale)
                events.append("repair_new_low_credit_reset")
            else:
                new = _advance(state, close)
                if new.credit >= A * state.scale and breadth is not None and breadth > .6:
                    assert prior_scale is not None
                    # The old ACTIVE line was disproved. This is a fresh repair
                    # episode; retaining max(old_line, candidate) would refail
                    # an allowed recovery below the old 63-observation high.
                    new = _new_segment(replace(new, mode="ACTIVE", repairs=state.repairs + 1,
                                               line=close * math.exp(-K * state.scale)), close, prior_scale)
                    events.append("repair_restored")
    else:
        raise ValueError("invalid mode")

    # Append today's inputs AFTER every rule using the prior-only scale/high.
    returns = state.prior_abs_returns
    if close is not None and state.previous_close is not None:
        returns = (returns + (abs(math.log(close / state.previous_close)),))[-WINDOW:]
    new = replace(new, last_at=observation.at, previous_close=close,
                  prior_closes=(state.prior_closes + (close,))[-WINDOW:], prior_abs_returns=returns)
    permit = (new.mode == "ACTIVE" and new.pending_price_failure is None
              and close is not None and breadth is not None and breadth > .6)
    decision = Decision(
        at=observation.at, scope=state.scope, mode=new.mode, permit_next_open=permit,
        valid_for="next_eligible_open_only; never_same_day_fill", original_break=broke,
        scale_before_close=prior_scale, line_used=used, next_line=new.line,
        events=tuple(events), unknown=unknown,
        effective_status="PENDING_PRICE_FAILURE" if new.pending_price_failure is not None else new.mode,
        pending_price_failure=new.pending_price_failure,
    )
    return new, decision


def run(observations: tuple[Observation, ...], scope: str) -> tuple[State, tuple[Decision, ...]]:
    state = State(scope=scope)
    decisions = []
    for observation in observations:
        state, decision = step(state, observation)
        decisions.append(decision)
    return state, tuple(decisions)


def dumps(state: State) -> str:
    return json.dumps({"version": VERSION, "state": asdict(state)}, sort_keys=True, allow_nan=False)


def loads(payload: str) -> State:
    x = json.loads(payload)
    if set(x) != {"version", "state"} or x["version"] != VERSION:
        raise ValueError("checkpoint version mismatch")
    v = x["state"]
    if v["source"] is not None:
        v["source"] = Source(**v["source"])
    v["prior_closes"] = tuple(v["prior_closes"])
    v["prior_abs_returns"] = tuple(v["prior_abs_returns"])
    def failure(row):
        row = dict(row)
        row["source"] = Source(**row["source"])
        return PriceFailure(**row)
    v["failure_log"] = tuple(failure(row) for row in v["failure_log"])
    if v["pending_price_failure"] is not None:
        v["pending_price_failure"] = failure(v["pending_price_failure"])
    result = State(**v)
    if result.mode not in ("WAIT", "ACTIVE", "REPAIR", "ENDED"):
        raise ValueError("invalid checkpoint mode")
    if result.failures != len(result.failure_log):
        raise ValueError("failure log/count mismatch")
    if result.pending_price_failure is not None:
        if (result.mode != "REPAIR" or not result.failure_log
                or result.pending_price_failure != result.failure_log[-1]
                or result.pending_price_failure.breadth_at_failure is not None
                or any(x is not None for x in (result.line, result.anchor, result.frontier, result.scale))
                or result.credit != 0):
            raise ValueError("invalid pending-failure checkpoint")
    return result
