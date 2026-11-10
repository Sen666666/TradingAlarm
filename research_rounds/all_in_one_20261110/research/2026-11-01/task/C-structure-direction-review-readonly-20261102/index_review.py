"""Index existing read-only evidence. No financial engine imports or replay."""
from pathlib import Path
from decimal import Decimal
import hashlib
import json

HERE = Path(__file__).resolve().parent
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
LOCAL = HERE.parent
AUG = W / 'g-s-C-August-continuation-v1-20261102'
PVR = W / 'pvr-slot1-native-readiness-20261101'
CAUSAL = Path('/tmp/August-four-arm-independent-20261102/C20_Aug25_CAUSAL_CASE.json')

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')

sources = [
    AUG / 'REPORT.txt',
    AUG / 'analysis/C10-ACTUAL_FUNDING_FLOWS.json',
    AUG / 'analysis/C20-AUG25-SOLD_WITHOUT_ORIGINAL_TARGET_BUY.json',
    AUG / 'analysis/C10-ACTUAL_CHAINS.json',
    AUG / 'analysis/C20-ACTUAL_CHAINS.json',
    AUG / 'august_runtime.py',
    AUG / 'AUTHORIZATION.json',
    W / 'g-s-C-industry-first-target-design-20261102/CONTRACT_PROPOSAL.txt',
    W / 'g-s-C-industry-first-projection-v1-20261102/c_selector.py',
    W / 'g-s-C-batch20-projection-r2-20261102/c_batch20.py',
    W / 'g-s-C-native-synthetic-v1-20261102/native_c.py',
    W / 'g-s-historical-native-prefix-20261101/native_capital.py',
    W / 'g-s-C-approved-risk-execution-readonly-20261102/REPORT.txt',
    PVR / 'semiconductor-2026H1-readonly/analysis-wording-errata-v1/CORE_READOUT.txt',
    PVR / 'continuation-2023-readiness/causal-capital-clock-errata-v1/ROOT_READOUT.txt',
    LOCAL / 'PVR-vs-C-July-entry-pool-errata-20261102/REPORT.txt',
    LOCAL / 'C-2022-month-difference-readonly-20261102/REPORT.txt',
    Path('/tmp/August-C10-limited-readonly-20261102/FINAL_READOUT.json'),
    CAUSAL,
]
assert len(sources) == len(set(sources)) and all(p.is_file() for p in sources)
before = {str(p): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sources}
save(HERE / 'SOURCE_SHA256.json', {'scope': 'read-only citations, not a new financial freeze', 'sources': before})

c = json.loads(CAUSAL.read_text())
assert c['positive_Q'] == {'600536.SH': 1800, '002065.SZ': 3900}
assert len(c['donors']) == 5 and len(c['D']) == 4
assert Decimal(c['open_existing_risk_before_new_buy']) > Decimal(c['open_account_risk6_limit_before_new_fee'])
assert Decimal(c['open_vs_close_after_D_risk_increase']).quantize(Decimal('.01')) == Decimal('11728.24')
advance = c['remaining_layer_risk_changes'][:3]
assert [(x['sid'], Decimal(x['risk_delta']).quantize(Decimal('.01'))) for x in advance] == [
    ('002518.SZ', Decimal('7028.00')), ('002281.SZ', Decimal('1920.00')), ('002230.SZ', Decimal('1482.00'))]
assert all(x['close_floor'] == x['open_floor'] for x in advance)
flow = json.loads((AUG / 'analysis/C10-ACTUAL_FUNDING_FLOWS.json').read_text())
matched = []
for day, sid, qty in [('2025-08-13', '600410.SH', 6800), ('2025-08-20', '300870.SZ', 400)]:
    rows = [r for r in flow['rows'] if r['original_plan_at'].startswith(day)
            and any(x['sid'] == sid and x['shares'] == qty for x in r['source_sales'])]
    assert len(rows) == 1
    r = rows[0]
    matched.append({k: r[k] for k in ('original_plan_at', 'certificate', 'source_exit_order',
        'source_sales', 'actual_source_net', 'planned_target_quantities')})

report = (HERE / 'REPORT.txt').read_text()
assert report.count('候选1（') == 1 and report.count('候选2（') == 1
assert all(s in report for s in ['旧PVR是重要冻结参照', '不捏造后来成交', '不是实盘认证',
    '市场资格', '不能把该11,728.24全称纯利润回吐', '不等于新机会更好'])
after = {str(p): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sources}
assert before == after
save(HERE / 'REVIEW_CHECKS.json', {
    'scope': 'source/quotation checks only; not strategy tests or account simulation',
    'financial_events': 0, 'account_imports': 0, 'candidate_implementations': 0,
    'new_indicators': 0, 'new_market_downloads': 0, 'parameter_searches': 0,
    'sources_verified': len(sources), 'sources_unchanged_during_indexing': before == after,
    'fixed_funding_evidence': matched,
    'Aug25_risk_feedback': {k: c[k] for k in ['positive_Q', 'D',
        'close_conditional_existing_risk_after_all_D', 'open_existing_risk_before_new_buy',
        'open_account_risk6_limit_before_new_fee', 'open_existing_risk_excess',
        'open_vs_close_after_D_risk_increase', 'conclusion']},
    'Aug25_top3_mark_changes': advance,
    'two_candidates_only': True, 'passed': True,
    'remaining_unknowns': [
        'No causal profit-versus-principal risk decomposition at every rejected-opportunity cursor.',
        'No counterfactual return for retention or capacity changes.',
        'No validated common expected-return ranking for healthy HOLD versus new BUY.',
        'Risk-budget objective after any decomposition is not authorized or frozen.',
    ]})
deliverables = ['REPORT.txt', 'index_review.py', 'SOURCE_SHA256.json', 'REVIEW_CHECKS.json']
save(HERE / 'DELIVERY_SHA256.json', {name: sha(HERE / name) for name in deliverables})
print(json.dumps({'passed': True, 'sources': len(sources), 'financial_events': 0,
    'report_sha256': sha(HERE / 'REPORT.txt'), 'directory': str(HERE)}, ensure_ascii=False))
