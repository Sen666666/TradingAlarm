"""One full-source pure-e export for all original 133713 primary candidates."""
from pathlib import Path
from collections import Counter
import hashlib
import importlib.util
import json
import time
import numpy as np
import pandas as pd
import features as own

HERE = Path(__file__).resolve().parent
ENTRY = HERE.parents[1]
PRIOR = ENTRY / 'pvr_information_v1'
PRIMARY = PRIOR / 'universe_audit/PRIMARY_CANDIDATES.jsonl'
EXPORTED = PRIOR / 'export/features.parquet'
EXPORTER = PRIOR / 'export/export_features.py'
ORIGINAL_FEATURE = PRIOR / 'feature_design/features.py'
SM = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
CASES = {'000620.SZ', '300666.SZ', '300085.SZ', '002583.SZ'}
KEY = ['window', 'day', 'sid']


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(name, value):
    (HERE / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def bits_equal(x, y):
    x = np.asarray(x, dtype='float64')
    y = np.asarray(y, dtype='float64')
    known = np.isfinite(x) & np.isfinite(y)
    return np.array_equal(np.isfinite(x), np.isfinite(y)) and np.array_equal(x[known].view(np.uint64), y[known].view(np.uint64))


def main():
    assert not (HERE / 'DUAL_MEMORY_FEATURES.parquet').exists()
    started = time.monotonic()
    spec = importlib.util.spec_from_file_location('dual_memory_read_only_original_loader', EXPORTER)
    loader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loader)
    assert sha(ORIGINAL_FEATURE) == loader.FEATURE_SHA
    sources = {str(p.resolve()): sha(p) for p in [PRIMARY, EXPORTED, EXPORTER, ORIGINAL_FEATURE, SM, HERE / 'features.py', Path(__file__)]}
    assert sources[str(PRIMARY.resolve())] == '49b4a70d62a497d8b610e15133a2e9f383c14a1b360275b785c0b0955e92496a'
    rows = []
    with PRIMARY.open() as stream:
        for i, line in enumerate(stream):
            row = json.loads(line)
            rows.append(dict(candidate_index=i, sid=row['sid'], day=row['day'], window=row['window'], decision_at=row['decision_at']))
    primary = pd.DataFrame(rows)
    assert len(primary) == 133713 and primary.sid.nunique() == 1660 and not primary.duplicated(KEY).any()
    meta = {r['symbol']: r for r in json.loads(SM.read_text())}
    old = pd.read_parquet(EXPORTED, columns=KEY + list(own.E_COLUMNS) + ['source_segment', 'pvr_valid_observation', 'pvr_clock_block', 'pvr_block_observation'])
    old_by_sid = {sid: group for sid, group in old.groupby('sid', sort=False)}
    outputs = []
    cases = []
    check = Counter()
    prefixes = []
    for number, (sid, candidates) in enumerate(primary.groupby('sid', sort=True)):
        signal = loader.read_signal(meta[sid], sources)
        valid, block = loader.API.original_observation_clock(signal)
        full = own.calculate(signal, valid, block)
        saved = old_by_sid[sid]
        dates = pd.DatetimeIndex(saved.day)
        aligned = full.reindex(dates)
        # All exported dates for all candidate symbols, including historical
        # warmup/invalid/missing cells; no comparison limited to selected days.
        for field in own.E_COLUMNS:
            assert bits_equal(aligned[field].to_numpy(float), saved[field].to_numpy(float)), (sid, field, 'export not bitexact')
            check[field + '_export_cells'] += len(saved)
            check[field + '_export_finite_bitexact'] += int(np.isfinite(saved[field].to_numpy(float)).sum())
        for field in ['source_segment', 'pvr_clock_block', 'pvr_block_observation']:
            assert bits_equal(aligned[field].to_numpy(float, na_value=np.nan), saved[field].to_numpy(float, na_value=np.nan)), (sid, field)
        assert np.array_equal(aligned.pvr_valid_observation.fillna(False).to_numpy(bool), saved.pvr_valid_observation.to_numpy(bool))
        requested = pd.DatetimeIndex(candidates.day)
        selected = full.reindex(requested).copy()
        selected.index = candidates.index
        selected['source_row_present'] = requested.isin(signal.index)
        selected['pvr_valid_observation'] = selected.pvr_valid_observation.fillna(False).astype(bool)
        selected['dual_memory_status'] = selected.dual_memory_status.fillna('NO_EXACT_SOURCE_OBSERVATION')
        selected['fast_status'] = selected.fast_status.fillna('NO_EXACT_SOURCE_OBSERVATION')
        selected['slow_status'] = selected.slow_status.fillna('NO_EXACT_SOURCE_OBSERVATION')
        for field in candidates:
            selected[field] = candidates[field]
        assert len(selected) == len(candidates)
        source_path, source_sha = loader.signal_path(meta[sid])
        selected['signal_source_sha256'] = source_sha
        outputs.append(selected)
        if sid in CASES:
            byblock = {int(k): g for k, g in full.loc[valid].groupby(block[valid], sort=False)}
            for _, row in selected.iterrows():
                example = dict(candidate_index=int(row.candidate_index), window=row.window, sid=sid, day=row.day,
                               dual_memory_status=str(row.dual_memory_status), fast_status=str(row.fast_status), slow_status=str(row.slow_status), signal_source_sha256=source_sha)
                if row.dual_memory_status == 'KNOWN':
                    group = byblock[int(row.pvr_clock_block)]
                    j = int(row.pvr_block_observation)
                    evidence = group.iloc[j-62:j+1]
                    example.update(e_days=evidence.index.strftime('%Y-%m-%d').tolist(), e_values=evidence.e.tolist(),
                                   E_fast=float(row.E_fast), E_slow=float(row.E_slow), e_t=float(row.e))
                cases.append(example)
        if sid in {'300058.SZ', '002583.SZ'}:
            cutoff = pd.Timestamp('2022-01-04' if sid == '300058.SZ' else '2024-11-01')
            short = signal.loc[:cutoff].copy()
            sv, sb = loader.API.original_observation_clock(short)
            truncated = own.calculate(short, sv, sb)
            assert truncated.equals(full.loc[truncated.index]), (sid, 'prefix mismatch')
            scalar = loader.API.original_pvr(short)
            for field in own.E_COLUMNS:
                assert bits_equal(truncated[field], scalar[field]), (sid, field, 'original scalar prefix mismatch')
            prefixes.append(dict(sid=sid, cutoff=str(cutoff.date()), truncated_source_rows=len(short), full_source_rows=len(signal),
                                 all_columns_all_common_rows_exact=True, original_scalar_six_columns_bitexact=True))
        if (number + 1) % 200 == 0:
            print(json.dumps(dict(completed_symbols=number+1, elapsed_seconds=time.monotonic()-started)), flush=True)
    out = pd.concat(outputs, ignore_index=True).sort_values('candidate_index').reset_index(drop=True)
    assert len(out) == 133713 and out.candidate_index.tolist() == list(range(133713)) and out[KEY].equals(primary[KEY])
    # Separate explicit primary-point check, not merely trusting full-grid check.
    joined = out.merge(old[KEY + list(own.E_COLUMNS)], on=KEY, how='left', suffixes=('_new', '_old'), validate='one_to_one')
    for field in own.E_COLUMNS:
        assert bits_equal(joined[field+'_new'], joined[field+'_old']), ('primary', field)
    out.to_parquet(HERE / 'DUAL_MEMORY_FEATURES.parquet', index=False, compression='zstd')
    pd.DataFrame(cases).to_parquet(HERE / 'FOUR_STOCK_63E_EVIDENCE.parquet', index=False, compression='zstd')
    save('PREFIX_CHECKS.json', prefixes)
    save('RUN_RECEIPT.json', dict(status='COMPLETE_ORIGINAL_E_DUAL_MEMORY_NO_SCORE_NO_ACCOUNT', rows=len(out), symbols=1660,
        known=int(out.dual_memory_status.eq('KNOWN').sum()), status_counts=dict(Counter(out.dual_memory_status)),
        fast_status_counts=dict(Counter(out.fast_status)), slow_status_counts=dict(Counter(out.slow_status)),
        fast_only_known=int((out.fast_status.eq('KNOWN') & out.slow_status.ne('KNOWN')).sum()),
        by_window={str(k):dict(Counter(g.dual_memory_status)) for k,g in out.groupby('window')},
        all_primary_six_scalar_columns_bitexact=True, all_export_comparable_cells_bitexact=dict(check),
        all_original_clock_fields_exact=True, true_truncated_prefix=prefixes, source_sha256=sources,
        outputs={n:dict(sha256=sha(HERE/n),rows=len(out) if n.startswith('DUAL') else len(cases)) for n in ['DUAL_MEMORY_FEATURES.parquet','FOUR_STOCK_63E_EVIDENCE.parquet']},
        definition=dict(E_fast='sum(k=0..4, .8**k * e[t-k]) / sum(k=0..4, .8**k)', E_slow='mean(e[t-62:t-5], 58 observations)',
                        known='Fast independently requires finite lag0..4; slow independently requires finite lag5..62 and all63 clock slots inside current original block; joint status never gates fast-only'),
        elapsed_seconds=time.monotonic()-started, new_accounts=0, new_scores=0, new_rankings=0, future_labels_read=False))
    print(json.dumps(dict(rows=len(out), known=int(out.dual_memory_status.eq('KNOWN').sum()), statuses=dict(Counter(out.dual_memory_status)), elapsed_seconds=time.monotonic()-started)), flush=True)


if __name__ == '__main__':
    main()
