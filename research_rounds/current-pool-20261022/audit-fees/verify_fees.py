"""Offline table/boundary checks; not an assertion of complete fee evidence."""
from collections import defaultdict
from datetime import date
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
D = Decimal


def verify():
    data = json.loads((ROOT / 'fees.json').read_text())
    periods = data['periods']
    checks = []

    def check(name, condition):
        if not condition:
            raise AssertionError(name)
        checks.append(name)

    check('no_account_or_algorithm_change', data['account_runs'] == data['algorithm_changes'] == 0)
    check('unfrozen_proposals', data['research_defaults_proposal']['status'] == 'proposal_for_root_freeze_not_already_authorized_execution_policy')
    check('unique_ids', len(periods) == len({x['id'] for x in periods}))
    check('cutoff_is_20261022_inclusive', data['study_end_exclusive'] == '2026-10-23')
    groups = defaultdict(list)
    for p in periods:
        check(p['id'] + ':date_order', date.fromisoformat(p['from_inclusive']) < date.fromisoformat(p['to_exclusive']) <= date.fromisoformat(data['study_end_exclusive']))
        check(p['id'] + ':sources_exist', bool(p['source_ids']) and all(s in data['sources'] for s in p['source_ids']))
        check(p['id'] + ':nonnegative_amounts', D(p['rate_decimal']) >= 0 and D(p['minimum_local']) >= 0 and D(p['fixed_per_transaction_local']) >= 0)
        check(p['id'] + ':bounds', p['maximum_local'] is None or D(p['maximum_local']) >= D(p['minimum_local']))
        check(p['id'] + ':currency_and_date', p['fee_currency'] == ('HKD' if p['market'] == 'HK' else 'CNY') and p['fee_date_basis'] == 'execution_local_trade_date')
        check(p['id'] + ':rounding', (p['rounding_unit'] is None and p['rounding_mode'] is None) or (D(p['rounding_unit']) > 0 and p['rounding_mode'] in ('ceil', 'nearest')))
        venues = ['HK'] if p['market'] == 'HK' else p['market'][2:].split('_')
        for venue in venues:
            groups[(venue, p['name'])].append(p)
    for key, items in groups.items():
        ordered = sorted(items, key=lambda p: p['from_inclusive'])
        check(str(key) + ':no_overlap', all(a['to_exclusive'] <= b['from_inclusive'] for a, b in zip(ordered, ordered[1:])))
    gaps = {x['id']: x for x in data['gaps']}
    check('southbound_unknown_not_zero', data['holding_fee_periods'] == [] and gaps['southbound_portfolio']['rate_decimal'] is None)
    check('northbound_not_used_as_fee_source', all('northbound_not_southbound' not in p['source_ids'] for p in periods))
    check('all_sources_authorized_official_domains', all(__import__('urllib.parse', fromlist=['urlparse']).urlparse(s['url']).hostname.endswith(('.sse.com.cn', '.szse.cn', '.hkex.com.hk')) for s in data['sources'].values()))

    def active(venue, name, at):
        rows = [p for p in groups[(venue, name)] if p['from_inclusive'] <= at < p['to_exclusive']]
        if len(rows) != 1:
            raise AssertionError((venue, name, at, len(rows)))
        return rows[0]

    def amount(p, notional='100000', shares=None, par=None):
        if p['amount_basis'] == 'traded_shares_times_actual_par_value':
            if shares is None or par is None:
                raise ValueError('Face-value fee requires explicit shares and par')
            basis = D(shares) * D(par)
        elif p['amount_basis'] == 'per_exchange_transaction':
            basis = D(0)
        else:
            basis = D(notional)
        fee = max(D(p['minimum_local']), basis * D(p['rate_decimal']) + D(p['fixed_per_transaction_local']))
        if p['maximum_local'] is not None:
            fee = min(D(p['maximum_local']), fee)
        if p['rounding_unit']:
            unit = D(p['rounding_unit'])
            fee = (fee / unit).quantize(D(1), rounding=ROUND_CEILING if p['rounding_mode'] == 'ceil' else ROUND_HALF_UP) * unit
        return fee

    def total(venue, at, side, notional='100000'):
        return sum((amount(active(venue, name, at), notional) for v, name in groups if v == venue and active(venue, name, at)['side'] in ('both', side)), D(0))

    check('A_sell_20230827', total('SZ', '2023-08-27', 'sell') == D('107.87'))
    check('A_sell_20230828', total('SZ', '2023-08-28', 'sell') == D('56.41'))
    check('A_buy_20230828_no_stamp', total('SZ', '2023-08-28', 'buy') == D('6.41'))
    check('HK_2022_100k', total('HK', '2022-07-01', 'buy') == D('140.35'))
    check('HK_2023_trade_fee_change', total('HK', '2023-01-03', 'buy') == D('140.50'))
    check('HK_2023_stamp_change', total('HK', '2023-11-17', 'buy') == D('110.50'))
    check('HK_2025_settlement_change', total('HK', '2025-06-30', 'buy') == D('112.70'))
    check('HK_old_settlement_minimum', amount(active('HK', 'stock_settlement', '2025-06-27'), '1000') == D('2'))
    check('HK_old_settlement_maximum', amount(active('HK', 'stock_settlement', '2025-06-27'), '10000000') == D('100'))
    check('HK_new_settlement_no_cap', amount(active('HK', 'stock_settlement', '2025-06-30'), '10000000') == D('420'))
    check('HK_stamp_round_up', amount(active('HK', 'stamp_duty', '2025-06-30'), '1000.01') == D('2'))
    check('HK_sfc_nearest_cent', amount(active('HK', 'sfc_levy', '2025-06-30'), '1000') == D('0.03'))
    sh_old = active('SH', 'transfer', '2015-07-31')
    check('SH_old_face_value_not_turnover', amount(sh_old, '100000', shares='10000', par='1') == D('3'))
    try:
        amount(sh_old, '100000')
        raise AssertionError('missing face value must fail')
    except ValueError:
        checks.append('SH_old_unknown_face_value_rejected')
    for source in json.loads((ROOT / 'source-manifest.json').read_text()):
        p = ROOT / source['path']
        check(source['path'] + ':hash', p.stat().st_size == source['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest() == source['sha256'])
    artifacts = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(ROOT.iterdir()) if p.is_file() and p.name not in ('verification.json',)}
    return dict(status='pass', check_count=len(checks), periods=len(periods), sources=len(data['sources']), gaps=len(gaps), account_runs=0, algorithm_changes=0, checks=checks, artifacts_sha256=artifacts, limitation='Offline structural and boundary checks only. No assertion of complete historical fee chain, retail pass-through or executable account readiness.')


if __name__ == '__main__':
    result = verify()
    with (ROOT / 'verification.json').open('x') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(json.dumps({k: result[k] for k in ('status', 'check_count', 'periods', 'sources', 'gaps', 'account_runs', 'algorithm_changes')}, ensure_ascii=False))
