"""One bounded, frozen, zero-account feature verification run."""
from pathlib import Path
import importlib.util, json, hashlib, time, math
from collections import Counter
import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
M = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(n, v): (O/n).write_text(json.dumps(v, ensure_ascii=False, indent=2, allow_nan=False)+'\n')

def main():
    start = time.monotonic()
    assert not (O/'FEATURE_VERIFICATION_RESULTS.json').exists(), 'no automatic repeat'
    freeze = json.loads((O/'FEATURE_PRE_RUN_FREEZE.json').read_text())
    for p, h in freeze['source_SHA256'].items(): assert sha(p) == h, p
    spec = importlib.util.spec_from_file_location('bounded_confirmation_features', O/'compute_flags.py')
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    records = json.loads(M.read_text()); manifest = {r['symbol']: r for r in records}
    coverage = Counter(); checked = {}; empty = []
    # Only file existence and SHA here: no full-universe feature calculation.
    for r in records:
        coverage[r['status']] += 1
        if r['status'] != 'complete':
            empty.append(dict(symbol=r['symbol'], status=r['status'], feature='UNKNOWN_NO_SOURCE'))
            continue
        fp = Path(r['refs']['facts'])
        sp = next(Path(p) for p in r['source_sha256'] if p.endswith('/signal.parquet'))
        for p, expected in [(fp, r['output_sha256'][str(fp)]), (sp, r['source_sha256'][str(sp)])]:
            actual = sha(p); assert actual == expected, str(p); checked[str(p)] = actual
    real = []; prefixes = []
    for sid in freeze['sample']:
        r = manifest[sid]; fp = Path(r['refs']['facts'])
        sp = next(Path(p) for p in r['source_sha256'] if p.endswith('/signal.parquet'))
        f = pd.read_parquet(fp, columns=['close','segment_id','raw_close','factor'])
        z = pd.read_parquet(sp, columns=['close','segment_id','price_eligible','observed_bar','synthetic_event_bar']).loc[:f.index[-1]]
        assert z.index.equals(f.index), sid
        np.testing.assert_array_equal(z.close.to_numpy(), f.close.to_numpy())
        np.testing.assert_array_equal(z.segment_id.to_numpy(), f.segment_id.to_numpy())
        def mask(v): return (v.price_eligible & v.observed_bar & ~v.synthetic_event_bar).astype('boolean')
        known = mask(z); full = mod.compute_flags(f, price_observed=known, debug=True)
        for cut in freeze['prefix_cuts']:
            # Physically cut both native facts and eligibility source before compute.
            ff = f.loc[:cut].copy(); zz = z.loc[:cut].copy()
            got = mod.compute_flags(ff, price_observed=mask(zz), debug=True)
            pd.testing.assert_frame_equal(got, full.loc[:cut], check_exact=True, check_freq=False)
            prefixes.append(dict(symbol=sid, cut=cut, rows=len(ff), exact=True))
        real.append(dict(symbol=sid, rows=len(f), original_observation_index_exact=True,
                         invalid_or_synthetic_native_slots=int((~known.fillna(False)).sum()),
                         A_known=int(full.A_known.sum()), B_known=int(full.B_known.sum()),
                         A_true=int(full.A.fillna(False).sum()), B_true=int(full.B.fillna(False).sum())))
    # Hand-formula and continuity properties, not account/return tests.
    ix = pd.date_range('2000-01-01', periods=180)
    def frame(c): return pd.DataFrame(dict(close=c, raw_close=c, factor=1., segment_id=0), index=ix)
    obs = pd.Series(True, index=ix)
    flat = mod.compute_flags(frame(np.full(180, 100.)), price_observed=obs, debug=True)
    assert not flat.A.fillna(False).any() and not flat.B.fillna(False).any()
    assert flat.A_known.iloc[:64].sum() == 0 and flat.A_known.iloc[64]
    assert flat.B_known.iloc[:20].sum() == 0 and flat.B_known.iloc[20]
    c = np.arange(180, dtype=float)+100.; c[75] += 15.
    normal = mod.compute_flags(frame(c), price_observed=obs, debug=True)
    ema = c[0]
    ref = []
    for value in c:
        if ref: ema = (2./11.)*value + (9./11.)*ema
        ref.append(ema)
    np.testing.assert_allclose(normal.EMA10.iloc[9:], np.asarray(ref[9:]), rtol=0, atol=1e-12)
    for t in [64,75,100,179]:
        ma = math.fsum(c[t-59:t+1])/60.
        mid = math.fsum(c[t-19:t+1])/20.
        upper = mid + 2.*math.sqrt(math.fsum((v-mid)**2 for v in c[t-19:t+1])/20.)
        assert abs(normal.MA60.iloc[t]-ma) < 1e-12
        assert abs(normal.BB_upper.iloc[t]-upper) < 1e-10
    missing = frame(c); missing.loc[ix[80], 'close'] = np.nan
    gap = mod.compute_flags(missing, price_observed=obs, debug=True)
    assert not gap.price_known.iloc[80]
    assert not gap.B_known.iloc[80:101].any() and gap.B_known.iloc[101]
    assert not gap.A_known.iloc[80:145].any() and gap.A_known.iloc[145]
    rejected = obs.copy(); rejected.iloc[80] = False
    pd.testing.assert_frame_equal(gap, mod.compute_flags(frame(c), price_observed=rejected, debug=True), check_exact=True)
    changed = frame(c); changed.loc[ix[80]:,'segment_id'] = 1
    seg = mod.compute_flags(changed, price_observed=obs, debug=True)
    assert not seg.B_known.iloc[80:100].any() and seg.B_known.iloc[100]
    assert not seg.A_known.iloc[80:144].any() and seg.A_known.iloc[144]
    for p, h in freeze['source_SHA256'].items(): assert sha(p) == h, p
    for p, h in checked.items(): assert sha(p) == h, p
    seconds = time.monotonic()-start
    assert seconds <= freeze['compute_seconds_budget'], seconds
    save('FEATURE_COVERAGE_AND_SOURCE_SHA.json',dict(status_counts=dict(coverage),
         stock_identities=len(records), full_universe_features_computed=False,
         complete_sources_SHA256=checked, unknown_identity_records=empty))
    save('FEATURE_VERIFICATION_RESULTS.json',dict(passed=True,seconds=seconds,
         real=real, physical_prefix_checks=prefixes, synthetic_checks=[
         'equal_price_zero_slope','independent_EMA_recursion','independent_MA_BB_arithmetic',
         'unknown_slot_rewarms_without_compression','ineligible_slot_same_unknown_behavior',
         'source_boundary_rewarms'], new_accounts=0, full_universe_feature_exports=0,
         no_native_integration=True, params=mod.PARAMS))
    print(json.dumps(dict(passed=True,seconds=seconds, real=real,
                         physical_prefixes=len(prefixes), universe=len(records)), ensure_ascii=False))

if __name__ == '__main__': main()
