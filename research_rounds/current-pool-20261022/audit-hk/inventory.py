"""Offline HK cache inventory. No network-capable repository imports."""
from pathlib import Path
import csv
import hashlib
import json
import math
from statistics import median

REPO = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
RESEARCH = REPO / 'TradingAlarm/research'
DATA = RESEARCH / 'data'
BATCH = DATA / 'ths-index-history-9603-20261018'
OUT = Path(__file__).resolve().parent
manifest = {}


def stamp(path):
    raw = path.read_bytes()
    manifest[str(path)] = {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
    return raw


def js(path):
    return json.loads(stamp(path))


def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def quality(rows):
    out = {'rows': len(rows), 'price_missing_rows': 0, 'price_nonpositive_rows': 0, 'ohlc_violation_rows': 0,
           'volume_missing_rows': 0, 'volume_zero_rows': 0, 'volume_one_rows': 0, 'amount_missing_rows': 0}
    unit = []
    for r in rows:
        o, h, l, c = [num(r[k]) for k in ['open', 'high', 'low', 'close']]
        v, a = num(r['volume']), num(r.get('amount'))
        out['price_missing_rows'] += any(x is None for x in [o, h, l, c])
        out['price_nonpositive_rows'] += any(x is not None and x <= 0 for x in [o, h, l, c])
        if all(x is not None for x in [o, h, l, c]):
            out['ohlc_violation_rows'] += h < max(o, l, c) or l > min(o, h, c)
        out['volume_missing_rows'] += v is None
        out['volume_zero_rows'] += v == 0
        out['volume_one_rows'] += v == 1
        out['amount_missing_rows'] += a is None
        if all(x is not None and x > 0 for x in [a, v, c]):
            unit.append(a / (v * c))
    out['amount_over_volume_times_close_median'] = median(unit) if unit else None
    return out


protocol = js(BATCH / 'protocol.json')
results = []
for item in protocol['symbols']:
    if item['category'] not in ['hk_stock', 'hk_etf']:
        continue
    symbol = item['symbol']
    cp = js(BATCH / 'checkpoints' / f'{symbol}.json')
    canonical = BATCH / cp['canonical']
    rows = list(csv.DictReader(stamp(canonical).decode().splitlines()))
    raw_hashes = []
    for p in cp['pages']:
        actual = hashlib.sha256(stamp(BATCH / p['file'])).hexdigest()
        raw_hashes.append(actual == p['body_sha256'])
    recent = [r for r in rows if r['date'] >= '2013-01-01']
    tencent_path = RESEARCH / item['tencent_raw']
    tencent = js(tencent_path)
    if 'rows' in tencent:
        tr = tencent['rows']
    else:
        key = next(iter(tencent['data']))
        tr = tencent['data'][key]['day']
    trows = {r[0]: r for r in tr}
    common = [r for r in rows if r['date'] in trows]
    volume_ratios = []
    price_equal = 0
    for r in common:
        ref = trows[r['date']]
        if all(num(r[k]) is not None and abs(float(r[k]) - float(ref[j])) <= .0005 for k, j in [('open', 1), ('close', 2), ('high', 3), ('low', 4)]):
            price_equal += 1
        v, rv = num(r['volume']), num(ref[5])
        if v is not None and rv is not None and rv > 0:
            volume_ratios.append(v / rv)
    results.append({'symbol': symbol, 'name': item['name'], 'category': item['category'], 'canonical_path': str(canonical),
                    'first': rows[0]['date'], 'last': rows[-1]['date'], 'pages': len(cp['pages']), 'checkpoint_status': cp['status'],
                    'stop_reason': cp['stop_reason'], 'rows_dropped_by_parser': cp['rows_dropped_by_parser'],
                    'page_overlap_conflicts': len(cp['overlap_conflicts']), 'canonical_hash_verified': hashlib.sha256(canonical.read_bytes()).hexdigest() == cp['canonical_sha256'],
                    'raw_page_hashes_verified': all(raw_hashes), 'duplicate_dates': len(rows) - len({r['date'] for r in rows}),
                    'full_history_quality': quality(rows), 'from_2013_quality': quality(recent),
                    'rights_in_original_batch': (BATCH / 'rights' / f'{symbol}.json').exists(),
                    'reference': {'path': str(tencent_path), 'rows': len(tr), 'first': min(trows), 'last': max(trows),
                                  'overlap_rows': len(common), 'all_four_prices_within_half_millitick_rows': price_equal,
                                  'ths_volume_over_tencent_median': median(volume_ratios) if volume_ratios else None,
                                  'reference_complete_flag': tencent.get('complete'), 'reference_stop_reason': tencent.get('stop_reason'),
                                  'rows_with_extra_fields': sum(len(r) > 6 for r in tr)},
                    'first_query': cp['pages'][0]['query'], 'last_query': cp['pages'][-1]['query']})

probe_path = REPO / 'reports/backtest-review-20261021/ths-probe.json'
probe = js(probe_path)
latest = []
for n in probe['nodes']:
    if not n['symbol'].startswith('UHK'):
        continue
    for q in n['queries']:
        raw_path = probe_path.parent / q['response_file']
        assert hashlib.sha256(stamp(raw_path)).hexdigest() == q['response_sha256']
        latest.append({'symbol': n['symbol'], 'kind': q['query']['id'], 'source': str(probe_path), 'query': q['query'],
                       'rows': q['decoded_rows'], 'first': q.get('first'), 'last': q.get('last'),
                       'rights_date_min': min(str(x['1']) for x in q['records']) if q['query']['id'] == 211 else None,
                       'rights_date_max': max(str(x['1']) for x in q['records']) if q['query']['id'] == 211 else None,
                       'raw_hash_verified': True})
for name in ['ths_readonly_fu.py', 'ths_readonly.py', 'fetch_ths_9603_history.py', 'fetch_history.py', 'market.py', 'stock_actions.py', 'ths_signal_adjustment.py']:
    path = RESEARCH / name if name != 'market.py' else RESEARCH.parent / name
    stamp(path)

summary = {'as_of_requested': '2026-10-22', 'offline_only': True, 'network_requests': 0, 'account_runs': 0, 'algorithm_changes': 0,
           'source_scope': 'explicit HK stock/ETF canonical cache in 9603 batch plus existing Tencent references and 2026-10-21 probe; not current HK whole-pool coverage',
           'stocks': len([r for r in results if r['category'] == 'hk_stock']),
           'stock_rows': sum(r['full_history_quality']['rows'] for r in results if r['category'] == 'hk_stock'),
           'stock_rows_from_2013': sum(r['from_2013_quality']['rows'] for r in results if r['category'] == 'hk_stock'),
           'etfs': len([r for r in results if r['category'] == 'hk_etf']), 'all_raw_hashes_match': all(r['raw_page_hashes_verified'] for r in results),
           'all_canonical_hashes_match': all(r['canonical_hash_verified'] for r in results),
           'existing_latest_probe': latest, 'symbols': results}
(OUT / 'cache-inventory.json').open('x').write(json.dumps(summary, ensure_ascii=False, indent=2) + '\n')
(OUT / 'cache-source-manifest.json').open('x').write(json.dumps({'sources': [{'path': p, **v} for p, v in sorted(manifest.items())], 'source_file_count': len(manifest)}, ensure_ascii=False, indent=2) + '\n')
flat = []
for r in results:
    flat.append({k: r[k] for k in ['symbol', 'name', 'category', 'first', 'last', 'pages', 'checkpoint_status', 'stop_reason', 'canonical_hash_verified', 'raw_page_hashes_verified']} | {'rows': r['full_history_quality']['rows']} | {'from_2013_' + k: v for k, v in r['from_2013_quality'].items()})
with (OUT / 'cache-coverage.csv').open('x', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(flat[0])); w.writeheader(); w.writerows(flat)
print(json.dumps({k: v for k, v in summary.items() if k != 'symbols'}, ensure_ascii=False, indent=2))
