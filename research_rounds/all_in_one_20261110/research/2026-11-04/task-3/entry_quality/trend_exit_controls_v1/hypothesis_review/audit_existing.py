"""Read existing research only; no market feature/model/account imports."""
from pathlib import Path
from collections import Counter
import datetime
import hashlib
import json

OUT = Path(__file__).resolve().parent
ROOT = OUT.parent
LEGACY = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds')
WORK = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
REPO = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
MEAN = REPO/'TradingAlarm/research/results/strength-mean-distance'

def read(path):
    return json.loads(path.read_text())

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

sources = [
    ROOT/'PROTOCOL.txt',
    MEAN/'protocol.json', MEAN/'decision.json', MEAN/'results.json',
    MEAN/'phase-review.json',
    LEGACY/'ema-gate-e0-i-20261026/CONCLUSION.md',
    LEGACY/'pv-structure-context-20261020/README.md',
    LEGACY/'pv-structure-context-20261020/code/context_model.py',
    LEGACY/'video-ema-a-share-20261026/RUN_STATE.json',
    LEGACY/'cp1-cross-sector-20261028/CONCLUSION.txt',
    LEGACY/'ph1-cross-sector-20261028/CONCLUSION.txt',
    LEGACY/'exit-posture-20261024/README.md',
    LEGACY/'semiconductor-exit-20261024/README.md',
    LEGACY/'market-regimes-exit-20261024/README.md',
    LEGACY/'b5-g1-20261025/code/policies_g1.py',
    LEGACY/'continuous-protection-lines-20261028/code/model.py',
    WORK/'case-stage-ledger-20261031/v3/joint_v3.py',
    WORK/'g1-current-state-readonly-20261101/READOUT.txt',
    ROOT/'execution_review/2022_2024_I_EXIT_BOUNDARIES.json',
    ROOT/'execution_review/strong_I_EXIT_BOUNDARIES.json',
    ROOT/'execution_review/VALIDATION.json',
]
evidence = {
    'status': 'EARLY_DESIGN_REVIEWED_GRACE_STOPPED_NO_SOFT_SCOPE',
    'old_mean_distance_protocol': read(MEAN/'protocol.json'),
    'old_mean_distance_decision': read(MEAN/'decision.json'),
    'old_mean_distance_results': [
        {k:r[k] for k in ['case','total_return','max_drawdown','fees','orders']}
        for r in read(MEAN/'results.json') if r['strategy'].startswith('mean_distance')
    ],
    'I_actual_exit_necessary_scope': {},
    'new_market_features': 0, 'new_models': 0, 'new_accounts': 0,
    'warning': 'Terminal I-exit layer membership is original-path coverage, not all first held/Ioff events or causal policy profit.',
}
for name in ['2022_2024', 'strong']:
    rows = read(ROOT/'execution_review'/f'{name}_I_EXIT_BOUNDARIES.json')
    groups = {'all_I_exit_layers': rows}
    if name == '2022_2024':
        groups['opened_2022_2023'] = [r for r in rows if r['opened'][:4] in ('2022','2023')]
        groups['opened_after_2024_10_08'] = [r for r in rows if r['opened'][:10] > '2024-10-08']
    for group, selected in groups.items():
        entry = dict(layers=len(selected),
                     I_floor_broken=sum(r['I_floor_broken'] is True for r in selected),
                     previous_active_I_same_domain=sum(r['previous_active_I_same_domain'] is True for r in selected),
                     hard_boundary_class=dict(Counter(r['hard_boundary_class'] for r in selected)),
                     necessary_grace_scope_preserving_I_floor=sum(r['I_floor_broken'] is not True for r in selected))
        assert entry['layers'] == entry['I_floor_broken'] == entry['previous_active_I_same_domain']
        assert entry['necessary_grace_scope_preserving_I_floor'] == 0
        evidence['I_actual_exit_necessary_scope'][name+'|'+group] = entry

(OUT/'EVIDENCE.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2)+'\n')
manifest = dict(
    at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    status=evidence['status'], sources={str(p):digest(p) for p in sources},
    deliverables={n:digest(OUT/n) for n in ['REVIEW.md','EVIDENCE.json','audit_existing.py']},
    checks=['literal_original_I_exit_floor_broken_all', 'same_domain_all', 'no_market_or_account_imports'],
    no_op_first_held_Ioff_proof='pending_execution_agent_separate_artifact',
    new_market_features=0, new_models=0, new_accounts=0,
)
(OUT/'SOURCE_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n')
print(json.dumps(dict(status=evidence['status'], coverage=evidence['I_actual_exit_necessary_scope']), ensure_ascii=False))
