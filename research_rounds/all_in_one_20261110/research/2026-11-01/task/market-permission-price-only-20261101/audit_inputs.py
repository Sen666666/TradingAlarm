"""Read existing metadata/CSV only. Never imports or calls the permission core.

Writes only beside this file. No download, indicator computation or account
replay. Existing account artifacts are read as bytes only for prior digest
controls. Existing prices/breadths are inspected, never regenerated.
"""
import csv
import hashlib
import json
import math
from pathlib import Path

OUT = Path(__file__).resolve().parent
PROJECT = Path('/Users/bytedance/Documents/ChatGPT/money')
RR = PROJECT / 'research_rounds'
RESEARCH = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
PROOF = RESEARCH / 'market-proof-lifecycle-readonly-20261101'
SOURCES = {}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def remember(path):
    path = Path(path)
    SOURCES[str(path)] = sha(path)
    return path


def read_json(path):
    return json.loads(remember(path).read_text())


def read_csv(path):
    with remember(path).open() as f:
        return list(csv.DictReader(f))


def finite(s):
    try:
        return bool(s != '' and math.isfinite(float(s)))
    except (TypeError, ValueError):
        return False


def csv_inventory(path, start, end):
    rows = read_csv(path)
    key = 'date' if 'date' in rows[0] else ''
    inside = [r for r in rows if start <= r[key] <= end]
    return dict(
        path=str(path), sha256=SOURCES[str(path)], rows=len(rows),
        first=rows[0][key], last=rows[-1][key], fields=list(rows[0]),
        date_unique=len({r[key] for r in rows}) == len(rows),
        date_ordered=[r[key] for r in rows] == sorted(r[key] for r in rows),
        calendar_window=[start, end], window_observations=len(inside),
        window_known_price=sum(finite(r.get('market')) and float(r['market']) > 0 for r in inside),
        window_known_breadth=sum(finite(r.get('breadth')) for r in inside),
        first_known_breadth=next((r[key] for r in rows if finite(r.get('breadth'))), None),
        prefix_observation_slots=sum(r[key] < start for r in rows),
        price_observation_provenance='CSV has no per-date price-source-ready flags; original price fills missing aggregate return with zero',
        signed_m_denominators='not in this CSV; selected fixed-point coverage available separately',
        scale_or_candidate_outputs_computed=False,
    )


def price_inventory(path):
    # Read existing fields only; no return, scale, frontier, line or state.
    import pyarrow.parquet as pq
    pf = pq.ParquetFile(path)
    rows = pq.read_table(path, columns=['date', 'close', 'segment_id']).to_pylist()
    dates = [str(r['date'])[:10] for r in rows]
    valid = [finite(r['close']) and r['close'] > 0 for r in rows]
    return dict(
        inspected_with='existing TradingAlarm/research/.venv/bin/python -B; pyarrow',
        schema_fields=pf.schema.names, rows=len(rows), first=dates[0], last=dates[-1],
        date_unique=len(set(dates)) == len(dates), date_ordered=dates == sorted(dates),
        known_positive_close_rows=sum(valid),
        source_segments=sorted({r['segment_id'] for r in rows}),
        calendar_window=['2026-01-01', '2026-06-30'],
        window_rows=sum('2026-01-01' <= d <= '2026-06-30' for d in dates),
        prefix_rows=sum(d < '2026-01-01' for d in dates),
        unknown_price_rows=len(rows)-sum(valid),
        new_indicators_computed=False,
    )


def main():
    source_controls = read_json(Path('/tmp/fast-recovery-source-controls-0gr4kg_m/SOURCE_CONTROLS.json'))
    for p in [PROJECT/'AGENTS.md', PROJECT/'README.md', PROJECT/'docs/HANDOFF.md',
              PROJECT/'docs/RESEARCH_CONSENSUS.md', PROJECT/'docs/NEXT_RESEARCH_TASKS.md',
              PROJECT/'docs/RESEARCH.md', PROJECT/'docs/DATA_SOURCES.md',
              PROJECT/'docs/RESEARCH_REVIEW_CHECKLIST.md',
              PROJECT/'TradingAlarm/research/TREND_RESEARCH_FOCUS.md',
              PROJECT/'TradingAlarm/desk/refresh.py', PROOF/'CORE_READOUT.txt']:
        remember(p)
    source_control_checks = {}
    for path, expected in source_controls['source_SHA256'].items():
        p = Path(path)
        if p.exists():
            actual = sha(p)
            source_control_checks[path] = dict(expected=expected, actual=actual, equal=actual == expected)
    assert all(v['equal'] for v in source_control_checks.values()), 'pre-existing source-control mismatch'
    metadata = read_json(RR/'a-share-selection-e0-20261024/inputs-v2/metadata.json')
    fixed_points = read_json(PROOF/'READY_COVERAGE_AT_FIXED_POINTS.json')
    industries = read_json(RESEARCH/'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')
    stocks = read_json(RESEARCH/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
    read_json(PROOF/'NATIVE_INPUT_COVERAGE.json')
    selected_breadth = read_json(PROOF/'INDUSTRY_M_BREADTH_SELECTED.json')
    read_json(PROOF/'OLD407_CACHED_INDUSTRY_BREADTH.json')
    old_csv = RR/'actual-risk-recovery-20261027/recovery.csv'
    native_csv = RESEARCH/'mainline-absolute-Q4-20261031/recovery.csv'
    cases = []
    common = dict(
        prototype_run=False, input_status='PARTIAL_EXISTING_CSV_NEEDS_PRICE_PROVENANCE_ADAPTER',
        warmup='63 preceding valid adjacent log returns AND 63 preceding known price slots; signed-m needs original source-segment warmup (first 64 suppressed), >=5 per industry, >=8 industries globally',
        left_censoring='begin WAIT at earliest verified input source; no account resume/ACTIVE seed; no pre-source lifecycle inference; preserve complete prefix before the calendar window',
        endpoint_policy='calendar boundary or existing source cutoff fixed before candidate history is run; no favorable candidate endpoint selection',
        snapshot_bias='current-survivor/current-industry/current-size snapshots; not PIT or unseen data',
    )
    for name, domain, start, end, p in [
        ('old_2024_924', 'OLD407_TECHNOLOGY_11_INDUSTRIES', '2024-09-01', '2024-12-31', old_csv),
        ('giveback_2022', 'NATIVE1709_90_INDUSTRIES', '2022-01-01', '2022-12-31', native_csv),
        ('continuous_2023', 'NATIVE1709_90_INDUSTRIES', '2023-01-01', '2023-12-31', native_csv),
        ('local_2026_global_context', 'NATIVE1709_90_INDUSTRIES', '2026-01-01', '2026-06-30', native_csv),
    ]:
        cases.append(dict(common, case=name, domain=domain,
                          price_definition='original sector-equal mean of stock mean eligible log returns, exponentiated cumulative return; no synthetic amount assigned',
                          breadth_definition='original signed-m industry fraction m>0, equal-weight across >=8 industries; not up-day count',
                          inventory=csv_inventory(p, start, end)))
    for sector, name in [('URFI881121', 'semiconductor'), ('URFI881172', 'electronic_chemicals')]:
        m = next(r for r in industries if r['series'] == sector)
        price = Path(m['refs']['CP1_input'])
        expected = m['output_sha256'][str(price)]
        assert sha(remember(price)) == expected
        for source in m['source_sha256']:
            remember(source)
        points = [r for r in selected_breadth if r['sector'] == sector and r['day'].startswith('2026')]
        denominators = [dict(day=r['day'], original_function_nonempty_source_roster=r['identities'], ready=r['ready'],
                             positive=r['positive'], breadth=r['breadth']) for r in points]
        legacy = RR/f'tech-drawdown-regime-20261027/diagnostic-v1/sector-{sector}.csv'
        legacy_rows = read_csv(legacy)
        cases.append(dict(
            common, case='local_2026_' + name, domain='NATIVE1709_INDUSTRY_' + sector,
            input_status='BLOCKED_MATCHING_CONTINUOUS_BREADTH_NOT_LOCATED_OR_VERIFIED',
            calendar_window=['2026-01-01', '2026-06-30'],
            price=dict(path=str(price), sha256=expected, hash_matches_existing_manifest=True,
                       semantics='actual industry price close inherited from original industry E0 source domain, not composite stock-basket price',
                       source_schema='close, segment_id declared by trace.py:source_frame; no CP1 receipt/E0 target consumed',
                       manifest_warm_from=m['warm_from'], manifest_full_observations=m['full_warm_observations'],
                       manifest_cutoff='2026-06-30 (universe prepare.py END contract)',
                       inspected_existing_fields=price_inventory(price)),
            breadth=dict(definition='within this industry, valid original signed-m>0 / ready count; minimum5, no global8-industry condition',
                         snapshot_identities=sum(v.get('sector_id') == sector for v in metadata.values()),
                         fixed_point_rows=denominators,
                         continuous_matching_native1709='not located/verified in this bounded inventory; cannot interpolate selected checkpoints',
                         legacy407_csv=str(legacy), legacy407_last=legacy_rows[-1][''],
                         legacy407_reusable=False, reason='legacy407 technology roster differs from native1709 industry denominator'),
            blockers=['continuous native1709 industry signed-m breadth with per-date ready denominator',
                      'final industry valid-observation adapter binding to the inspected price source',
                      'semantic clarification and main/independent review before any candidate history'],
        ))
    result = dict(
        scope='existing inputs and metadata only', historical_shadow_sequences=0,
        market_indicator_recomputations=0, account_runs=0, downloads=0,
        fixed_calendar_cases=cases,
        fixed_point_global_coverage=[dict(day=r['day'], ready=r['ready_signed_m'], unknown=r['unknown'],
                                          valid_industries=r['industries_meeting_original_min5']) for r in fixed_points],
        roster_counts=dict(native1709=len(stocks), industries=len(industries)),
        source_control_checks=source_control_checks,
    )
    (OUT/'HISTORICAL_INPUT_READINESS.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    (OUT/'INPUT_SHA256.json').write_text(json.dumps(SOURCES, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(dict(cases=len(cases), input_files_hashed=len(SOURCES),
                          old_source_controls_equal=len(source_control_checks), historical_shadow_sequences=0)))


if __name__ == '__main__':
    main()
