"""Read-only research dedup and pure Decimal recovery counterexamples.

No strategy/model/Account imports and no financial event execution.
Old economic results below are attributed to their bound saved reports;
this script does not purport to re-audit or replay their original books.
"""
from pathlib import Path
from decimal import Decimal as D, getcontext
import hashlib
import json

getcontext().prec = 60
HERE = Path(__file__).resolve().parent
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
P = Path('/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility')
S = HERE.parent
FILES = [
    W/'c1-drawdown-capacity-20261101/CONTRACT.txt',
    W/'c1-drawdown-capacity-20261101/RESULTS.txt',
    W/'c1-drawdown-capacity-20261101/adapter_c1.py',
    W/'c1-drawdown-capacity-20261101/independent-results-audit/AUDIT_REPORT.txt',
    W/'recovery-2023-readiness-20261101/RUN_CONTRACT.txt',
    W/'recovery-2023-readiness-20261101/RUN_RESULTS.txt',
    P/'SOURCE_AND_DEDUP_READOUT.txt',
    P/'market_phase_2022_2023/READOUT.txt',
    HERE/'NATIVE_ACT_PVR_CONTRACT_REVIEW.json',
    S/'DIAGNOSTIC_SCOPE_FREEZE.json',
    S/'state_semantics/READOUT.txt',
    S/'scale_concentration/results_v3/SUMMARY.json',
]


def fraction(nav, high):
    dd = max(D(0), D(1) - nav/high)
    return max(D(0), D(1) - dd/D('.20'))


def main():
    source_hash = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in FILES}
    contract = FILES[0].read_text()
    code = FILES[2].read_text()
    assert '不随ACT phase恢复重置H' in contract
    assert "D('.10')+D('.50')*max(D(0),D(1)-self.drawdown/D('.20'))" in code
    pure = []
    for nav in map(D, ['800000', '790000', '700000']):
        high = D('1000000')
        g = fraction(nav, high)
        assert g == 0
        # Closed cash-only state: no holdings, no external capital, no pending
        # entitlements, no interest. Multiplying ALL new-risk targets by zero
        # creates no asset exposure, so any market-price sequence cannot move NAV.
        seq = [nav]
        for _ in range(12):
            assert fraction(seq[-1], high) == 0
            seq.append(seq[-1])
        assert len(set(seq)) == 1
        assert fraction(nav, nav) == 1  # a reset changes the policy state
        pure.append(dict(NAV=str(nav), global_H=str(high), g=str(g),
                         flat_zero_exposure_NAV_invariant_12_steps=True,
                         explicit_phase_H_reset_would_change_g_to='1'))

    native = json.loads((HERE/'NATIVE_ACT_PVR_CONTRACT_REVIEW.json').read_text())
    original_resume_examples = []
    for e in native['results']['2022_2024']['episodes']:
        if e.get('resume'):
            nav = D(e['resume_NAV'])
            original_resume_examples.append(dict(
                date=e['resume'], original_NAV=str(nav), assumed_global_H='1000000',
                proposed_g_at_THIS_ORIGINAL_state=str(fraction(nav, D('1000000'))),
                is_candidate_policy_replay=False))
    assert all(D(x['proposed_g_at_THIS_ORIGINAL_state']) == 0 for x in original_resume_examples)
    out = dict(
        status='STOP_GENERIC_DRAWDOWN_FLOW_CANDIDATE_PENDING_NEW_MECHANISM_AND_RECOVERY_CONTRACT',
        scope='Saved-document/source review plus pure Decimal counterexamples; no old or new economic replay.',
        C1_definition=dict(
            formula='c=.10+.50*max(0,1-D/.20)',
            D='max(0,1-actual_decision_CLOSE_NAV/global_CLOSE_high)',
            high_reset_on_ACT_resume=False,
            action='Confirmed total-capital cap in route/request/migration; old positions not forced sold.',
            unaffected='Original probe/core budgets, stock/industry limits, signal, exits, ACT.'),
        old_completed_results_as_reported=dict(
            weak2022=dict(C1_minus_Bdiag_end_NAV='129285.43',
                          Bdiag_return_pct='-33.2676', C1_return_pct='-20.3391'),
            strong=dict(C1_minus_Bdiag_end_NAV='-71164.50',
                        Bdiag_DD_pct='13.1795', C1_DD_pct='13.6038',
                        Bdiag_actual_tail_contribution='822182', C1_actual_tail_contribution='642713'),
            continuous2023=dict(C1_minus_Bdiag_year_wealth_change='-23117.97',
                                Bdiag_return_pct='-.60', C1_return_pct='-3.40',
                                Bdiag_DD_pct='21.15', C1_DD_pct='8.05',
                                Bdiag_average_exposure_pct='38.92', C1_average_exposure_pct='14.94',
                                C1_cap_at_10pct_closes=176, C1_closes=242,
                                C1_max_capacity_pct='18.1673',
                                Bdiag_actual_closed_tail='159812', C1_actual_closed_tail='48413',
                                ACT_resume='2023-01-19', first_actual_core_and_confirmed_buy='2023-01-20')),
        economic_inference=[
            'C1 improves 2022 losses/DD and remains a risk-preference menu; not a mathematical refutation of every drawdown controller.',
            'Its strong-window lower return/higher DD and 2023 smaller recovery participation reject promotion as a universal information-quality improvement.',
            'The current proposed g scales FLOW targets for core and mobile rather than confirmed STOCK capacity, includes different pools, and uses No60 rather than old Bdiag. It is not the same intervention already tested.',
            'These differences do not supply an independent ex-ante failure signal. A large weak-period loss or high observed risk alone does not warrant repeating the same economic shrink family.',
            'Current No60 market stages include both rebound losses at high exposure and positive stock selection during a falling index. Uniform contraction is not a demonstrated repair of selection/recovery.',
            'Static quantity times original layer outcome is not account savings: unit minima, cash, queues, later selection, ACT and inventories change endogenously.'
        ],
        proposed_global_g_counterexample=dict(
            formula='g=max(0,1-D/.20)',
            required_definition='Whether D uses global high, ACT phase high, or an explicit new recovery reset must be frozen before code.',
            blocker='With non-reset global H and ALL core/mobile new-risk targets zero at NAV<=.8H, a flat cash-only state is absorbing. Original ACT resume resets its own peak but does not change global H.',
            pure_examples=pure,
            original_resume_state_examples=original_resume_examples,
            scope_limit='Original-state examples are not the new policy path. Pure invariant excludes new capital, interest and outstanding entitlement revaluation. AR-to-cash payment by itself is not a NAV increase.',
            repairs_are_new_policy='Nonzero floor, phase reset, external seed, target normalization or another restoration rule changes the frozen economic contract; none approved here.'),
        new_evidence_gate=[
            'Specify the target: absolute risk preference versus algorithmic failure discrimination; do not switch after seeing outcomes.',
            'Name new state information and why it separates failures from true winners; current realized drawdown alone is already C1 family.',
            'Prove liveness after full flat, legal-unit starvation, unknown data, ACT reset and fees; preserve pending-order/old-position liabilities.',
            'Freeze action, denominator, CLOSE-to-OPEN clock and resource accounting; finite full-account intervention only after coverage and independent review.'
        ],
        source_sha256=source_hash,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        new_accounts=0, new_financial_events=0, original_or_sealed_files_changed=0)
    (HERE/'C1_DEDUP_AND_RECOVERY_REVIEW.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(status=out['status'], source_files=len(source_hash),
                          pure_counterexamples=len(pure), new_accounts=0), ensure_ascii=False))


if __name__ == '__main__':
    main()
