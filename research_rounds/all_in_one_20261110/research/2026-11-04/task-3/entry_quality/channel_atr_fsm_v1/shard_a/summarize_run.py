"""Read completed fixed-run receipts only; no model rerun."""
from pathlib import Path
from collections import Counter
import json
import hashlib

OUT = Path(__file__).resolve().parent
RUN = OUT / 'run_v1'
receipt = json.loads((RUN / 'RUN_RECEIPT.json').read_text())
coverage = json.loads((RUN / 'COVERAGE_ALL_SYMBOLS.json').read_text())
inventory = json.loads((OUT / 'INVENTORY_SUMMARY.json').read_text())
assert receipt['status'] == 'COMPLETE' and receipt['errors'] == 0
assert receipt['symbols_requested'] == 855
assert receipt['symbols_completed'] == 846
assert receipt['symbols_not_applicable'] == 9
assert json.loads((RUN / 'ERRORS.json').read_text()) == []
assert receipt['raw_CP_anchors'] == 24151
periods = {}
for start, end in receipt['periods']:
    period_rows = [p for row in coverage for p in row['periods'] if p['start'] == start and p['end'] == end]
    periods[start + '__' + end] = {
        key: sum(p.get(key, 0) for p in period_rows)
        for key in ['observations', 'raw_CP_anchors', 'channel_seen', 'channel_advance', 'main_exit_events']
    }
statuses = Counter()
for row in coverage:
    statuses.update(row.get('pair_status_counts', {}))
example = json.loads((RUN / '000001_SZ/CP_ANCHOR_PAIRS.json').read_text())[0]
summary = {
    'status': 'ONE_FIXED_RUN_COMPLETE_NO_RETRY',
    'runner_receipt': receipt,
    'periods': periods,
    'pair_status_counts': dict(statuses),
    'inventory_CP_anchor_counts_exact': (
        periods['2022-01-01__2023-12-31']['raw_CP_anchors'] == inventory['periods']['2022_2023']['original_raw_CP_receipts']
        and periods['2024-09-01__2024-12-31']['raw_CP_anchors'] == inventory['periods']['2024_Sep_Dec']['original_raw_CP_receipts']
    ),
    'pair_top_level_schema': list(example),
    'pair_CP_schema': list(example['CP']) if isinstance(example.get('CP'), dict) else None,
    'pair_ATR3_schema': list(example['ATR3']) if isinstance(example.get('ATR3'), dict) else None,
    'original_raw_outputs_not_modified': True,
}
assert summary['inventory_CP_anchor_counts_exact']
(OUT / 'RUN_V1_SUMMARY.json').write_text(json.dumps(summary, indent=2) + '\n')
paths = [RUN / 'RUN_RECEIPT.json', RUN / 'COVERAGE_ALL_SYMBOLS.json', RUN / 'ERRORS.json',
         OUT / 'RUN_V1_SUMMARY.json', Path(__file__).resolve()]
seal = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
(OUT / 'RUN_V1_RECEIPT_SHA256.json').write_text(json.dumps(seal, indent=2) + '\n')
print(json.dumps(summary, indent=2))
print('receiptSHA', seal[str(RUN / 'RUN_RECEIPT.json')])
