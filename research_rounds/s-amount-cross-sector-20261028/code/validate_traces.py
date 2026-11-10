"""Independently audit stored S-AMT1 traces; no model or account execution."""
from __future__ import annotations

from collections import Counter
import math
import traceback

from sa_common import O, ROOT, FORM, PREPS, pool, read, save, sha, pd, np


EPS = np.finfo(np.float64).eps / 2
GAMMA4 = 4 * EPS / (1 - 4 * EPS)


def order(a, b):
    a, b = float(a), float(b)
    assert math.isfinite(a) and math.isfinite(b) and min(a, b) >= 0
    return 0 if abs(a - b) <= GAMMA4 * max(a, b) else (1 if a > b else -1)


def close(actual, expected, label):
    assert math.isclose(float(actual), float(expected), rel_tol=2e-12, abs_tol=2e-13), (
        label, actual, expected)


def audit_stock(sector, sid):
    signal_path = PREPS[sector] / 'signals' / f'{sid}.parquet'
    facts_path = PREPS[sector] / 'facts' / f'{sid}.parquet'
    output_path = O / 'signals' / sector / f'{sid}.parquet'
    signal, facts, z = [pd.read_parquet(p) for p in [signal_path, facts_path, output_path]]
    assert facts.index.isin(signal.index).all() and z.index.equals(facts.index), (sector, sid, 'index')
    excluded = signal.index.difference(facts.index)
    for day in excluded:
        row = signal.loc[day]
        assert bool(row.synthetic_event_bar) and not bool(row.observed_bar) and pd.isna(row.amount), (
            sector, sid, day, 'only explicit non-observation bridge rows may be excluded')
    signal = signal.reindex(facts.index)
    assert signal.observed_bar.astype(bool).all() and not signal.synthetic_event_bar.astype(bool).any()
    assert signal.segment_id.equals(z.segment_id), (sector, sid, 'segments')
    assert z.original_buy.equals(facts.i_buy.astype(bool).rename('original_buy'))
    np.testing.assert_array_equal(z.strict_buy.to_numpy(), (facts.i_buy.astype(bool) & z.strict_target).to_numpy())
    ready = z.loc[z.ready]
    assert ((ready.weight > 0) & (ready.weight <= 1)).all(), (sector, sid, 'weight')
    assert (ready.credit >= 0).all() and (ready.frontier >= 0).all()
    assert (ready.credit <= ready.frontier + 2e-13).all(), (sector, sid, 'credit bound')
    counts = Counter(rows=len(z), ready_rows=len(ready), buy_days=int(z.strict_buy.sum()),
                     excluded_synthetic_non_observations=len(excluded))
    for _, bars in signal.groupby('segment_id', sort=False):
        trace = z.loc[bars.index]
        dates = [str(day.date()) for day in bars.index]
        prices, amounts = bars.close.to_numpy(float), bars.amount.to_numpy(float)
        assert np.isfinite(prices).all() and (prices > 0).all()
        assert np.isfinite(amounts).all() and (amounts > 0).all()
        # Independent log arithmetic is compared within a numerical tolerance;
        # exact scalar ordering is retained for policy transitions.
        returns = np.r_[np.nan, np.log(prices[1:] / prices[:-1])]
        active, floor = False, math.nan
        direction, anchor = -1, None
        frontier, credit = 0., 0.
        anchor_cache = {}
        for i, row in enumerate(trace.itertuples()):
            ctx = (sector, sid, dates[i])
            assert row.ready == (i >= 64), (ctx, 'preparation')
            if i < 64:
                assert row.event == 0 and not row.strict_target and not row.strict_exited
                assert math.isnan(row.strict_floor)
                continue
            new_extreme = anchor is None or (direction == -1 and order(prices[i], prices[anchor]) < 0) or (direction == 1 and order(prices[i], prices[anchor]) > 0)
            if new_extreme:
                anchor, frontier, credit = i, 0., 0.
                counts['new_extreme_resets'] += 1
            else:
                counts['same_anchor_recurrences'] += 1
            d = -direction
            assert row.candidate_direction == d and row.anchor_date == dates[anchor], (ctx, 'causal anchor')
            close(row.anchor_price, prices[anchor], (ctx, 'anchor price'))
            if anchor not in anchor_cache:
                s = max(math.sqrt(math.fsum(float(r) ** 2 for r in returns[anchor - 63:anchor]) / 63), 1e-8)
                b = float(np.median(amounts[anchor - 21:anchor]))
                anchor_cache[anchor] = (s, b, 1.5 * math.sqrt(5) * s)
            scale, baseline, threshold = anchor_cache[anchor]
            close(row.scale, scale, (ctx, 'frozen scale'))
            close(row.amount_baseline, baseline, (ctx, 'frozen amount baseline'))
            close(row.threshold, threshold, (ctx, 'frozen threshold'))
            x = d * math.log(prices[i] / prices[anchor])
            close(row.displacement, x, (ctx, 'actual displacement'))
            # Use the stored displacement after independently checking it, to
            # avoid mistaking log/log1p last-bit differences for event changes.
            x = float(row.displacement)
            fresh = order(max(0., x), frontier) > 0
            delta = x - frontier if fresh else 0.
            weight = min(1., math.sqrt(amounts[i] / baseline))
            close(row.delta_frontier, delta, (ctx, 'new frontier increment'))
            close(row.weight, weight, (ctx, 'weight'))
            q = math.fsum((credit, delta * weight))
            next_f = x if fresh else frontier
            close(row.frontier, next_f, (ctx, 'frontier recurrence'))
            close(row.credit, q, (ctx, 'credit recurrence'))
            close(row.confirmation, row.credit / row.threshold, (ctx, 'confirmation'))
            if not fresh:
                assert row.credit == credit, (ctx, 'no new price must add no credit')
                counts['zero_increment_no_credit'] += 1
            should_confirm = fresh and order(max(0., x) / row.threshold, 1.) >= 0 and order(row.credit / row.threshold, 1.) >= 0
            assert row.event == (d if should_confirm else 0), (ctx, 'confirmation contract')
            exited = active and order(prices[i], floor) <= 0
            if exited:
                active = False
            if row.event:
                counts['up_events' if row.event == 1 else 'down_events'] += 1
                assert row.delta_frontier > 0 and row.pivot_date == dates[anchor]
                close(row.pivot, prices[anchor], (ctx, 'confirmed pivot'))
                if row.event == 1:
                    if active:
                        floor = max(floor, prices[anchor])
                    elif not exited:
                        active, floor = True, prices[anchor]
                direction, anchor, frontier, credit = row.event, i, 0., 0.
                assert row.next_frontier == 0 and row.next_credit == 0
                counts['confirmation_resets'] += 1
            else:
                frontier, credit = float(row.frontier), float(row.credit)
            assert row.next_anchor_date == dates[anchor] and row.next_leg_direction == direction, (ctx, 'post-event direction')
            close(row.next_frontier, frontier, (ctx, 'post-event frontier'))
            close(row.next_credit, credit, (ctx, 'post-event credit'))
            assert row.strict_target == active and row.strict_exited == exited, (ctx, 'old S policy order')
            if active or exited:
                assert row.strict_floor == floor, (ctx, 'old S support policy')
            else:
                assert math.isnan(row.strict_floor), (ctx, 'inactive hidden floor')
            counts['state_rows'] += 1
    return counts


def main():
    registry = read(FORM / 'registry.json')
    for name, expected in registry['source_sha256'].items():
        assert sha(ROOT / name) == expected, name
    totals, by_sector = Counter(), {}
    for sector in ['TECH', 'DRUG']:
        tally = Counter()
        for sid in pool(sector).symbol:
            tally.update(audit_stock(sector, sid))
            tally['stocks'] += 1
            if tally['stocks'] % 50 == 0:
                print(sector, tally['stocks'], flush=True)
        by_sector[sector] = dict(tally)
        totals.update(tally)
    partial = []
    for p in sorted((O / 'signals-partial-v1/TECH').glob('*.parquet')):
        final = O / 'signals/TECH' / p.name
        pd.testing.assert_frame_equal(pd.read_parquet(p), pd.read_parquet(final), check_exact=True)
        partial.append({'symbol': p.stem, 'rows': len(pd.read_parquet(p)),
                        'partial_sha256': sha(p), 'final_sha256': sha(final),
                        'all_values_and_dtypes_exact': True})
    assert partial, 'Expected preserved failed-prefix preparation outputs'
    save(O / 'trace-validation.json', {
        'passed': True, 'independent_stored_trace_audit': True,
        'totals': dict(totals), 'sectors': by_sector,
        'original_buy_intersection_exact': True,
        'original_S_policy_reconstruction_exact': True,
        'all_confirmations_have_new_price_and_two_thresholds': True,
        'model_hashes_match_frozen_registry': True,
        'preserved_partial_outputs': partial,
        'preserved_partial_rows': sum(r['rows'] for r in partial),
        'preparation_failure': 'v1 empty prefix segment_id metadata dtype only; all preserved nonempty tables exactly match final values and dtypes',
        'audit_failure': 'initial checker incorrectly required synthetic bridge dates to occur in the observed facts clock; corrected checker explicitly verifies each excluded bridge as synthetic/unobserved/missing-amount, with model and traces unchanged',
        'historical_model_reruns_in_this_audit': 0, 'account_runs_in_this_audit': 0,
    })
    print(dict(totals), 'partial', len(partial), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        attempt = 1
        while (O / f'trace-validation-failed-v{attempt}.json').exists():
            attempt += 1
        save(O / f'trace-validation-failed-v{attempt}.json', {'passed': False, 'error': traceback.format_exc()})
        raise
