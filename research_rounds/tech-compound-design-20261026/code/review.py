"""Read-only review of existing accounts and a proposed technology roster.

No new account, trading decision, price download, or economic replay.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv
import hashlib
import json
from collections import Counter, defaultdict

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
CORE = ['半导体', '元件', '光学光电子', '其他电子', '消费电子', '电子化学品',
        '计算机设备', '软件开发', 'IT服务', '通信设备', '通信服务']

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def write(name, obj):
    with (HERE / name).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')

def main():
    selection = ROOT / 'research_rounds/a-share-selection-e0-20261024/inputs-v2/selection.json'
    master = ROOT / 'research_rounds/current-pool-20261022/audit-snapshot/current-stock-master.industry-resolved.csv'
    old_curves = ROOT / 'research_rounds/sector-ix-i-20261026/analysis-v2/curves.csv'
    ema_curves = ROOT / 'research_rounds/ema-gate-e0-i-20261026/analysis/curves.csv'
    meta = {r['symbol']: r for r in csv.DictReader(master.open())}
    selected = json.loads(selection.read_text())
    counts = Counter(); pool = []; unknown = []
    for r in selected['lines']:
        m = meta[r['security_id']]
        if r['sector_id'] is None or r['company_cap_cny'] is None:
            unknown.append(dict(r, name=m['name'], industry=m['industry_name']))
            continue
        if m['industry_name'] in CORE:
            assert r['company_cap_cny'] > 1e10
            pool.append(dict(symbol=r['security_id'], name=m['name'], industry=m['industry_name'],
                             sector_id=r['sector_id'], current_cap_cny=r['company_cap_cny']))
            counts[m['industry_name']] += 1
    assert len(pool) == 407 and len(counts) == 11 and len(unknown) == 2
    pool.sort(key=lambda x: (CORE.index(x['industry']), x['symbol']))
    with (HERE / 'proposed-pool.csv').open('x') as f:
        w = csv.DictWriter(f, fieldnames=list(pool[0])); w.writeheader(); w.writerows(pool)
    write('scope-proposal.json', dict(status='design_only', user_requested_scope='科技股；2024年至今；有限资金与复利',
          operational_scope='proposed core electronics/computer/communication; not user-specified exact industries',
          industries=[dict(industry=k, stocks=counts[k]) for k in CORE], eligible_stocks=len(pool),
          cap_rule='existing current company cap > CNY10bn', snapshot_id=selected['snapshot_id'],
          omitted_unknowns_retained=unknown, prices_currently_end='2026-10-22',
          comparison_account_end='2026-10-16', new_economic_accounts=0))
    groups = defaultdict(list)
    for path in [old_curves, ema_curves]:
        for r in csv.DictReader(path.open()):
            if r['group'] not in ['SEMI', 'COMM']: continue
            if path == old_curves:
                if r['policy'] != 'IX': continue
            elif r['scenario'] != 'base' or r['policy'] not in ['E0', 'I', 'E0G', 'IG']: continue
            groups[(r['group'], r['policy'])].append(r)
    result = []
    for (g, policy), rs in sorted(groups.items()):
        before = [r for r in rs if r['date'] < '2024-01-01']
        after = [r for r in rs if r['date'] >= '2024-01-01']
        n0 = float(before[-1]['nav']); peak = n0; dd = 0
        assert before[-1]['date'] == '2023-12-29' and after[-1]['date'] == '2026-10-16'
        for r in after:
            n = float(r['nav']); peak = max(peak, n); dd = max(dd, 1-n/peak)
        result.append(dict(group=g, policy=policy, base_date=before[-1]['date'], base_nav=n0,
                           first_date=after[0]['date'], end_date=after[-1]['date'],
                           end_nav=float(after[-1]['nav']), period_return=float(after[-1]['nav'])/n0-1,
                           period_drawdown=dd, inherited_positions=True,
                           interpretation='existing 2021 account slice, not a fresh 2024 cash account'))
    with (HERE / 'existing-account-2024-slices.csv').open('x') as f:
        w = csv.DictWriter(f, fieldnames=list(result[0])); w.writeheader(); w.writerows(result)
    # Independent endpoint check: compound the already-published annual returns.
    annual_paths = [ROOT/'research_rounds/sector-ix-i-20261026/analysis-v2/annual.csv',
                    ROOT/'research_rounds/ema-gate-e0-i-20261026/analysis/annual.csv']
    annual = defaultdict(list)
    for path in annual_paths:
        for r in csv.DictReader(path.open()):
            if r['group'] not in ['SEMI', 'COMM'] or int(r['year']) < 2024: continue
            if path == annual_paths[0]:
                if r['policy'] != 'IX': continue
            elif r['scenario'] != 'base' or r['policy'] not in ['E0', 'I', 'E0G', 'IG']: continue
            annual[(r['group'], r['policy'])].append(float(r['net_return']))
    for r in result:
        product = 1.0
        for a in annual[(r['group'], r['policy'])]: product *= 1+a
        assert abs(product-1-r['period_return']) < 1e-11
    dependencies = [selection, master, old_curves, ema_curves, *annual_paths,
                    ROOT/'research_rounds/sector-ix-i-20261026/CONCLUSION.md',
                    ROOT/'research_rounds/temperature-sizing-20261026/CONCLUSION.md',
                    ROOT/'research_rounds/unlimited-capital-20261026/CONCLUSION.md',
                    ROOT/'research_rounds/selection-rotation-abcd-20261025/CONCLUSION.md',
                    ROOT/'research_rounds/budget-ownership-isolation-20261025/CONCLUSION.md',
                    ROOT/'research_rounds/ema-gate-e0-i-20261026/CONCLUSION.md',
                    ROOT/'research_rounds/entry-risk-holding-review-20261026/CANDIDATE_I_RB1.md',
                    ROOT/'research_rounds/rs-h1-execution-20261025/code/sector_account.py']
    write('review-receipt.json', dict(recorded_at=datetime.now(timezone.utc).isoformat(),
          passed=True, new_economic_accounts=0, downloads=0, existing_paths_sliced=len(result),
          independently_compounded_annual_endpoints=True,
          input_sha256={str(p.relative_to(ROOT)):sha(p) for p in dependencies},
          output_sha256={n:sha(HERE/n) for n in ['scope-proposal.json','proposed-pool.csv','existing-account-2024-slices.csv']},
          limits='All history already seen; slices inherit positions and earlier capital paths; pool is current snapshot.'))
    print(json.dumps(dict(proposed_stocks=len(pool), industries=counts, existing_path_slices=len(result),
                         annual_endpoint_checks='passed', new_economic_accounts=0), ensure_ascii=False))

if __name__ == '__main__': main()
