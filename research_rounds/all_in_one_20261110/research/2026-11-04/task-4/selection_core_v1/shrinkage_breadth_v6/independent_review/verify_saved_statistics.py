"""Read-only aggregation/hash audit of saved v6 tables; no rank or label generation."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'reentry_v1/funding_agent/.python313_readers'))
import numpy as np
import pandas as pd

B = Path(__file__).resolve().parents[1]
O = Path(__file__).resolve().parent
D = B / 'diagnostics'


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def close(actual, expected):
    assert np.isclose(actual, expected, atol=1e-12, rtol=1e-12, equal_nan=True), (actual, expected)


daily = pd.read_parquet(D / 'DAILY_TAIL_EXPOSURE_COUNTS.parquet')
summary = pd.read_parquet(D / 'PATH_TAIL_EXPOSURE_BY_PERIOD_AND_N.parquet')
net = pd.read_parquet(D / 'ADDED_MINUS_REMOVED_TAIL_HITS.parquet')
assert len(daily) == 10850
assert not daily.duplicated(['date', 'method', 'stratum']).any()
assert daily.groupby(['method', 'stratum']).size().eq(1085).all()
assert daily.loc[daily.stratum.eq('ALL'), 'selected'].eq(3).all()
ints = ['selected', 'selected_label_known', 'hits', 'tailN_in_stratum']
wide = daily.set_index(['date', 'method', 'stratum'])[ints].unstack('stratum')
for c in ints:
    assert (wide[c]['N1'] + wide[c]['N2_TO10']).equals(wide[c]['SPARSE_N_LE10'])
    assert (wide[c]['SPARSE_N_LE10'] + wide[c]['DENSE_N_GT10']).equals(wide[c]['ALL'])

for r in summary.itertuples(index=False):
    assert r.grouping == 'study_window'
    a = daily.loc[daily.study_window.eq(r.period) & daily.method.eq(r.method) & daily.stratum.eq(r.stratum)]
    assert a.selected.sum() == r.industry_days
    assert a.selected_label_known.sum() == r.label20_known
    assert a.hits.sum() == r.tail_hits
    assert a.tailN_in_stratum.sum() == r.tailN_in_stratum
    assert a.tailN_all90.sum() == r.tailN_all90
    close(r.coverage_of_all90_tail, a.hits.sum() / a.tailN_all90.sum())
    close(r.coverage_within_stratum, a.hits.sum() / a.tailN_in_stratum.sum() if a.tailN_in_stratum.sum() else np.nan)
    close(r.precision, a.hits.sum() / a.selected_label_known.sum() if a.selected_label_known.sum() else np.nan)
    close(r.mean_daily_coverage_of_all90_tail, a.coverage_of_all90_tail.mean())
    close(r.mean_daily_coverage_within_stratum, a.coverage_within_stratum.mean())
    close(r.mean_daily_precision, a.precision.mean())

z = summary.set_index(['period', 'stratum', 'method'])
for r in net.itertuples(index=False):
    assert r.net_tail_hits == r.added_tail_hits - r.removed_tail_hits
    a, b = z.loc[(r.period, r.stratum, 'T0_ORIGINAL')], z.loc[(r.period, r.stratum, 'T10_KAPPA10')]
    assert r.net_tail_hits == b.tail_hits - a.tail_hits
    assert r.added - r.removed == b.industry_days - a.industry_days

old = json.loads((D / 'FIRST_EXECUTION_UNCHANGED_MAIN_AND_NET_CHECK.json').read_text())
main = summary.loc[summary.stratum.eq('ALL')].sort_values(['period', 'method']).reset_index(drop=True)
before = pd.DataFrame(old['main_stage_pooled_rows']).sort_values(['period', 'method']).reset_index(drop=True)
pd.testing.assert_frame_equal(before[main.columns], main, check_dtype=False, check_exact=True)
pd.testing.assert_frame_equal(pd.DataFrame(old['tail_net_rows']), net, check_dtype=False, check_exact=True)

manifest_checks = {}
for relative in ['features/SOURCE_SHA256.json', 'features/OUTPUT_SHA256.json', 'diagnostics/SOURCE_SHA256.json', 'diagnostics/OUTPUT_SHA256.json']:
    m = B / relative
    records = json.loads(m.read_text())
    for name, expected in records.items():
        p = Path(name)
        if not p.is_absolute():
            p = m.parent / p
        assert p.is_file() and sha(p) == expected, (relative, name)
    manifest_checks[relative] = {'entries_exact': len(records), 'manifest_sha256': sha(m)}

result = {
    'status': 'PASS_SAVED_STATISTICAL_IDENTITIES_AND_CURRENT_MANIFESTS',
    'scope': 'Stored-table aggregation, first/final result invariance and hashes only; no new feature, rank, label, model, account or threshold.',
    'daily_rows': len(daily),
    'each_method_stratum_full1085': True,
    'all_selected3_daily': True,
    'nested_strata_partition_identities': True,
    'summary_rows_checked': len(summary),
    'pooled_and_daily_denominators_and_means': True,
    'net_rows_checked': len(net),
    'net_equals_added_minus_removed_and_T10_minus_T0': True,
    'first_final_ALL_all_columns_and_all_net_columns_exact': True,
    'first_daily_rows': old['old_daily_rows'],
    'final_daily_rows': len(daily),
    'reporting_note': 'Both first and final daily row counts are 10850. Explicit empty-stratum handling is a rule correction, not evidence that this dataset gained rows.',
    'manifests': manifest_checks,
    'audit_script_sha256': sha(__file__),
    'table_sha256': {str(p.relative_to(B)): sha(p) for p in [D/'DAILY_TAIL_EXPOSURE_COUNTS.parquet', D/'PATH_TAIL_EXPOSURE_BY_PERIOD_AND_N.parquet', D/'ADDED_MINUS_REMOVED_TAIL_HITS.parquet']},
}
(O / 'SAVED_STATISTICAL_IDENTITIES.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
print(json.dumps(result, ensure_ascii=False))
