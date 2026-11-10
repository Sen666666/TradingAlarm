"""One fixed pure-signal historical pass, after the saved original-input gate."""
from __future__ import annotations
from dataclasses import asdict
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

import pandas as pd

O = Path(__file__).resolve().parent
BASE = O.parent
FROZEN = BASE / 'v2-frozen'
INPUT = BASE / 'input-preparation/prepared-v2'
RUN = O / 'run-v1'
PROOF = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/market-proof-lifecycle-readonly-20261101')
AUDIT = Path('/tmp/price-permission-v2-independent-86ax66p4/AUDIT.json')
EXPECTED_CORE = '962275bd41b5c7bbc062a1191780a6b6a9c616f8d3097ea669b602eabbc9ac59'
EXPECTED_CONTRACT = 'c3914aed1896563253961ea40d6065614a115cef21e13a93e1e74ad71779c54a'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, float):
        return x if math.isfinite(x) else None
    if isinstance(x, pd.Timestamp):
        return str(x.date())
    if hasattr(x, 'item'):
        return clean(x.item())
    return x


def save(name, x):
    (RUN / name).write_text(json.dumps(clean(x), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def number(x):
    return float(x) if pd.notna(x) and math.isfinite(x) else None


def main():
    RUN.mkdir(exist_ok=False)
    gate = json.loads((INPUT / 'INPUT_GATE.json').read_text())
    assert gate['passed'] and gate['existing_checkpoints_exact'] == 37 and len(gate['physical_raw_prefixes']) >= 3
    assert gate['v2_frozen_unchanged']
    audit = json.loads(AUDIT.read_text())
    assert audit['passed'] and audit['source_sha256'] == EXPECTED_CORE and audit['contract_sha256'] == EXPECTED_CONTRACT
    assert sha(FROZEN / 'signal_core.py') == EXPECTED_CORE
    assert sha(FROZEN / 'CONTRACT.md') == EXPECTED_CONTRACT
    artifacts = json.loads((INPUT / 'ARTIFACT_SHA256.json').read_text())
    assert all(sha(INPUT / p) == h for p, h in artifacts.items())
    frozen_before = {p.name: sha(p) for p in FROZEN.iterdir() if p.is_file()}
    input_before = {str(p.relative_to(INPUT)): sha(p) for p in INPUT.rglob('*') if p.is_file()}
    registry = json.loads((INPUT / 'FIXED_CASE_INPUT_REGISTRY.json').read_text())
    streams = [
        ('OLD407_global', 'OLD407/market.parquet', '2024-12-31', 'OLD407', 'composite-original-as-run'),
        ('NATIVE1709_global', 'NATIVE1709/market.parquet', '2026-06-30', 'NATIVE1709', 'composite-original-as-run'),
        ('NATIVE1709_semiconductor', 'NATIVE1709/industry_URFI881121.parquet', '2026-06-30', 'NATIVE1709', 'index-URFI881121'),
        ('NATIVE1709_electronic_chemicals', 'NATIVE1709/industry_URFI881172.parquet', '2026-06-30', 'NATIVE1709', 'index-URFI881172'),
    ]
    save('SHADOW_FREEZE.json', dict(core_sha256=EXPECTED_CORE, contract_sha256=EXPECTED_CONTRACT,
                                   independent_audit_sha256=sha(AUDIT), input_gate_sha256=sha(INPUT / 'INPUT_GATE.json'),
                                   original_input_artifact_manifest_sha256=sha(INPUT / 'ARTIFACT_SHA256.json'),
                                   runner_sha256=sha(Path(__file__)), protocol_sha256=sha(O / 'PROTOCOL.md'),
                                   streams=streams, case_primary_windows={c['case']: c['existing_primary_window'] for c in registry},
                                   no_account_seed=True, one_pass_per_unique_stream=True, execution='close decision for next eligible open only',
                                   candidate_parameters_unchanged=True, new_account_runs=0))
    # Import happens only after gate checks AND the run freeze have been saved.
    spec = importlib.util.spec_from_file_location('frozen_permission_core', FROZEN / 'signal_core.py')
    core = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = core
    spec.loader.exec_module(core)
    results = {}
    summaries = {}
    events = []
    for name, path, end, domain, price_kind in streams:
        data = pd.read_parquet(INPUT / path).loc[:end]
        assert data.index.is_unique and data.index.is_monotonic_increasing
        state = core.State(scope=name)
        daily = []
        previous_permit = False
        current_segment = 0
        for day, row in data.iterrows():
            before = state
            if price_kind.startswith('index') and pd.notna(row.price_source_segment_id):
                current_segment = int(row.price_source_segment_id)
            source = core.Source(domain + '-fixed-research-roster', price_kind,
                                 'original-signed-m21/min5/equal-sector-min8' if price_kind.startswith('composite') else 'original-signed-m21/research-industry-min5',
                                 'original-source-segment-' + str(current_segment))
            close = number(row.price_input)
            breadth = number(row.breadth)
            state, d = core.step(state, core.Observation(str(day.date()), source, close, breadth))
            permit_change = None
            if d.permit_next_open != previous_permit:
                permit_change = 'permission_granted' if d.permit_next_open else 'permission_revoked'
            rec = dict(day=str(day.date()), stream=name, close=close, breadth=breadth,
                       breadth_margin= breadth - .6 if breadth is not None else None,
                       old_line_log_margin=math.log(close/d.line_used) if close is not None and d.line_used is not None else None,
                       mode=d.mode, effective_status=d.effective_status,
                       permit_next_open=d.permit_next_open, permission_change=permit_change,
                       original_break=d.original_break, line_used=d.line_used, next_line=d.next_line,
                       prior_scale=d.scale_before_close, anchor=state.anchor, frontier=state.frontier,
                       frozen_segment_scale=state.scale, credit=state.credit,
                       starts=state.starts, repairs=state.repairs, failures=state.failures,
                       pending_failure_at=state.pending_price_failure.at if state.pending_price_failure else None,
                       events=list(d.events), unknown=list(d.unknown),
                       source_segment=current_segment,
                       ready_m=number(row.get('ready_m', row.get('signed_m_stocks_ready'))),
                       positive_m=number(row.get('positive_m')),
                       ready_industries=number(row.get('breadth_industries_ready')))
            daily.append(rec)
            significant = [e for e in d.events if e != 'price_advance']
            if significant or permit_change:
                event = dict(rec)
                event['failure_receipt'] = asdict(state.failure_log[-1]) if state.failures > before.failures else None
                events.append(event)
            previous_permit = d.permit_next_open
        df = pd.DataFrame(daily).set_index('day')
        results[name] = df
        flat = df.copy()
        for col in ['events', 'unknown']:
            flat[col] = flat[col].map(lambda x: json.dumps(x, ensure_ascii=False))
        flat.to_csv(RUN / (name + '_daily.csv'), float_format='%.17g')
        df.to_parquet(RUN / (name + '_daily.parquet'))
        (RUN / (name + '_final_checkpoint.json')).write_text(core.dumps(state) + '\n')
        summaries[name] = dict(first=df.index[0], last=df.index[-1], observations=len(df),
                               first_break_start=next((str(x['day']) for x in daily if 'break_started' in x['events']), None),
                               lifetime_starts=state.starts, lifetime_repairs=state.repairs, lifetime_price_failures=state.failures,
                               unknown_price=sum('price' in x['unknown'] for x in daily), unknown_breadth=sum('breadth' in x['unknown'] for x in daily),
                               pending_days=sum(x['effective_status']=='PENDING_PRICE_FAILURE' for x in daily),
                               left_state='WAIT at earliest available source; complete prefix consumed; no case/account reset')
    save('STREAM_SUMMARY.json', summaries)
    save('EVENTS.json', events)
    case_results = []
    for c in registry:
        start, end = c['existing_primary_window']
        names = [c['domain'] + '_global']
        if c['case'] == 'PVR_SLOT1_2026_LOCAL':
            names += ['NATIVE1709_semiconductor', 'NATIVE1709_electronic_chemicals']
        for name in names:
            df = results[name]
            window = df.loc[start:end]
            previous = df.loc[df.index < start].iloc[-1]
            selected_events = [r for r in events if r['stream']==name and start<=r['day']<=end]
            critical = []
            for col in ['breadth_margin', 'old_line_log_margin']:
                known = window[window[col].notna()]
                for day in known[col].abs().sort_values(kind='stable').head(3).index:
                    critical.append(dict(day=day, quantity=col, distance=window.loc[day, col],
                                         status=window.loc[day, 'effective_status'], permit=bool(window.loc[day,'permit_next_open'])))
            repaired_refailed = []
            restores = [r for r in selected_events if 'repair_restored' in r['events']]
            for r in restores:
                nxt = next((x for x in selected_events if x['day']>r['day'] and any(e.startswith('price_failure_') for e in x['events'])), None)
                if nxt:
                    repaired_refailed.append(dict(restored=r['day'], next_observed_price_failure=nxt['day'],
                                                  observations_until_failure=int(df.index.get_loc(nxt['day'])-df.index.get_loc(r['day'])),
                                                  breadth_at_failure=nxt['breadth']))
            case_results.append(dict(case=c['case'], stream=name, window=[start,end], observations=len(window),
                                     prior_close_status=previous.effective_status, prior_close_permit=bool(previous.permit_next_open),
                                     first_close_status=window.iloc[0].effective_status, end_status=window.iloc[-1].effective_status,
                                     permitted_closes=int(window.permit_next_open.sum()),
                                     grant_dates=[r['day'] for r in selected_events if r['permission_change']=='permission_granted'],
                                     withdrawal_dates=[r['day'] for r in selected_events if r['permission_change']=='permission_revoked'],
                                     break_start_dates=[r['day'] for r in selected_events if 'break_started' in r['events']],
                                     restore_dates=[r['day'] for r in restores],
                                     price_failure_dates=[r['day'] for r in selected_events if any(e.startswith('price_failure_') for e in r['events'])],
                                     ended_dates=[r['day'] for r in selected_events if r['mode']=='ENDED' and r['events']],
                                     unknown_price_days=int(window.close.isna().sum()), unknown_breadth_days=int(window.breadth.isna().sum()),
                                     pending_days=int((window.effective_status=='PENDING_PRICE_FAILURE').sum()),
                                     critical_observations=critical, repaired_then_failed_again=repaired_refailed,
                                     event_records=selected_events))
    save('FIXED_CASE_RESULTS.json', case_results)
    local = []
    for name in ['NATIVE1709_semiconductor', 'NATIVE1709_electronic_chemicals']:
        idx = results[name].loc['2026-04-30':'2026-06-30'].index
        for day in idx:
            industry = results[name].loc[day]
            global_row = results['NATIVE1709_global'].loc[day]
            local.append(dict(day=day, stream=name, industry_permit=bool(industry.permit_next_open), global_permit=bool(global_row.permit_next_open),
                              industry_status=industry.effective_status, global_status=global_row.effective_status,
                              industry_breadth=industry.breadth, global_breadth=global_row.breadth,
                              local_permit_global_withheld=bool(industry.permit_next_open and not global_row.permit_next_open)))
    save('GLOBAL_LOCAL_COMPARISON.json', local)
    checkpoint_labels = []
    for c in json.loads((PROOF / 'CHECKPOINT_LIFECYCLE.json').read_text()):
        name = c['domain'] + '_global'
        day = c['day']
        if day in results[name].index:
            r = results[name].loc[day]
            checkpoint_labels.append(dict(case=c['case'], day=day, stream=name, mode=r.effective_status,
                                          permit_for_next_open=bool(r.permit_next_open), label_clock='this close -> next eligible open, no original trade labeling'))
        else:
            checkpoint_labels.append(dict(case=c['case'], day=day, stream=name, shadow_not_run='outside fixed old924 primary endpoint; original input checkpoint was validated'))
    save('CHECKPOINT_SHADOW_LABELS.json', checkpoint_labels)
    assert frozen_before == {p.name: sha(p) for p in FROZEN.iterdir() if p.is_file()}
    assert input_before == {str(p.relative_to(INPUT)): sha(p) for p in INPUT.rglob('*') if p.is_file()}
    save('COMPLETION.json', dict(passed=True, unique_streams=4, observations=sum(len(df) for df in results.values()),
                                fixed_case_projections=len(case_results), one_pass_per_stream=True,
                                frozen_core_and_contract_unchanged=True, input_artifacts_unchanged=True,
                                account_paths=0, financial_returns=0, order_simulations=0, source_downloads=0,
                                parameter_changes=0, history_reruns=0, independent_result_audit='pending in another task'))
    save('ARTIFACT_SHA256.json', {p.name: sha(p) for p in sorted(RUN.iterdir()) if p.is_file() and p.name != 'ARTIFACT_SHA256.json'})
    print(json.dumps(clean(dict(completed=True, streams=summaries,
                               cases=[{k:c[k] for k in ['case','stream','observations','permitted_closes','break_start_dates','restore_dates','price_failure_dates']} for c in case_results])), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
