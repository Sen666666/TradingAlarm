"""Copy already-frozen price inputs and make the two masks explicit. No fetch."""
import importlib.util
import numpy as np
import pandas as pd
from common import HERE, REPO, sha, read, write, now, old_identity

def main():
    identity = old_identity()
    write(HERE / 'validation/before-identity.json', identity)
    assert identity['passed']
    out = HERE / 'inputs'
    out.mkdir(exist_ok=False)
    rows = []
    columns = ['open', 'high', 'low', 'close', 'volume', 'segment_id',
               'valid_price_observation', 'valid_strength_observation']

    def save(identifier, group, f, sources, **extra):
        target = out / (identifier + '.parquet')
        f.index.name = 'date'
        f[columns].to_parquet(target)
        rows.append(dict(id=identifier, group=group, file=str(target.relative_to(HERE)),
                         sha256=sha(target), rows=len(f),
                         price_observations=int(f.valid_price_observation.sum()),
                         strength_observations=int(f.valid_strength_observation.sum()),
                         first=str(f.index[0].date()), last=str(f.index[-1].date()),
                         source_files={str(p.relative_to(REPO)): sha(p) for p in sources}, **extra))

    b1 = REPO / 'research_rounds/pv-strength-20261025'
    b4 = REPO / 'research_rounds/pv-strength-b4-20261025'
    ids = ['AU0', '518880', '512480', '001309.SZ', '688981.SH', '600036.SH', '600519.SH']
    for sid in ids:
        p = b1 / 'inputs' / (sid + '.parquet')
        f = pd.read_parquet(p)
        # This is precisely the old seven-asset comparison adapter, not a
        # claim that the canonical E0 core rejects missing volume prices.
        f['valid_price_observation'] = f.valid_strength_observation.copy()
        legacy = b4 / 'results' / (sid + '.parquet')
        save(sid, 'same_seven_original_adapter', f, [p, legacy],
             old_b4_path=str(legacy.relative_to(REPO)),
             old_e0_path=str(legacy.relative_to(REPO)), old_e0_prefix='e0_',
             mask_reason='Preserve the frozen seven-asset comparison clock; AU0 excludes its three old zero-volume rows.')

    old = REPO / 'research_rounds/pv-participation-response-20261020'
    source = old / 'prepared/source-precision-v1'
    manifest_path = source / 'manifest.json'
    manifest = read(manifest_path)
    mask_path = source / 'observation-mask-addendum.json'
    assert sha(mask_path) == manifest['copied_files']['observation-mask-addendum.json']['sha256']
    masks = {row['symbol']: row for row in read(mask_path)['series']}
    helper = old / 'code/data_utils.py'
    spec = importlib.util.spec_from_file_location('b5_legacy_input_adapter', helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    selected = [record for record in manifest['series'] if not record['symbol'].startswith('HK')]
    assert len(selected) == 8
    for record in selected:
        p = source / record['file']
        assert sha(p) == record['sha256'], p
        raw = pd.read_csv(p, index_col='date', parse_dates=True, float_precision='round_trip')
        sid = record['symbol']
        f = module.eligible_prices(raw, sid, masks[sid]['exclude_price_dates'])
        assert len(f) == record['price_observed_rows']
        f['segment_id'] = 0
        f['valid_price_observation'] = True
        f['valid_strength_observation'] = np.isfinite(f.volume) & f.volume.gt(0)
        save('legacy_' + sid, 'original_e0_price_adapter', f,
             [p, manifest_path, mask_path, helper],
             mask_reason='Original eligible_prices and saved exclusions; preserve valid prices even when volume is missing.')
    write(out / 'manifest.json', dict(recorded_at=now(), series=rows, network_requests=0,
                                      current_seven=7, original_e0_non_hk=8,
                                      history='seen_development_not_independent_samples',
                                      preparation_sha256=sha(__file__)))
    print({'series': len(rows), 'rows': sum(x['rows'] for x in rows),
           'price_observations': sum(x['price_observations'] for x in rows),
           'strength_observations': sum(x['strength_observations'] for x in rows)}, flush=True)

if __name__ == '__main__':
    main()
