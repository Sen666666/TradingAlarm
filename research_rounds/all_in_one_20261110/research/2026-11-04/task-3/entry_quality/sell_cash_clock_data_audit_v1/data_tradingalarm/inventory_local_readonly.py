"""Bounded local inventory only. No service, credential, model or account access."""
from pathlib import Path
import collections, hashlib, json
import pyarrow.parquet as pq

O = Path(__file__).resolve().parent
REPO = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
APP = Path('/Users/bytedance/Documents/ChatGPT/money/TradingAlarm')
MONEY = APP.parent
LATEST = APP/'runtime/market/update-20261104-153015-646272/prepared'


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())


def main():
    bound = {}
    def bind(p):
        bound[str(p)] = sha(p)
        return p

    market_path = bind(APP/'data/market.json')
    market = read(market_path)
    repo_market = bind(REPO/'TradingAlarm/data/market.json')
    assert sha(repo_market) == sha(market_path)
    intraday = []
    for s in market['stocks']:
        pts = s.get('intraday', [])
        if not pts: continue
        intraday.append({'symbol': s['symbol'], 'rows': len(pts), 'dates': sorted({p['date'] for p in pts}),
                         'first': {'date': pts[0]['date'], 'time': pts[0]['time']},
                         'last': {'date': pts[-1]['date'], 'time': pts[-1]['time']},
                         'missing_volume_rows': sum(p.get('volume') is None for p in pts),
                         'missing_amount_rows': sum(p.get('amount') is None for p in pts),
                         'fields': sorted({k for p in pts for k in p}),
                         'capturedAt_label': s.get('capturedAt')})
    manifest_path = bind(LATEST/'manifest.json')
    manifest = read(manifest_path)
    runtime_samples = []
    for sid in ['002583.SZ', '000620.SZ', '688146.SH', 'URFI881121']:
        p = bind(LATEST/'bars'/f'{sid}.parquet')
        pf = pq.ParquetFile(p)
        dates = pq.read_table(p, columns=['trade_date', 'observed_at']).to_pandas()
        nonempty = dates.observed_at.fillna('').ne('')
        runtime_samples.append({'sid': sid, 'path': str(p), 'rows': pf.metadata.num_rows,
                                'schema': [{'name': f.name, 'type': str(f.type)} for f in pf.schema_arrow],
                                'min_date': str(dates.trade_date.min()), 'max_date': str(dates.trade_date.max()),
                                'blank_observed_at': int((~nonempty).sum()), 'nonblank_observed_at': int(nonempty.sum()),
                                'last_nonblank_values': dates.loc[nonempty, 'observed_at'].tail(3).tolist()})
    actions, action_status, action_fields = [], collections.Counter(), set()
    action_files = sorted((LATEST/'actions').glob('*.json'))
    for p in action_files:
        x = read(p); action_status[x['status']] += 1
        actions.extend(x['events'])
        for e in x['events']: action_fields.update(e)
    paper_batches, paper_symbols, paper_dates, receipts = [], set(), [], []
    qroot = APP/'runtime/paper-quotes'
    for d in sorted(x for x in qroot.iterdir() if x.is_dir()):
        protocol = read(bind(d/'protocol.json'))
        histories = []
        for p in sorted((d/'history').glob('*.json')):
            x = read(p); bars = x.get('bars', [])
            paper_symbols.add(x['symbol']); paper_dates.extend(b['date'] for b in bars)
            histories.append({'path': str(p), 'symbol': x['symbol'], 'rows': len(bars),
                              'date_min': min((b['date'] for b in bars), default=None),
                              'date_max': max((b['date'] for b in bars), default=None),
                              'fields': sorted({k for b in bars for k in b}), 'source': x.get('source')})
        for p in sorted((d/'pages').glob('*/*/*/receipt.json')):
            x = read(p)
            receipts.append({'path': str(p), 'received_at': x.get('received_at'), 'recovered_at': x.get('recovered_at')})
        paper_batches.append({'path': str(d), 'history_count': len(histories), 'histories': histories,
                              'protocol_item_count': len(protocol.get('items', []))})
    receipt_example = next(x for x in receipts if x['received_at'] is not None)
    bind(Path(receipt_example['path']))
    rd = REPO/'TradingAlarm/research/data'
    feature_manifest = read(bind(rd/'stock-features/manifest.json'))
    feature_path = bind(rd/'stock-features/local-features.parquet')
    feature_footer = pq.ParquetFile(feature_path)
    master = read(bind(rd/'baostock-master.json'))
    ca_example = read(bind(rd/'ths-actions-688008.json'))
    meta_paths = [REPO/'docs/catalog.json', REPO/'docs/DATA_SOURCES.md', REPO/'docs/SECURITY.md',
                  REPO/'docs/HANDOFF.md', APP/'README.md', APP/'market.py', APP/'build_data.py',
                  APP/'desk/refresh.py', APP/'desk/paper_quotes.py',
                  MONEY/'research_rounds/current-pool-20261022/code/history_batch.py',
                  rd/'forward-observation/README.md', rd/'forward-observation/protocol.json']
    for p in meta_paths: bind(p)
    rules_path = bind(MONEY/'research_rounds/pvr-act-comparison-20261027/execution-rules-v2.json')
    rules = read(rules_path)
    schema_keys = set()
    def keys(x):
        if isinstance(x, dict):
            schema_keys.update(x)
            for v in x.values(): keys(v)
        elif isinstance(x, list):
            for v in x: keys(v)
    keys(rules)
    absent = sorted(k for k in schema_keys if any(s in k.lower() for s in ['limit', 'halt', 'suspend', 'tick', 'is_st', 'risk_warning']))
    current_path = bind(APP/'runtime/market/current.json')
    current = read(current_path)
    found = {'app_capture': {'paths': [str(market_path), str(repo_market)], 'identical_bytes': True,
                            'source': market['source'], 'capture_label': market['capturedAt'],
                            'stock_roster_count': len(market['stocks']),
                            'nonempty_quote_records': sum(bool(s.get('quote')) for s in market['stocks']),
                            'quote_field_ids': sorted({k for s in market['stocks'] for k in s.get('quote', {})}),
                            'quote_semantics': 'numeric field snapshots; bid/ask/depth mapping NOT_VERIFIED',
                            'intraday_symbols': len(intraday), 'intraday_rows': sum(x['rows'] for x in intraday),
                            'intraday': intraday, 'decodeSkipped': market['decodeSkipped']},
             'latest_runtime': {'root': str(LATEST), 'manifest_path': str(manifest_path),
                                'kind_counts': dict(collections.Counter(s['kind'] for s in manifest['series'])),
                                'coverage_last_counts': dict(collections.Counter(str(x.get('last')) for x in manifest['coverage'])),
                                'file_counts': {d: len(list((LATEST/d).glob('*.json' if d == 'actions' else '*.parquet'))) for d in ['bars','facts','signals','actions']},
                                'sample_footers_and_times': runtime_samples, 'current_publication': current},
             'CA': {'files': len(action_files), 'events': len(actions), 'status_counts': dict(action_status),
                    'effective_min': min(x['effective_date'] for x in actions), 'effective_max': max(x['effective_date'] for x in actions),
                    'paid_at_known': sum(bool(x.get('paid_at')) for x in actions),
                    'new_shares_sellable_at_known': sum(bool(x.get('new_shares_sellable_at')) for x in actions),
                    'event_schema': sorted(action_fields), 'sample_688008_announcement_date_rows': len(ca_example.get('rows', [])),
                    'sample_688008_fields': sorted({k for x in ca_example.get('events', []) for k in x})},
             'paper_quote_named_batches': {'root': str(qroot), 'batch_count': len(paper_batches), 'symbols': sorted(paper_symbols),
                                           'bar_min': min(paper_dates), 'bar_max': max(paper_dates), 'batches': paper_batches,
                                           'receipt_count': len(receipts), 'received_at_nonnull': sum(bool(x['received_at']) for x in receipts),
                                           'recovered_only_count': sum(x['received_at'] is None and bool(x['recovered_at']) for x in receipts),
                                           'example_packet_receipt': receipt_example,
                                           'frequency': 'id210 period16384 daily OHLCV; same-day morning bar may still be in progress'},
             'derived_stock_features': {'path': str(feature_path), 'rows_footer': feature_footer.metadata.num_rows,
                                        'symbols_manifest': feature_manifest['symbols'], 'schema': feature_footer.schema_arrow.names,
                                        'source_manifest': feature_manifest['source'], 'limitations': feature_manifest['limitations']},
             'baostock_master': {'rows': len(master['rows']), 'row_schema': sorted(master['rows'][0]), 'status': 'snapshot; not historical ST/suspension timeline'}}
    out = {'status': 'BOUNDED_LOCAL_DATA_INVENTORY_COMPLETE_NO_NETWORK', 'found': found,
           'not_found_within_inspected_scope': ['verified multi-year broad minute/tick/depth history covering original No60 dates',
                                               'per-event exchange publication and receive timestamps for app normalized minute points',
                                               'historical ST/halt/true daily limit/tick fields in current execution rules',
                                               'broker/exchange order arrival/fill/cancel ACK dataset', 'explicit third-party redistribution/commercial data license'],
           'unverified_or_not_examined': ['numeric quote field IDs may include bid/ask/depth but mapping not verified',
                                        'private/credential/authentication captures and settings excluded', 'other unlisted source trees and raw binary bodies not exhaustively examined',
                                        'no global assertion that this machine has no other intraday source'],
           'rules_relevant_key_hits': absent,
           'time_semantics': {'packet_receipt_received_at': 'local wallclock after matching response and writing raw body, before decode (history_batch.py:202-208); not exchange event/publication time',
                              'recovered_at': 'recovery time; received_at explicitly missing, cannot backfill receive',
                              'runtime_observed_at': 'normalization/ingestion now (desk/refresh.py:143-148), not per-bar exchange receive/publication',
                              'runtime_published_at': 'local prepared snapshot publication, not historical market publication',
                              'app_capturedAt': 'hardcoded approximate batch/default labels (build_data.py:13-14,59,63)',
                              'bar_minute_timestamp': 'decoded provider minute label, not receive time; no subseconds/queue/order chronology'},
           'permission': {'local_user_readonly_client_authorization': 'documented in README/docs for original named services; no service accessed in this audit',
                          'provider_license_or_redistribution_right': 'UNKNOWN_NO_EXPLICIT_GRANT_IN_INSPECTED_METADATA',
                          'legal_guarantee': False},
           'source_sha256': bound, 'scope': 'Known roots and fixed manifests only; no unbounded whole-disk traversal',
           'network_calls': 0, 'credential_files_read': 0, 'new_models_accounts_or_backtests': 0, 'source_data_modified': False}
    (O/'INVENTORY.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps({'status': out['status'], 'minute_symbols': len(intraday), 'minute_rows': sum(x['rows'] for x in intraday),
                      'paper_daily_symbols': len(paper_symbols), 'packet_receipts': len(receipts), 'CA_events': len(actions), 'bound_files': len(bound)}))


if __name__ == '__main__': main()
