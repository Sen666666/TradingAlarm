"""Public B5 evidence/policy orchestration; no account or execution layer."""
from __future__ import annotations

from evidence import build_evidence
from policy import e0_policy


def run_b5(f, enhancements=False):
    """Return evidence, journal, state and ledger under those exact dict keys.

    journal contains `events` (pure E0 market receipts) and `strength` (the
    unchanged frozen B4 journal).  enhancements=True has no defined policy and
    is rejected; False consumes E0 facts without consulting strength fields.
    """
    if enhancements is True:
        raise NotImplementedError("B5 strength-enhanced participation is not specified or implemented")
    evidence, journal = build_evidence(f)
    state, ledger = e0_policy(evidence, enhancements=enhancements)
    return dict(evidence=evidence, journal=journal, state=state, ledger=ledger)
