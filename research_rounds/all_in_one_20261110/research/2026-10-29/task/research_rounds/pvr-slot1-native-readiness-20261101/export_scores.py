"""Only the frozen original PVR, full warm history; no account or price labels."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, time, gzip, shutil
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
W = O.parent
P = W/'pvr-current-v3-information-capital-20261101'
FORMULA = P/'original_score_function.py'
EXPECTED = '9328109bada26c53b04cf0f3e84d719917cb528ff8608b3e9faa5d1c55ba8cb2'
WINDOWS = [('2022-01-01', '2022-12-30'), ('2025-07-01', '2026-06-30')]

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p, x):
    p = Path(p); p.parent.mkdir(parents=True, exist_ok=True)
    t = p.with_name(p.name+'.tmp')
    t.write_text(json.dumps(x, ensure_ascii=False, indent=2, allow_nan=False)+'\n'); t.replace(p)

def original():
    assert sha(FORMULA) == EXPECTED
    env = dict(np=np, pd=pd)
    exec(compile(FORMULA.read_text(), str(FORMULA), 'exec'), env)
    return env['score']

def main():
    begin = time.monotonic(); score = original()
    calendars = {}
    for win, root in [('2022', W/'2022-normal-reference-20261031/runs/B_diag/pair'),
                      ('2025_26', W/'q2-normal-continuation-20261031/runs/B_diag/pair')]:
        p = root/'daily.jsonl.gz'
        with gzip.open(p, 'rt') as f:
            ds = [json.loads(line)['at'][:10] for line in f]
        assert len(ds) == len(set(ds)) == 242
        calendars[win] = dict(dates=ds, source=str(p), source_sha256=sha(p))
    dates = pd.DatetimeIndex([d for v in calendars.values() for d in v['dates']], name='day')
    manifest_path = W/'universe-cp1-inputs-20261031/STOCK_MANIFEST.json'
    records = json.loads(manifest_path.read_text())
    assert len(records) == 1709
    previous = O/'SCORES_MANIFEST.json'
    prior = json.loads(previous.read_text()) if previous.exists() else {}
    archive_manifest = O/'preflight-development-v1/SCORES_MANIFEST.json'
    if not prior.get('physical_future_prefix_checks') and archive_manifest.exists():
        prior = json.loads(archive_manifest.read_text())
    roots = []; prefixes = prior.get('physical_future_prefix_checks', [])
    old_points = 0; old_byte_checks = 0; numeric_recomputations = 0
    for n, r in enumerate(records, 1):
        sid = r['symbol']
        source, source_hash = next((Path(p), h) for p, h in r['source_sha256'].items() if p.endswith('/signal.parquet'))
        assert sha(source) == source_hash, ('original source changed', sid)
        out = O/'scores'/f'{sid}.parquet'; meta = out.with_suffix('.json')
        legacy = P/'pvr-cache'/f'{sid}.parquet'
        legacy_hash = sha(legacy) if legacy.exists() else None
        if meta.exists():
            m = json.loads(meta.read_text())
            assert m['source_sha256'] == source_hash and m['formula_sha256'] == EXPECTED
            assert m['windows'] == [list(x) for x in WINDOWS] and sha(out) == m['output_sha256']
            assert m['legacy_cache_sha256'] == legacy_hash
            if not m.get('explicit_full_market_decision_calendar'):
                # Reindex the completed identical score export, no score recomputation.
                archive = O/'preflight-development-v1/scores'; archive.mkdir(exist_ok=True)
                shutil.copy2(out, archive/out.name); shutil.copy2(meta, archive/meta.name)
                keep = pd.read_parquet(out).reindex(dates)
                tmp = out.with_name(out.name+'.tmp'); keep.to_parquet(tmp); tmp.replace(out)
                m.update(source_observation_export_sha256=m['output_sha256'],
                         explicit_full_market_decision_calendar=True, output_rows=len(keep),
                         ready=int(keep.score.notna().sum()), NA=int(keep.score.isna().sum()),
                         output_sha256=sha(out))
                save(meta, m)
        else:
            numeric_recomputations += 1
            f = pd.read_parquet(source).loc[:'2026-06-30']
            z = score(f)
            if legacy.exists():
                old = pd.read_parquet(legacy)
                pd.testing.assert_frame_equal(z.reindex(old.index), old, check_exact=True, check_freq=False)
                assert sha(legacy) == legacy_hash
            keep = z[['score']].reindex(dates)
            out.parent.mkdir(parents=True, exist_ok=True)
            tmp = out.with_name(out.name+'.tmp'); keep.to_parquet(tmp); tmp.replace(out)
            m = dict(symbol=sid, source=str(source), source_sha256=source_hash,
                     formula_sha256=EXPECTED, windows=[list(x) for x in WINDOWS],
                     source_full_warm_start=str(f.index.min()) if len(f) else None,
                     source_rows=len(f), output_rows=len(keep), ready=int(keep.score.notna().sum()),
                     NA=int(keep.score.isna().sum()), output_sha256=sha(out),
                     explicit_full_market_decision_calendar=True,
                     legacy_cache_sha256=legacy_hash,
                     old_all_eight_columns_exact=True if legacy.exists() else None,
                     old_points=len(old) if legacy.exists() else 0)
            save(meta, m)
            if n in (1, 500, 1000, 1500):
                cut = '2025-07-02'
                small = score(f.loc[:cut])
                pd.testing.assert_frame_equal(small, z.loc[:cut], check_exact=True, check_freq=False)
                changed = f.copy()
                changed.loc[changed.index > cut, 'close'] *= 7
                changed.loc[changed.index > cut, 'amount'] *= .013
                pd.testing.assert_frame_equal(score(changed).loc[:cut], z.loc[:cut], check_exact=True, check_freq=False)
                prefixes.append(dict(sid=sid, cut=cut, physical_prefix_exact=True, future_price_amount_perturbation_exact=True))
        old_points += m['old_points']; old_byte_checks += int(legacy.exists()); roots.append(m)
        if n % 250 == 0:
            save(O/'EXPORT_PROGRESS.json', dict(completed=n, seconds=time.monotonic()-begin, formula_sha256=EXPECTED))
            print('SCORE_EXPORT', n, '/', len(records), round(time.monotonic()-begin, 2), flush=True)
    assert old_points == 29938, old_points
    save(O/'SCORES_MANIFEST.json', dict(at=datetime.now(timezone.utc).isoformat(),
         fixed_stock_ids=[r['symbol'] for r in records], stocks=1709,
         original_stock_manifest_sha256=sha(manifest_path), formula_sha256=EXPECTED,
         windows=WINDOWS, decision_calendars=calendars, explicit_stock_date_cells=1709*len(dates),
         entries=roots, old_cache_byte_identity_files=old_byte_checks,
         old_all_eight_column_points_exact=old_points, physical_future_prefix_checks=prefixes,
         seconds=time.monotonic()-begin, original_PVR_numeric_functions_called_this_pass=numeric_recomputations,
         initial_original_PVR_generation_seconds=prior.get('initial_original_PVR_generation_seconds', prior.get('seconds')),
         recomputed_I_CP1_stage=0, accounts_advanced=0,
         scoring_scope='same original PVR function, exported full native potential dates, source invalids stay NA'))
    print('SCORES_DONE', len(roots), 'old points', old_points, round(time.monotonic()-begin, 2), flush=True)

if __name__ == '__main__':
    try: main()
    except BaseException as e:
        save(O/'failure/SCORE_EXPORT_ERROR.json', dict(type=type(e).__name__, reason=str(e), new_account_paths=0))
        raise
