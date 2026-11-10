"""Read saved market inputs and gap inventories; never import or run a strategy."""
from pathlib import Path
from collections import Counter
import csv
import json
import time

import numpy as np
import pandas as pd

ROOT = Path('/Users/bytedance/Documents/ChatGPT/money')
OUT = Path(__file__).resolve().parent
B = Path('/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1')
U = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031')
E = Path('/Users/bytedance/Documents/Codex/2026-11-06/entry_state_selection_v1')
H = ROOT / 'docs/handoff_2026-11-10'
START, END = pd.Timestamp('2024-09-02'), pd.Timestamp('2025-01-20')


def read(p):
    return json.loads(Path(p).read_text())


def write_json(name, obj):
    with (OUT / name).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def write_csv(name, rows):
    if not rows:
        return
    with (OUT / name).open('x', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


t0 = time.monotonic()
roster_path = B / 'joint51_candidate_v9_facts/CLASSIFICATION_ALL1709.csv'
roster = pd.read_csv(roster_path, keep_default_na=False)
roster = roster[roster.eligible.eq(True)]
manifest = {m['symbol']: m for m in read(U / 'STOCK_MANIFEST.json')}
calendar = pd.read_parquet(E / 'momentum_persistence_breadth_v1/canonical_mu3_comparison_v2/KNOWN3.parquet', columns=[]).index
calendar = calendar[(calendar >= START) & (calendar <= END)]
assert len(roster) == 1692 and len(calendar) == 93

coverage, absent, fields_bad, actions = [], [], [], []
action_counts = Counter()
for number, r in enumerate(roster.itertuples(index=False), 1):
    sid = r.symbol
    p = Path(next(p for p in manifest[sid]['source_sha256'] if p.endswith('/signal.parquet')))
    columns = ['raw_open', 'raw_high', 'raw_low', 'raw_close', 'raw_volume', 'amount',
               'adjustment_factor', 'volume_eligible', 'price_eligible', 'source_invalid', 'segment_id']
    raw = pd.read_parquet(p, columns=columns)
    z = raw.loc[(raw.index >= START) & (raw.index <= END)]
    internal = calendar[(calendar >= raw.index.min()) & (calendar <= raw.index.max())].difference(raw.index)
    for d in internal:
        absent.append(dict(symbol=sid, name=r.name, day=str(d.date()),
                           classification='NO_SOURCE_ROW_STATUS_UNRESOLVED_NOT_PROVEN_MISSING_BAR', source=str(p)))
    invalid = {}
    for c in ['raw_open', 'raw_high', 'raw_low', 'raw_close', 'adjustment_factor', 'amount', 'raw_volume']:
        valid = np.isfinite(z[c]) & z[c].gt(0)
        invalid[c] = int((~valid).sum())
        for d in z.index[~valid]:
            fields_bad.append(dict(symbol=sid, name=r.name, day=str(d.date()), field=c,
                                   value=str(z.loc[d, c]), source=str(p)))
    ap = ROOT / 'research_rounds/a-share-selection-e0-20261024/inputs-v1/actions' / (sid + '.json')
    ad = read(ap)
    period_events = 0
    for ev in ad.get('events', []):
        cash = float(ev.get('cash_per_old_share') or 0)
        split = float(ev.get('split_ratio') or 1)
        in_window = START <= pd.Timestamp(ev['effective_date']) <= END
        action_counts['all_saved_events'] += 1
        action_counts['cash_events'] += int(cash > 0)
        action_counts['cash_events_payment_unknown'] += int(cash > 0 and not ev.get('paid_at'))
        action_counts['nonunit_ratio_events'] += int(split != 1)
        action_counts['nonunit_ratio_sellable_unknown'] += int(split != 1 and not ev.get('new_shares_sellable_at'))
        if in_window:
            period_events += 1
            actions.append(dict(symbol=sid, name=r.name, source_effective_date=ev['effective_date'],
                                cash_per_old_share=ev.get('cash_per_old_share'), split_ratio=ev.get('split_ratio'),
                                paid_at=ev.get('paid_at'), new_shares_sellable_at=ev.get('new_shares_sellable_at'),
                                classification=ev.get('classification'), source=str(ap)))
    coverage.append(dict(symbol=sid, name=r.name, sector=r.sector51, full_source_first=str(raw.index.min().date()),
                         full_source_last=str(raw.index.max().date()), full_source_rows=len(raw),
                         window_rows=len(z), common_calendar_sessions=len(calendar),
                         internal_absent_sessions=len(internal), invalid_open=invalid['raw_open'],
                         invalid_close=invalid['raw_close'], invalid_factor=invalid['adjustment_factor'],
                         zero_or_invalid_volume=invalid['raw_volume'], zero_or_invalid_amount=invalid['amount'],
                         source_invalid_rows=int(z.source_invalid.fillna(True).sum()),
                         period_source_action_events=period_events, source=str(p)))
    if number % 400 == 0:
        print(f'Checked {number}/{len(roster)} saved source tables', flush=True)

event_snapshot = read(H / 'contributions/m12_runtime/EVENT_COVERAGE_SNAPSHOT.json')
gaps = []
required = {
    'october_local_primary_pdf': ('LOCAL_EVIDENCE_NOT_ADMITTED', '复核已有公告、精确事件与源因子桥并接入；688507另缺对应公告公开记录'),
    'january_local_official_raw': ('LOCAL_RAW_NOT_REVIEWED_OR_ADMITTED', '从现有官方响应提取精确事件，核对登记/除权/付款日及金额并接入'),
    'january_missing_official_exact_evidence': ('OFFICIAL_EXACT_EVIDENCE_MISSING', '取得对应实施公告或完整官方事件行：登记日、除权日、到账日、每股现金、适用股类'),
}
for category, (status, needed) in required.items():
    for day, symbols in event_snapshot['categories'][category].items():
        for sid in symbols:
            if [sid, day] == event_snapshot['v2_exact_new_admitted']:
                continue
            gaps.append(dict(symbol=sid, source_event_date=day, category=category, status=status,
                             required=needed, scope='M12_TARGET_20240902_20250120',
                             evidence=str(H / 'contributions/m12_runtime/EVENT_COVERAGE_SNAPSHOT.json')))
for ev in event_snapshot['categories']['non_cash_or_nonstandard']:
    gaps.append(dict(symbol=ev['sid'], source_event_date=ev['date'], category=ev['kind'],
                     status='COMPLEX_EVENT_FACTS_AND_ACCOUNTING_UNRESOLVED', required=ev['local_hint'],
                     scope='M12_TARGET_20240902_20250120',
                     evidence=str(H / 'contributions/m12_runtime/EVENT_COVERAGE_SNAPSHOT.json')))
assert len(gaps) == 54
q1 = read(B / 'mainline_m7_2025q1_universe_facts_v1/Q1_ADDITIONAL_74_BLOCKERS.json')
q1_rows = [dict(symbol=x['sid'], ex_date=x['ex_date'], reasons='|'.join(x['reasons']),
                source_bridge_pass=x['source_bridge_pass'], scope='2025Q1_FULL_FROZEN_UNIVERSE_NOT_ADDITIVE_TO_M12_14') for x in q1]

deps = list(csv.DictReader((H / 'CURRENT_INPUT_DEPENDENCIES.csv').open(encoding='utf-8-sig')))
missing_deps = [x['absolute_path'] for x in deps if not Path(x['absolute_path']).is_file()]
summary = dict(audit_kind='READ_ONLY_SAVED_DATA_INVENTORY_NO_INDICATORS_NO_BACKTEST_NO_DOWNLOAD',
               universe=len(roster), window=[str(START.date()), str(END.date())], sessions=len(calendar),
               raw_source_tables_found=len(coverage), tables_with_any_window_rows=sum(x['window_rows'] > 0 for x in coverage),
               tables_without_window_rows=[x['symbol'] for x in coverage if not x['window_rows']],
               internal_no_source_row_stock_sessions=len(absent),
               stocks_with_internal_no_source_row=len({x['symbol'] for x in absent}),
               field_invalid_counts=dict(Counter(x['field'] for x in fields_bad)),
               source_invalid_rows=sum(x['source_invalid_rows'] for x in coverage),
               all_saved_action_summary=dict(action_counts), explicit_source_actions_in_window=len(actions),
               current_m12_potential_event_boundaries=len(gaps),
               current_m12_boundary_categories=dict(Counter(x['category'] for x in gaps)),
               q1_missing_official_events=len(q1_rows), q1_missing_is_larger_scope_and_overlaps_m12=True,
               dependencies_checked=len(deps), dependencies_missing=missing_deps,
               external_dependency_count=sum(not x['absolute_path'].startswith(str(ROOT) + '/') for x in deps),
               elapsed_seconds=round(time.monotonic() - t0, 3),
               limits=['Missing source rows do not establish missing trading data: suspension and listing status need separate evidence.',
                       'Events not admitted are potential boundaries, not proof of a held-position blocker.',
                       'Historical source-payment unknowns are not a count of current unresolved events.',
                       'Existence checked; no full rehash of all large frozen dependencies.',
                       'This is the frozen 1692-stock mainline input, not the live 407-stock desk data.'])
write_csv('source_coverage_1692.csv', coverage)
write_csv('no_source_rows_requires_status.csv', absent)
write_csv('invalid_source_fields.csv', fields_bad)
write_csv('explicit_actions_target_window.csv', actions)
write_csv('m12_potential_event_boundaries_54.csv', gaps)
write_csv('q1_missing_official_events_46.csv', q1_rows)
write_json('SUMMARY.json', summary)
print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
