"""Prepare saved original CP and request annotations only. No V4/state/account run."""
from pathlib import Path
import hashlib
import json
import math
import csv
import pandas as pd
import numpy as np

HERE = Path(__file__).resolve().parent
BASE = HERE.parent
WORK = BASE.parent
SM = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
Y_MANIFEST = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/2022-normal-reference-20261031/inputs/MANIFEST.json')
H_MANIFEST = Path('/Users/bytedance/Documents/Codex/2026-11-04/task/ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/MANIFEST.json')
SOURCES = {}


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def read_json(p):
    p = Path(p); SOURCES[str(p)] = sha(p)
    return json.loads(p.read_text())


def clean(x):
    if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)): return [clean(v) for v in x]
    if x is None or x is pd.NA: return None
    if isinstance(x, (float, np.floating)): return float(x) if math.isfinite(x) else None
    if isinstance(x, (np.bool_,)): return bool(x)
    if isinstance(x, (np.integer,)): return int(x)
    if isinstance(x, pd.Timestamp): return str(x.date())
    return x


def save(name, x):
    (HERE / name).write_text(json.dumps(clean(x), ensure_ascii=False, indent=2) + '\n')


def selected(sid, day):
    return ('2022-01-01' <= day <= '2022-01-31') if sid == '000620.SZ' else ('2024-01-01' <= day <= '2024-01-31' or '2024-09-01' <= day <= '2024-11-27')


def main():
    manifest = {r['symbol']: r for r in read_json(SM) if r['symbol'] in ('000620.SZ', '002583.SZ')}
    input_index = {r['sid']: r for r in read_json(BASE / 'path_inputs/INPUT_INDEX.json')}
    schemas = read_json(BASE / 'path_inputs/SOURCE_SCHEMAS.json')
    traces = {(r['sid'], r['day']): r for r in read_json(BASE / 'signal_traces_v3/v3_all4/ALL_DAILY_TRACES.json')}
    requests = read_json(BASE / 'signal_traces/v2_all7/ORIGINAL_INTENT_SIGNAL_JOIN.json')
    requests = [{k: v for k, v in r.items() if k.startswith('original_') or k in ('sid', 'window')}
                for r in requests if r['sid'] in manifest and selected(r['sid'], r['original_signal_at'][:10])]
    chains = read_json(WORK / 'structural_failure_v1/chains/COMPLETE_ORIGINAL_CHAINS.json')
    snapshots = {}
    for chain in chains:
        sid = chain['campaign']['sid']
        if sid not in manifest: continue
        for row in chain['observations']:
            live = []
            for layer in row['actual_live_layers']:
                snap = layer['snapshot']
                live.append({k: snap.get(k) for k in ('id', 'kind', 'opened', 'signal_at', 'floor', 'last_core_line', 'stock_structure', 'budget_order')})
            snapshots[(sid, row['day'])] = {'original_live_layer_annotations': live,
                'original_pending_sells': row['original_pending_sells'],
                'source_scope': 'Original CLOSE snapshot only; does not establish V4 positions, pending orders or fill completion.'}
    annual = {'000620.SZ': read_json(Y_MANIFEST), '002583.SZ': read_json(H_MANIFEST)}
    daily = []; receipts = []; generator_sources = {}; checks = []
    for sid, meta in manifest.items():
        src = Path(input_index[sid]['output'])
        assert sha(src) == input_index[sid]['output_sha256']; SOURCES[str(src)] = sha(src)
        frame = pd.read_parquet(src)
        inp = Path(meta['refs']['CP1_input']); SOURCES[str(inp)] = sha(inp)
        f = pd.read_parquet(inp)
        gen = f.loc[[d for d in frame.index if selected(sid, str(d.date()))]]
        assert (gen.e0_valid == frame.loc[gen.index, 'native__i_target'].astype(bool)).all()
        assert np.array_equal(gen.i_floor.to_numpy(), frame.loc[gen.index, 'native__i_floor'].to_numpy(), equal_nan=True)
        rec = next(r for r in annual[sid] if r['sid'] == sid)
        canonical_path = Path(rec['output_path'])
        assert sha(canonical_path) == rec['output_sha256']
        canonical = {r['confirmed_day']: r for r in read_json(canonical_path)}
        generator_sources[sid] = {'input_path': str(inp), 'source_first_day': str(f.index[0].date()),
            'source_last_day': str(f.index[-1].date()), 'columns': list(f.columns),
            'original_CP_output': schemas[sid]['CP']['path'], 'canonical_annual_receipts': str(canonical_path),
            'causal_scope': 'Frozen original CP generated using native-I-derived e0_valid and i_floor; no regeneration under V3 I.',
            'selected_e0_valid_exact_old_native_I_target': True, 'selected_i_floor_exact_old_native_I_floor': True}
        for stamp, row in frame.iterrows():
            day = str(stamp.date())
            if not selected(sid, day): continue
            original_cp = {k[4:]: v for k, v in row.items() if k.startswith('CP__')}
            proof = canonical.get(day)
            assert bool(original_cp['receipt']) == (proof is not None)
            if proof is not None:
                assert proof['original_candidate'] == original_cp['candidate']
                assert proof['original_scale'] == original_cp['scale']
            req = [r for r in requests if r['sid'] == sid and r['original_signal_at'][:10] == day]
            for r in req:
                if r['original_CP1_id'] is not None:
                    assert proof and r['original_CP1_id'] == proof['receipt_id']
            t = traces[(sid, day)]
            item = {'sid': sid, 'day': day, 'C': row['price__close'], 'raw_C': row['price__raw_close'],
                'source_segment': row['price__segment_id'], 'original_E0_event': row['events__event'],
                'original_native_I_target': row['native__i_target'], 'original_native_I_floor': row['native__i_floor'],
                'original_native_I_buy': row['native__i_buy'], 'original_G1_grade': row['native__g_grade'],
                'original_CP': original_cp, 'canonical_receipt': proof,
                'original_CP_generator_input': gen.loc[stamp].to_dict(),
                'original_requests': req,
                'V3_signal_comparison_only': {k: t[k] for k in ('generation', 'active_generation', 'mode', 'I_hold', 'I_expand', 'P_old', 'P_new', 'R', 'up_after_R', 'recovery_cycle', 'trial_event', 'support_exit_events')},
                'original_position_condition_only': snapshots.get((sid, day)),
                'original_position_snapshot_status': 'SAVED_ORIGINAL_CONDITION_ONLY' if (sid, day) in snapshots else 'NOT_IN_REUSED_CHAIN_SCOPE_UNKNOWN_NOT_FLAT'}
            daily.append(item)
            if proof:
                receipts.append({'sid': sid, 'confirmed_CLOSE_day': day, 'receipt_id': proof['receipt_id'],
                    'original_candidate_adjusted': proof['original_candidate'],
                    'original_used_scale': proof['original_scale'], 'scale_frozen_at': proof['scale_frozen_at'],
                    'formation_start_exclusive': proof['formation_start_exclusive'],
                    'formation_end_inclusive': proof['formation_end_inclusive'],
                    'original_E0_episode_id': proof['original_E0_episode_id'],
                    'request_roles': [r['original_role'] for r in req],
                    'request_CP_ids': [r['original_CP1_id'] for r in req],
                    'original_actual_layer_ids': [n for r in req for n in r['original_actual_layer_ids']],
                    'V3_mode_comparison_only': t['mode'], 'V3_I_expand_comparison_only': t['I_expand'],
                    'V3_new_up_event_same_day': t['trial_event'] is not None,
                    'source_receipt_file': str(canonical_path)})
        checks.append({'sid': sid, 'days': len(gen), 'receipts': sum(r['sid'] == sid for r in receipts),
                       'canonical_receipt_dates_candidate_scale_exact': True, 'original_request_CP_ids_exact': True})
    for name in ('model.py', 'common.py'):
        path = Path('/Users/bytedance/Documents/ChatGPT/money/research_rounds/continuous-protection-lines-20261028/code') / name
        SOURCES[str(path)] = sha(path)
    save('DAILY_ORIGINAL_CP_INPUTS.json', daily)
    save('CP_RECEIPT_TABLE.json', receipts)
    save('ORIGINAL_REQUEST_ANNOTATIONS.json', requests)
    save('CP_GENERATOR_SOURCE_AND_INPUT_CONTRACT.json', generator_sources)
    with (HERE / 'CP_RECEIPT_TABLE.csv').open('w', newline='') as out:
        writer = csv.DictWriter(out, fieldnames=list(receipts[0])); writer.writeheader()
        for row in receipts:
            writer.writerow({k: json.dumps(v, ensure_ascii=False) if isinstance(v, list) else v for k, v in row.items()})
    assert len(daily) == 97 and len(receipts) == 29
    save('PREPARATION_RECEIPT.json', {'status': 'ORIGINAL_FACTS_ONLY_READY_NO_V4_RUN', 'checks': checks,
         'daily_rows': len(daily), 'receipt_rows': len(receipts), 'request_rows': len(requests),
         'new_models': 0, 'new_states': 0, 'accounts': 0, 'orders': 0, 'quantities': 0, 'cash_or_returns': 0,
         'script_sha256': sha(__file__), 'source_sha256': SOURCES,
         'missing_snapshot_means': 'Unknown outside reused original chain scope, never candidate-flat.',
         'hold_scope': 'V3 signal holding generation is not actual position. Original snapshot is conditional annotation only.'})
    save('OUTPUT_SHA256.json', {str(p): sha(p) for p in HERE.iterdir() if p.is_file() and p.name != 'OUTPUT_SHA256.json'})
    print(json.dumps({'checks': checks, 'requests': len(requests), 'output': str(HERE)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
