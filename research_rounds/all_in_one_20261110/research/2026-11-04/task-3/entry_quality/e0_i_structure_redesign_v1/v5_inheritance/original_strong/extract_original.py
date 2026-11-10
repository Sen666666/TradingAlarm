"""Read stored No60 records only; no strategy imports or account replay."""
from pathlib import Path
from collections import Counter
import gzip
import hashlib
import json
import pandas as pd

ROOT = Path('/Users/bytedance/Documents/Codex/2026-11-04/task-3')
OUT = Path(__file__).resolve().parent
BOOK = ROOT / 'entry_quality/trend_exit_controls_v1/runs/BASELINE/strong/pair/B.json.gz'
DAILY = BOOK.with_name('daily.jsonl.gz')
FACT = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/facts/000711.SZ.parquet')

def read_gz(p):
    with gzip.open(p, 'rt') as f:
        return json.load(f)

def dump(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')

book = read_gz(BOOK)
layers = {x['id']: x for x in book['layers']}
meta = book['metadata']
daily = {}
with gzip.open(DAILY, 'rt') as f:
    for line in f:
        z = json.loads(line)
        daily[z['at'][:10]] = z

events = []
for index, trade in enumerate(book['trades']):
    if trade['side'] != 'sell':
        continue
    parts = [p for p in trade.get('parts', [])
             if meta[str(p['layer'])]['role'] == 'mobile'
             and p.get('reason') == 'CP1_add_protection' and p['shares'] > 0]
    if not parts:
        continue
    sid, at = trade['security_id'], trade['at']
    after = [x for x in daily[at[:10]]['layers'] if x['sid'] == sid and x['qty'] > 0]
    part_checks = []
    for part in parts:
        early = layers[part['layer']]
        root = meta[str(early['id'])]['stock_structure']
        full_exit = early['qty'] == 0 and early['closed'] == at
        later_before = [x for x in layers.values()
                        if x['sid'] == sid and meta[str(x['id'])]['role'] == 'mobile'
                        and early['opened'] < x['opened'] < at
                        and (not x['closed'] or x['closed'] >= at)]
        later_live = [x for x in later_before if not x['closed'] or x['closed'] > at]
        same = [x for x in later_live if meta[str(x['id'])]['stock_structure'] == root]
        part_checks.append({
            'early_layer': early['id'], 'opened': early['opened'], 'stock_structure': root,
            'sold_shares': part['shares'], 'closed': early['closed'],
            'early_fully_closed_at_this_sell': full_exit,
            'later_mobile_present_before_sell': [x['id'] for x in later_before],
            'later_mobile_live_after_sell_any_structure': [x['id'] for x in later_live],
            'later_mobile_live_after_sell_same_structure': [x['id'] for x in same],
            'strict_analog_candidate': full_exit and bool(same),
        })
    events.append({
        'trade_index': index, 'sid': sid, 'at': at, 'receipt_id': trade['receipt_id'],
        'CP_parts': parts, 'checks': part_checks,
        'post_CLOSE_snapshot_at': daily[at[:10]]['at'],
        'post_CLOSE_live_layers': [{k: x.get(k) for k in
                                   ['id', 'role', 'qty', 'opened', 'floor', 'last_core_line', 'stock_structure']}
                                  for x in after],
        'post_CLOSE_class': 'mobile_survives' if any(x['role'] == 'mobile' for x in after)
                            else 'core_only' if after else 'flat',
    })

checks = [c for e in events for c in e['checks']]
summary = {
    'scope': 'Stored original No60 strong account; not a V5 account',
    'snapshot_first': min(x['at'] for x in daily.values()),
    'snapshot_last': max(x['at'] for x in daily.values()),
    'snapshots': len(daily), 'all_layers': len(layers),
    'mobile_layers_by_metadata_role': sum(m['role'] == 'mobile' for m in meta.values()),
    'CP_sell_trade_events': len(events),
    'unique_sid_timestamp_CP_sell_events': len({(e['sid'], e['at']) for e in events}),
    'CP_sell_parts': len(checks),
    'full_early_layer_exit_parts': sum(c['early_fully_closed_at_this_sell'] for c in checks),
    'full_early_layer_exit_parts_with_later_mobile_preexisting': sum(
        c['early_fully_closed_at_this_sell'] and bool(c['later_mobile_present_before_sell']) for c in checks),
    'strict_same_structure_later_mobile_survivors': sum(c['strict_analog_candidate'] for c in checks),
    'later_mobile_survivors_without_structure_filter': sum(
        c['early_fully_closed_at_this_sell'] and bool(c['later_mobile_live_after_sell_any_structure']) for c in checks),
    'post_CLOSE_classes': dict(Counter(e['post_CLOSE_class'] for e in events)),
    'V5_probe_parent_or_authenticated_carrier_witness': 'NOT_SAVED_IN_ORIGINAL_ACCOUNT',
    'original_pool_probe_is_V5_probe_purpose': False,
    'new_accounts': 0, 'new_backtests': 0, 'new_quantities': 0,
    'strategy_imports': 0, 'account_replays': 0,
}
dump('SUMMARY.json', summary)
dump('ALL_ORIGINAL_CP_SELL_CHECKS.json', events)

# Deliberately nonqualifying contrast: all MOBILE exits; only an old CORE remains.
sid = '000711.SZ'
trade_idx = 1516
trade = book['trades'][trade_idx]
assert trade['security_id'] == sid and trade['at'].startswith('2026-03-25')
fact = pd.read_parquet(FACT).loc['2026-03-23':'2026-03-25']
facts = []
for date, row in fact.iterrows():
    facts.append({'day': str(date)[:10], **{k: row[k].item() if hasattr(row[k], 'item') else row[k]
                                         for k in fact.columns}})
analog = {
    'classification': 'CORE_ONLY_CONTRAST_NOT_LATER_ADD_INHERITANCE',
    'sid': sid, 'trade_index': trade_idx, 'sell_trade': trade,
    'facts': facts,
    'snapshots': [{
        'at': daily[day]['at'],
        'layers': [x for x in daily[day]['layers'] if x['sid'] == sid],
        'pending_sells': daily[day]['pending_sells'],
    } for day in ['2026-03-23', '2026-03-24', '2026-03-25']],
    'original_final_layer_records': [x for x in layers.values() if x['id'] in [713, 723, 733, 761, 769]],
    'metadata': {str(i): meta[str(i)] for i in [713, 723, 733, 761, 769]},
    'interpretation': 'I_target is true, but G1 is -3; original I_target is not V3/V5 mature. '
                      'No V5 parent/complete/carrier record exists. Remaining CORE100 alone cannot establish inherited qualification.',
}
dump('CORE_ONLY_CONTRAST_000711.json', analog)
sources = [BOOK, DAILY, FACT, Path(__file__).resolve()]
dump('SOURCE_MANIFEST.json', {'source_sha256': {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},
                              'method': 'Read existing book final layers/metadata/trades and saved daily snapshots; no price or account simulation.'})
print(json.dumps(summary, ensure_ascii=False, indent=2))
