"""Read frozen market data and expose exact E0 events; no account simulation."""
from pathlib import Path
import concurrent.futures
import hashlib
import importlib.util
import json
import math
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1]
PREVIOUS = ROOT / 'research_rounds/s-amount-cross-sector-20261028'
EVIDENCE = ROOT / 'research_rounds/pv-strength-b5-20261025/code/evidence.py'
POLICY = ROOT / 'research_rounds/pv-strength-b5-20261025/code/policy.py'
ARITHMETIC = EVIDENCE.with_name('arithmetic.py')
sys.path.insert(0, str(EVIDENCE.parent))
from arithmetic import compare, higher

spec = importlib.util.spec_from_file_location('ph1_frozen_e0_evidence', EVIDENCE)
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def read(p):
    return json.loads(Path(p).read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def save(p, value):
    with Path(p).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


TECH = Path(read(ROOT / 'research_rounds/pvr-act-comparison-20261027/input.json')['snapshot']['path'])
DRUG = ROOT / 'research_rounds/innovative-drug-sfw3-20261028/prepared'
PREPS = {'TECH': TECH, 'DRUG': DRUG}
POOLS = {
    'TECH': ROOT / 'research_rounds/tech-compound-design-20261026/proposed-pool.csv',
    'DRUG': ROOT / 'research_rounds/innovative-drug-local-recovery-20261028/pool.csv',
}
CUTS = ('2024-12-31', '2026-06-30')


def events(f):
    parts = []
    for segment, g in f.groupby('segment_id', sort=False):
        z, _ = ev._event_facts(g)
        z = z[['event', 'confirmed_pivot_price', 'confirmed_pivot_date']].rename(
            columns={'confirmed_pivot_price': 'pivot', 'confirmed_pivot_date': 'pivot_date'})
        z['close'] = g.close
        z['segment_id'] = g.segment_id
        parts.append(z)
    if parts:
        return pd.concat(parts).sort_index()
    return pd.DataFrame({
        'event': pd.Series(dtype=float), 'pivot': pd.Series(dtype=float),
        'pivot_date': pd.Series(dtype='string'), 'close': pd.Series(dtype=float),
        'segment_id': pd.Series(dtype=f.segment_id.dtype)}, index=f.index)


def reconstruct_nr1(f, z):
    """Independent state reducer: exit first, then original upward confirmation.

    Mirrors the frozen policy with decline_candidate=False; does not infer
    events from a floor change and never creates the removed reclaim branch.
    """
    result = []
    for _, g in f.groupby('segment_id', sort=False):
        active, floor = False, math.nan
        for t, c in g.close.items():
            exited = False
            if active and compare(float(c), floor) <= 0:
                active, exited = False, True
            if z.at[t, 'event'] == 1:
                pivot = float(z.at[t, 'pivot'])
                if active:
                    floor = higher(floor, pivot)
                elif not exited:
                    active, floor = True, pivot
            result.append((t, int(active), floor if active or exited else math.nan))
    return pd.DataFrame(result, columns=['date', 'target', 'floor']).set_index('date')


def job(task):
    sector, sid = task
    sp, fp = PREPS[sector] / 'signals' / f'{sid}.parquet', PREPS[sector] / 'facts' / f'{sid}.parquet'
    signal, facts = pd.read_parquet(sp), pd.read_parquet(fp)
    assert signal.index.is_unique and signal.index.is_monotonic_increasing, (sector, sid, 'signal_clock')
    assert facts.index.is_unique and facts.index.is_monotonic_increasing, (sector, sid, 'fact_clock')
    assert facts.index.difference(signal.index).empty, (sector, sid, 'missing_real_observation')
    excluded = signal.loc[signal.index.difference(facts.index)]
    assert excluded.empty or (excluded.synthetic_event_bar.astype(bool) & ~excluded.observed_bar.astype(bool)).all(), (sector, sid, 'unexplained_exclusion')
    f = signal.reindex(facts.index)
    np.testing.assert_array_equal(f.segment_id.to_numpy(), facts.segment_id.to_numpy(), err_msg=sid + '/segment')
    np.testing.assert_allclose(f.close, facts.close, rtol=0, atol=0, equal_nan=True, err_msg=sid + '/close')
    assert np.isfinite(f[['close', 'amount']].to_numpy(float)).all() and f[['close', 'amount']].gt(0).all().all(), (sector, sid, 'close_amount')
    z = events(f)
    rebuilt = reconstruct_nr1(f, z)
    np.testing.assert_array_equal(rebuilt.target.to_numpy(), facts.e0_target.to_numpy(), err_msg=sid + '/e0_target')
    np.testing.assert_allclose(rebuilt.floor, facts.e0_floor, rtol=0, atol=0, equal_nan=True, err_msg=sid + '/e0_floor')
    count = 0
    for cut in CUTS:
        # Rerun the pure kernel from a physically truncated input frame.
        short = events(f.loc[:cut].copy())
        pd.testing.assert_frame_equal(short, z.loc[:cut], check_exact=True)
        count += len(short)
    confirmed = z.loc[z.event.ne(0)]
    assert confirmed['pivot'].notna().all() and confirmed['pivot_date'].notna().all()
    for t, r in confirmed.iterrows():
        pivot_at = pd.Timestamp(r.pivot_date)
        assert pivot_at < t, (sector, sid, 'future_or_current_pivot')
        assert f.at[pivot_at, 'segment_id'] == r.segment_id
        assert float(f.at[pivot_at, 'close']) == float(r['pivot']), (sector, sid, 'not_closing_pivot')
    path = OUT / 'events' / sector / f'{sid}.parquet'
    assert not path.exists(), path
    z.to_parquet(path)
    return {
        'sector': sector, 'symbol': sid, 'rows': len(z),
        'source_segments': int(f.segment_id.nunique()),
        'excluded_synthetic_bridge_rows': len(excluded),
        'up_events': int(z.event.eq(1).sum()), 'down_events': int(z.event.eq(-1).sum()),
        'prefixes': len(CUTS), 'prefix_rows': count,
        'e0_target_exact': True, 'e0_floor_exact': True,
        'inputs': {str(sp): sha(sp), str(fp): sha(fp)}, 'output': str(path), 'output_sha256': sha(path),
    }


def main():
    sources = {str(p): sha(p) for p in [EVIDENCE, POLICY, ARITHMETIC, ROOT / 'TradingAlarm/desk/refresh.py', Path(__file__)]}
    for sector in PREPS:
        assert read(PREVIOUS / f'signal-validation-{sector}.json')['passed']
        (OUT / 'events' / sector).mkdir(parents=True, exist_ok=False)
    records = []
    tasks = [(s, sid) for s in PREPS for sid in pd.read_csv(POOLS[s]).symbol]
    assert len(tasks) == 455
    try:
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as pool:
            for r in pool.map(job, tasks):
                records.append(r)
                print(r['sector'], r['symbol'], r['rows'], flush=True)
        assert all(sha(p) == h for p, h in sources.items()), 'source_changed_during_preparation'
        save(OUT / 'event-validation.json', {
            'passed': True, 'stocks': len(records), 'rows': sum(r['rows'] for r in records),
            'prefixes': sum(r['prefixes'] for r in records), 'prefix_rows': sum(r['prefix_rows'] for r in records),
            'exact_e0_target_and_floor': len(records), 'cuts': CUTS,
            'source_sha256': sources, 'records': records,
            'interface': 'evidence._event_facts(signal.reindex(facts.index), separately per segment_id)',
            'column_mapping': {'event': 'event', 'pivot': 'confirmed_pivot_price', 'pivot_date': 'confirmed_pivot_date'},
            'event_time': 'row index is confirmation date; pivot_date is prior closing observation date, not intraday low or download observed_at',
            'no_forward_fill': True, 'no_account_run': True, 'frozen_sources_unchanged': True,
        })
    except Exception as exc:
        save(OUT / 'event-preparation-failure.json', {'passed': False, 'error': repr(exc), 'source_sha256': sources, 'completed_records': records})
        raise


if __name__ == '__main__':
    main()
