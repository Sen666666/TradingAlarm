"""E0-NR1: no independent reclaim entry; frozen E0 remains unchanged.

Use the existing B5 input/source-boundary contract. Raw decline/reclaim evidence
may still be inspected, but cannot create participation through this policy.
This is a separately named research version, not a replacement for frozen E0.
"""
VERSION = 'E0-NR1'

def e0_nr1_policy(evidence):
    from policy import e0_policy
    view = evidence.copy()
    view['decline_candidate'] = False
    return e0_policy(view, enhancements=False)

def run_e0_nr1(frame):
    from evidence import build_evidence
    evidence, journal = build_evidence(frame)
    state, ledger = e0_nr1_policy(evidence)
    return dict(version=VERSION, evidence=evidence, journal=journal,
                state=state, ledger=ledger)
