"""Read-only integrity checks, followed by an exclusive completion manifest."""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, csv

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for part in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()

def read(path):
    return json.loads(path.read_text())

def main():
    verified = {}
    def check_map(label, mapping, base):
        errors = []
        for name, expected in mapping.items():
            path = Path(name)
            if not path.is_absolute():
                path = base / path
            actual = sha(path) if path.is_file() else None
            if actual != expected:
                errors.append(dict(path=str(path), expected=expected, actual=actual))
        assert not errors, (label, errors)
        verified[label] = len(mapping)

    check_map('raw_freeze', read(HERE/'raw-freeze.json')['sha256'], ROOT)
    m = read(HERE/'model-freeze-v1.json')
    check_map('model_sources', m['source_sha256'], ROOT)
    check_map('model_signals', m['signal_files'], HERE)
    check_map('account_freeze', read(HERE/'account-freeze.json')['sha256'], ROOT)
    prior = ROOT/'research_rounds/sector-ix-i-20261026'
    check_map('previous_round_all_artifacts', read(prior/'complete.json')['artifacts'], ROOT)
    check_map('previous_account_freeze', read(prior/'account-freeze-v2.json')['sha256'], ROOT)
    old = ROOT/'research_rounds/rs-h1-execution-20261025'
    oldfreeze = read(old/'freeze.json')
    check_map('legacy_execution_code', oldfreeze['code'], old/'code')
    check_map('legacy_inputs', oldfreeze['inputs'], ROOT)
    check_map('E0_R_R1_registry', read(ROOT/'research_rounds/algorithm-baselines-20261024/registry.json')['sha256'], ROOT)

    audit = read(HERE/'analysis-v1/accounting.json')
    prefix = read(HERE/'technical/prefix-receipt-v1.json')
    assert audit['passed'] and audit['accounts']==28 and audit['daily_rows']==39200
    assert audit['max_absolute_NAV_difference_cny']=='0'
    assert prefix['passed'] and prefix['paths']==14 and prefix['rows']==dict(daily=10178, decisions=10178)
    assert read(HERE/'old-I-identity.json')['passed']
    assert read(HERE/'review-v1/receipt.json')['passed']
    with (HERE/'analysis-v1/summary.csv').open() as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows)==28 and len({r['account'] for r in rows})==28
    for r in rows:
        assert (HERE/'accounts'/(r['account']+'.json')).is_file()
        total = sum(float(r[k]) for k in ['tail_pnl','ordinary_pnl','open_pnl'])
        assert abs(total-(float(r['final_nav'])-1e6)) < 1e-6
    assert len([r for r in rows if r['policy']=='LER' and r['scenario']=='base'])==4
    assert all(float(r['max_drawdown'])>.2 for r in rows if r['policy']=='LER')
    for path in [HERE/'CONCLUSION.md', HERE/'TRADE_REVIEW.md', HERE/'README.md', HERE/'report/index.html']:
        assert path.is_file() and path.stat().st_size>1000
    for folder in ['raw','model-charts-v1']:
        assert len([p for p in (HERE/folder).glob('*.png') if not p.name.startswith('contact')])==12
    assert len(list((HERE/'review-v1').glob('*_tail.png')))==4
    assert len(list((HERE/'review-v1').glob('*_loss.png')))==4

    receipt = dict(passed=True, recorded_at=datetime.now(timezone.utc).isoformat(),
                   hash_checks=verified, total_frozen_file_checks=sum(verified.values()),
                   economic_nav_error_cny='0', economic_paths=28, real_prefix_paths=14,
                   economic_replays_after_results=0, rule_changes_after_results=0)
    with (HERE/'integrity.json').open('x') as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2); handle.write('\n')
    artifacts = {str(p.relative_to(ROOT)):sha(p) for p in sorted(HERE.rglob('*'))
                 if p.is_file() and p.name!='complete.json' and '__pycache__' not in p.parts}
    final = dict(status='complete', recorded_at=datetime.now(timezone.utc).isoformat(),
        adopted_as_default=False, one_candidate='LER-01 v1', new_economic_paths=24,
        old_control_paths=4, valid_economic_paths=28, economic_runs=1, economic_reruns=0,
        post_result_rule_changes=0, stocks=256, raw_windows=12, candidate_windows=12,
        actual_structure_review_cases=8, economic_daily_rows=39200, nav_error_cny='0',
        real_financial_prefix_paths=14, prefix_daily_rows=10178, prefix_decision_rows=10178,
        pure_fact_prefix_paths=12, independent_formula_checks=744,
        failed_technical_attempts_preserved=3, new_market_downloads=0, live_trading=False,
        strict_tail_coverage_base_pools=['COMM'],
        local_report='http://127.0.0.1:8798/report/',
        artifact_count=len(artifacts), artifacts=artifacts)
    with (HERE/'complete.json').open('x') as handle:
        json.dump(final, handle, ensure_ascii=False, indent=2); handle.write('\n')
    print(json.dumps({k:v for k,v in final.items() if k!='artifacts'}, ensure_ascii=False, indent=2))
    print(json.dumps(receipt, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
