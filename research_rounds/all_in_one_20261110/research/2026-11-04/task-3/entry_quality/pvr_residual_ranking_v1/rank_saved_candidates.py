"""Frozen cross-sectional rank observation, not a strategy/account runner."""
from __future__ import annotations
import argparse
import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
SOURCE = HERE.parent / 'pvr_information_v1'
KEY = ['window', 'day', 'sid']
GROUP = ['window', 'day', 'sector']
TARGETS = ['000620.SZ', '300085.SZ', '300666.SZ', '301611.SZ', '603061.SH']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    with Path(path).open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')


def pct(x):
    """Tie-aware closed interval percentiles; no fictitious tie resolution."""
    if len(x) < 2:
        return pd.Series(np.nan, index=x.index)
    return (x.rank(method='average') - 1.) / (len(x) - 1.)


def isotonic_prediction(p, q):
    """Unweighted nondecreasing least squares, exact ties pooled first."""
    t = pd.DataFrame({'p': p, 'q': q}).groupby('p', sort=True).q.agg(['mean', 'size'])
    blocks = []
    for i, row in enumerate(t.itertuples()):
        blocks.append([i, i, float(row.mean) * int(row.size), int(row.size)])
        while len(blocks) > 1 and blocks[-2][2] / blocks[-2][3] > blocks[-1][2] / blocks[-1][3]:
            b = blocks.pop()
            a = blocks.pop()
            blocks.append([a[0], b[1], a[2] + b[2], a[3] + b[3]])
    pred = np.empty(len(t), float)
    for lo, hi, total, weight in blocks:
        pred[lo:hi + 1] = total / weight
    lookup = pd.Series(pred, index=t.index)
    return p.map(lookup).astype(float)


def score_group(g):
    p = pct(g.PVR_round12)
    q = pct(g.relative_return20)
    denominator = float(((p - p.mean()) ** 2).sum())
    if denominator <= 1e-15:
        return None
    unrestricted_beta = float(((p - p.mean()) * (q - q.mean())).sum() / denominator)
    b = max(0., unrestricted_beta)
    a = float(q.mean() - b * p.mean())
    residual = q - a - b * p
    residual_rank = pct(residual.round(12))
    high_rank = pct(g.close_gap_prior_high20)
    low_rank = pct(g.low_improvement)
    shape_raw = .5 * high_rank + .5 * low_rank
    shape = pct(shape_raw.round(12))
    iso = isotonic_prediction(p, q)
    iso_residual = q - iso
    out = pd.DataFrame({
        'p': p, 'q': q, 'OLS_prediction': a + b * p,
        'OLS_residual': residual, 'residual_percentile': residual_rank,
        'frontier_percentile': high_rank, 'low_percentile': low_rank,
        'structure_raw': shape_raw, 'structure_percentile': shape,
        'S': .5 * p + .3 * residual_rank + .2 * shape,
        'S_naive_RS': .5 * p + .3 * q + .2 * shape,
        'isotonic_prediction': iso, 'isotonic_residual': iso_residual,
        'isotonic_residual_percentile': pct(iso_residual.round(12)),
    }, index=g.index)
    out['S_isotonic'] = .5 * p + .3 * out.isotonic_residual_percentile + .2 * shape
    for name in ['S', 'S_naive_RS', 'S_isotonic']:
        ordering = g[['original_H1_rank', 'sid']].join(out[name]).sort_values(
            [name, 'original_H1_rank', 'sid'], ascending=[False, True, True]).index
        out.loc[ordering, name + '_common_rank'] = np.arange(1, len(g) + 1)
    meta = dict(n=int(len(g)), beta=b, unrestricted_beta=unrestricted_beta, intercept=a,
                rank_correlation=float(p.corr(q)),
                raw_residual_p_covariance=float(((p-p.mean())*(residual-residual.mean())).mean()),
                reranked_residual_p_correlation=float(p.corr(residual_rank)),
                residual_nunique=int(residual.round(12).nunique()),
                isotonic_residual_nunique=int(iso_residual.round(12).nunique()),
                same_RS20_anchor=bool(g.return20_anchor_day.nunique(dropna=False) == 1),
                n_RS20_anchors=int(g.return20_anchor_day.nunique(dropna=False)),
                source_PVR_round12_ties=int(len(g)-g.PVR_round12.nunique()),
                S_vs_isotonic_changed_rank=int((out.S_common_rank != out.S_isotonic_common_rank).sum()))
    return out, meta


def checks():
    p = pd.Series([0., 0., .5, 1.])
    assert np.allclose(pct(p), [1/6, 1/6, 2/3, 1.])
    p = pd.Series([0., .5, 1.])
    assert np.allclose(isotonic_prediction(p, pd.Series([0., 1., .5])), [0., .75, .75])
    assert np.allclose(isotonic_prediction(p, pd.Series([1., .5, 0.])), [.5, .5, .5])
    assert np.allclose(isotonic_prediction(pd.Series([0., 0., 1.]), pd.Series([0., 1., 1.])), [.5, .5, 1.])
    return {'tie_percentile': 'PASS', 'PAVA_monotone_violation': 'PASS', 'PAVA_tied_x': 'PASS'}


def execute(structure, out):
    started = time.monotonic()
    out.mkdir(parents=True, exist_ok=False)
    inputs = [Path(__file__), HERE/'FREEZE.json', SOURCE/'universe_audit/PRIMARY_CANDIDATES.jsonl',
              SOURCE/'universe_audit/PRIMARY_CANDIDATES_MANIFEST.json', SOURCE/'export/features.parquet',
              SOURCE/'export/FEATURE_MANIFEST_PRE_LABEL.json', Path(structure)]
    sources = {str(p.resolve()): sha(p) for p in inputs}
    save(out/'RUN_STARTED.json', dict(source_sha256=sources, new_accounts=0, order_generation=False,
                                    future_labels_loaded=False, automatic_retry=False))
    unit = checks()
    # stdlib parsing preserves the saved IEEE score; pandas' default fast JSON
    # float parser may move the last bit and must not be used for this check.
    with inputs[2].open() as stream:
        primary = pd.DataFrame(json.loads(line) for line in stream)
    assert len(primary) == 133713 and not primary.duplicated(KEY).any()
    fc = ['sid', 'day', 'window', 'sector', 'score', 'relative_return20', 'relative_return20_status',
          'close_gap_prior_high20', 'close_gap_prior_high20_status', 'return20_anchor_day',
          'aligned_sector_return_on_stock20_interval', 'return20']
    f = pd.read_parquet(SOURCE/'export/features.parquet', columns=fc)
    x = primary.merge(f, on=KEY, validate='one_to_one', how='left')
    ready = x.original_PVR_ready
    assert np.array_equal(x.loc[ready, 'original_PVR'].to_numpy(float), x.loc[ready, 'score'].to_numpy(float))
    assert np.isfinite(x.score).equals(ready)
    low = pd.read_parquet(structure)
    assert len(low) == 133713 and not low.duplicated(KEY).any()
    assert 'L' in low and 'low_improvement' not in low
    low = low.rename(columns={'L': 'low_improvement'})
    x = x.merge(low, on=KEY, how='left', validate='one_to_one', suffixes=('', '_low'))
    assert 'low_improvement' in x
    x['PVR_round12'] = x.score.round(12)
    x['common_valid'] = np.isfinite(x[['score', 'relative_return20', 'close_gap_prior_high20', 'low_improvement']]).all(axis=1)
    x['n_legal'] = x.groupby(GROUP).sid.transform('size')
    x['n_common'] = x.groupby(GROUP).common_valid.transform('sum')
    x['rank_status'] = np.where(x.common_valid, 'UNKNOWN_GROUP_N_LT10', 'UNKNOWN_INPUT')
    x['H1_sector_rank'] = x.groupby(GROUP).original_H1_slot.rank(method='first').astype(int)
    x['PVR_sector_rank'] = x.groupby(GROUP).original_PVR_slot.rank(method='first').astype(int)
    stats, frames = [], []
    for keys, g in x.loc[x.common_valid & x.n_common.ge(10)].groupby(GROUP, sort=True):
        result = score_group(g)
        if result is None:
            x.loc[g.index, 'rank_status'] = 'UNKNOWN_CONSTANT_PVR'
            continue
        frame, meta = result
        meta.update(dict(zip(GROUP, keys)))
        frames.append(frame)
        stats.append(meta)
        x.loc[g.index, 'rank_status'] = 'KNOWN'
    scores = pd.concat(frames).sort_index() if frames else pd.DataFrame(index=[])
    x = x.join(scores)
    x['hybrid_S_pending_slot'] = x.original_PVR_slot.astype(int)
    x['hybrid_S_isotonic_pending_slot'] = x.original_PVR_slot.astype(int)
    for _, g in x.loc[x.rank_status.eq('KNOWN')].groupby(GROUP, sort=False):
        slots = np.sort(g.original_PVR_slot.to_numpy(int))
        for name, dest in [('S', 'hybrid_S_pending_slot'), ('S_isotonic', 'hybrid_S_isotonic_pending_slot')]:
            order = g.sort_values([name, 'original_H1_rank', 'sid'], ascending=[False, True, True]).index
            x.loc[order, dest] = slots
    x['hybrid_S_sector_rank'] = x.groupby(GROUP).hybrid_S_pending_slot.rank(method='first').astype(int)
    x['hybrid_S_isotonic_sector_rank'] = x.groupby(GROUP).hybrid_S_isotonic_pending_slot.rank(method='first').astype(int)
    # This is a sidecar permutation only. Check fixed unknown slots and industry-slot conservation.
    for _, g in x.groupby(['window', 'day'], sort=False):
        assert sorted(g.hybrid_S_pending_slot) == sorted(g.original_PVR_slot)
    for _, g in x.groupby(GROUP, sort=False):
        assert sorted(g.hybrid_S_pending_slot) == sorted(g.original_PVR_slot)
    unknown = ~x.rank_status.eq('KNOWN')
    assert (x.loc[unknown, 'hybrid_S_pending_slot'] == x.loc[unknown, 'original_PVR_slot']).all()
    known = x.loc[~unknown]
    assert np.isfinite(known.S).all() and known.S.between(0, 1).all()
    groupstats = pd.DataFrame(stats)
    x.to_parquet(out/'ALL_ORIGINAL_CANDIDATES_WITH_RANKS.parquet', index=False)
    groupstats.to_csv(out/'FIT_GROUPS.csv', index=False)
    target = ((x.sid.eq('000620.SZ') & (x.day.between('2022-01-01', '2022-01-31') | x.day.eq('2022-09-28')))
              | (x.sid.eq('300085.SZ') & x.day.between('2024-09-12', '2024-10-31'))
              | (x.sid.isin(TARGETS[2:]) & x.window.eq('strong')))
    display = [*KEY, 'sector', 'roles', 'rank_status', 'n_legal', 'n_common', 'score', 'relative_return20',
               'return20_anchor_day', 'close_gap_prior_high20', 'low_improvement', 'p', 'q',
               'OLS_prediction', 'OLS_residual', 'residual_percentile', 'frontier_percentile',
               'low_percentile', 'structure_percentile', 'S', 'S_naive_RS', 'S_isotonic',
               'original_H1_slot', 'original_PVR_slot', 'original_H1_rank', 'original_PVR_priority_rank',
               'H1_sector_rank', 'PVR_sector_rank', 'S_common_rank', 'S_naive_RS_common_rank',
               'S_isotonic_common_rank', 'hybrid_S_pending_slot', 'hybrid_S_sector_rank',
               'hybrid_S_isotonic_pending_slot', 'hybrid_S_isotonic_sector_rank']
    x.loc[target, display].sort_values(['sid', 'day']).to_csv(out/'ALL_FIXED_TARGET_DATES.csv', index=False)
    case_groups = x.loc[target, GROUP].drop_duplicates()
    competitors = x.merge(case_groups, on=GROUP, how='inner', validate='many_to_one')
    competitors[display].sort_values([*GROUP, 'original_PVR_slot']).to_csv(out/'ALL_SAME_DAY_INDUSTRY_COMPETITORS.csv', index=False)
    freeze = json.loads((HERE/'FREEZE.json').read_text())
    earlykeys = set(freeze['early_table_dates'])
    early = x.loc[(x.sid+'|'+x.day).isin(earlykeys), display].sort_values(['sid','day'])
    early.to_csv(out/'EARLY_FIXED_CASE_TABLE.csv', index=False)
    coverage = {}
    for w, g in x.groupby('window'):
        fit = groupstats[groupstats.window.eq(w)]
        known_g = g[g.rank_status.eq('KNOWN')]
        coverage[w] = dict(legal_rows=len(g), unique_stocks=g.sid.nunique(), days=g.day.nunique(),
                           sector_day_groups=g.groupby(GROUP).ngroups,
                           rank_status_counts=g.rank_status.value_counts().to_dict(),
                           known_groups=len(fit), known_rows=len(known_g),
                           missing_RS20=int((~np.isfinite(g.relative_return20)).sum()),
                           missing_PVR=int((~np.isfinite(g.score)).sum()),
                           missing_low=int((~np.isfinite(g.low_improvement)).sum()),
                           fit_median_rank_correlation=float(fit.rank_correlation.median()),
                           fit_same_RS20_anchor_groups=int(fit.same_RS20_anchor.sum()),
                           fit_PVR_round12_tie_excess=int(fit.source_PVR_round12_ties.sum()),
                           reranked_residual_abs_p_corr_median=float(fit.reranked_residual_p_correlation.abs().median()),
                           S_vs_isotonic_changed_rows=int((known_g.S_common_rank != known_g.S_isotonic_common_rank).sum()),
                           S_vs_PVR_changed_rows=int((known_g.hybrid_S_pending_slot != known_g.original_PVR_slot).sum()))
    coverage['fixed_target_dates'] = dict(rows=int(target.sum()), known=int((target & ~unknown).sum()),
                                        missing_from_requested_early=sorted(earlykeys-set(early.sid+'|'+early.day)),
                                        competitor_rows=len(competitors))
    save(out/'COVERAGE_AND_FORM_RISK.json', coverage)
    save(out/'CHECKS.json', dict(pure_checks=unit, original_PVR_bitexact=True,
                                unique_candidate_rows=True, unknown_slots_fixed=True,
                                industry_slot_sets_preserved=True, all_pending_slot_sets_preserved=True,
                                no_future_labels_loaded=True, new_accounts=0))
    files = {p.name: sha(p) for p in out.iterdir() if p.is_file()}
    save(out/'COMPLETION.json', dict(status='COMPLETE_STATIC_RANK_OBSERVATION_ONLY',
                                     input_sha256=sources, output_sha256=files,
                                     elapsed_seconds=time.monotonic()-started, new_accounts=0))
    print(json.dumps(coverage, ensure_ascii=False, indent=2))
    print(early[['sid','day','rank_status','n_legal','score','relative_return20','p','residual_percentile',
                 'structure_percentile','S','H1_sector_rank','PVR_sector_rank','hybrid_S_sector_rank',
                 'S_isotonic_common_rank']].to_string(index=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--structure-input', required=True)
    parser.add_argument('--out', type=Path, default=HERE/'run_v1')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    if args.execute:
        execute(args.structure_input, args.out)
    else:
        print(json.dumps(checks(), indent=2))
