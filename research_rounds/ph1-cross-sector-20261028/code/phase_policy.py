"""Pure PH1/F position protection policy; no market or account side effects.

Prices must already share the same causal corporate-action coordinate.  The
caller initializes TRIAL once on first fill and closes it only after liquidation.
This module does not size orders, interpret fills, or manufacture missing facts.
"""
from __future__ import annotations

from datetime import date, datetime
import importlib.util
import math
from pathlib import Path


_ROOT = Path(__file__).resolve().parents[3]
_ARITH = _ROOT / "research_rounds/s-amount-confirmation-20261028/code/s_amount_arithmetic.py"
_SPEC = importlib.util.spec_from_file_location("ph1_frozen_arithmetic", _ARITH)
_MOD = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MOD)
compare, higher = _MOD.compare, _MOD.higher

PHASES = frozenset(("FLAT", "TRIAL", "BRIDGE", "TREND", "EXIT_PENDING"))


def _price(value, field):
    value = float(value)
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"{field}: finite positive price required")
    return value


def _flag(value, field):
    if value is None:
        raise ValueError(f"{field}: explicit boolean fact required")
    if value == True:
        return True
    if value == False:
        return False
    raise ValueError(f"{field}: explicit boolean fact required")


def _time(value, field):
    """Preserve date-only precision instead of inventing a closing timestamp."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value) if len(value) == 10 else datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field}: ISO date/datetime required") from exc
    raise ValueError(f"{field}: date/datetime required")


def _date(value):
    return value.date() if isinstance(value, datetime) else value


def _later(pivot_at, entry_at):
    if isinstance(pivot_at, datetime) and isinstance(entry_at, datetime):
        try:
            return pivot_at > entry_at
        except TypeError as exc:
            raise ValueError("mixed timezone precision in pivot_at/entry_at") from exc
    return _date(pivot_at) > _date(entry_at)


def _not_future(pivot_at, at, field):
    if isinstance(pivot_at, datetime) and isinstance(at, datetime):
        try:
            valid = pivot_at <= at
        except TypeError as exc:
            raise ValueError(f"mixed timezone precision in {field}/at") from exc
    else:
        valid = _date(pivot_at) <= _date(at)
    if not valid:
        raise ValueError(f"{field}: future pivot is not an available fact")


def step(state, obs, policy):
    """Return {'state': copy, 'diagnostic': dict}; never mutate input.

    policy: F (use finer supports throughout) or PH (TRIAL -> BRIDGE/TREND).
    risk_on=True means ACT permits continued holding. original_up is original
    E0 validity. E/E_prev are current/prior E0 supports. E_up/F_up explicitly
    identify upward events; absent-event pivot fields may be None. obs.at is
    the current close, and entry_at is the FIRST actual fill time.
    """
    if policy not in ("F", "PH"):
        raise ValueError("policy must be F or PH")
    new = dict(state)
    phase = new["phase"]
    if phase not in PHASES:
        raise ValueError(f"unknown phase: {phase}")
    if policy == "F" and phase in ("BRIDGE", "TREND"):
        raise ValueError("F policy cannot inherit PH handoff state")
    diagnostic = {
        "policy": policy, "phase_before": phase, "phase_after": phase,
        "P_before": new.get("P"), "P_after": new.get("P"),
        "exit_required": False, "exit_reason": None, "exit_causes": [],
        "handoff": False, "handoff_checks": None,
        "F_eligible": False, "F_applied": False,
    }
    if phase == "FLAT":
        return {"state": new, "diagnostic": diagnostic}
    if phase == "EXIT_PENDING":
        diagnostic.update(exit_required=True, exit_reason="locked", exit_causes=["locked"])
        return {"state": new, "diagnostic": diagnostic}

    P = _price(new["P"], "P")
    entry_support = _price(new["E_entry"], "E_entry")
    entry_at = _time(new["entry_at"], "entry_at")
    at = _time(obs["at"], "at")
    _not_future(entry_at, at, "entry_at")
    causes = []
    if _flag(obs["exit_pending"], "exit_pending"):
        causes.append("locked")
    if not _flag(obs["risk_on"], "risk_on"):
        causes.append("ACT")
    if not _flag(obs["original_up"], "original_up"):
        causes.append("E0")
    # A locked/structural exit does not depend on obtaining a new support.
    if not causes and compare(_price(obs["close"], "close"), P) <= 0:
        causes.append("protection")
    if causes:
        new["phase"] = "EXIT_PENDING"
        diagnostic.update(phase_after="EXIT_PENDING", exit_required=True,
                          exit_reason=causes[0], exit_causes=causes)
        return {"state": new, "diagnostic": diagnostic}

    E = _price(obs["E"], "E")
    E_prev = _price(obs["E_prev"], "E_prev")
    if compare(E, E_prev) < 0:
        raise ValueError("E0 support fell within a live valid structure/price coordinate")
    E_up = _flag(obs["E_up"], "E_up")
    F_up = _flag(obs["F_up"], "F_up")

    handoff = False
    if policy == "PH" and phase == "TRIAL":
        checks = {"original_up": True, "E_up": E_up,
                  "pivot_after_entry": False, "pivot_above_entry_support": False,
                  "E_raised": compare(E, E_prev) > 0}
        if E_up:
            pivot_at = _time(obs["pivot_at"], "pivot_at")
            _not_future(pivot_at, at, "pivot_at")
            pivot = _price(obs["pivot"], "pivot")
            checks["pivot_after_entry"] = _later(pivot_at, entry_at)
            checks["pivot_above_entry_support"] = compare(pivot, entry_support) > 0
        diagnostic["handoff_checks"] = checks
        handoff = all(checks.values())
    if handoff:
        # M has priority over today's fine event; it cannot tighten L_star.
        new["L_star"] = higher(P, E)
        new["P"] = new["L_star"]
        new["phase"] = "TREND" if compare(E, new["L_star"]) >= 0 else "BRIDGE"
        diagnostic["handoff"] = True
    else:
        new["P"] = higher(P, E)
        if phase in ("BRIDGE", "TREND"):
            L_star = _price(new["L_star"], "L_star")
            if compare(P, L_star) < 0:
                raise ValueError("protection below frozen handoff floor")
            if phase == "BRIDGE" and compare(E, L_star) >= 0:
                new["phase"] = "TREND"
        elif F_up:
            F_at = _time(obs["F_pivot_at"], "F_pivot_at")
            _not_future(F_at, at, "F_pivot_at")
            F_pivot = _price(obs["F_pivot"], "F_pivot")
            if _date(F_at) >= _date(entry_at):
                diagnostic["F_eligible"] = True
                diagnostic["F_applied"] = compare(F_pivot, new["P"]) > 0
                new["P"] = higher(new["P"], F_pivot)
    diagnostic.update(phase_after=new["phase"], P_after=new["P"])
    return {"state": new, "diagnostic": diagnostic}
