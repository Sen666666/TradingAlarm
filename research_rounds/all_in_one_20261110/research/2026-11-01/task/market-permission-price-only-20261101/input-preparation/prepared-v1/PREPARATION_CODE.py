"""Bounded original-input export. Never imports the new FSM or account engines."""
from __future__ import annotations
import ast
import copy
import hashlib
import json
from pathlib import Path
import sys
import time
import traceback

import numpy as np
import pandas as pd

O = Path(__file__).resolve().parent
RUN = O / (sys.argv[1] if len(sys.argv) > 1 else 'prepared-v1')
assert RUN.parent == O
ROOT = Path('/Users/bytedance/Documents/ChatGPT/money')
RR = ROOT / 'research_rounds'
W = Path('/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds')
PROOF = W / 'market-proof-lifecycle-readonly-20261101'
FROZEN = O.parent / 'v2-frozen'
TARGETS = {'URFI881121': '半导体', 'URFI881172': '电子化学品'}
CUTS = ['2023-01-19', '2024-09-23', '2026-05-07']
SOURCES = {}
KNOWN = json.loads((PROOF / 'SOURCE_SHA256.json').read_text())


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def remember(p, expected=None):
    p = Path(p)
    actual = sha(p)
    expected = expected or KNOWN.get(str(p))
    if expected is not None:
        assert actual == expected, ('source changed', str(p))
    SOURCES[str(p)] = actual
    return p


def read(p):
    return json.loads(remember(p).read_text())


def clean(x):
    if isinstance(x, dict):
        return {str(k): clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [clean(v) for v in x]
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (np.bool_,)):
        return bool(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if np.isfinite(x) else None
    if isinstance(x, pd.Timestamp):
        return str(x.date())
    return x


def save(name, obj):
    p = RUN / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(clean(obj), ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def table(name, f):
    p = RUN / name
    p.parent.mkdir(parents=True, exist_ok=True)
    f.to_parquet(p.with_suffix('.parquet'))
    f.to_csv(p.with_suffix('.csv'), float_format='%.17g')


def load_function():
    p = remember(ROOT / 'TradingAlarm/desk/refresh.py',
                 '6a144503d62891ae8856fe35b0475797226d2370b44ceb328d420dcc7084cdfc')
    node = next(n for n in ast.parse(p.read_text()).body if isinstance(n, ast.FunctionDef) and n.name == 'compute_recovery')
    assert ast.unparse(node.body[-1].value) == 'z'
    original = ast.dump(node)
    node = copy.deepcopy(node)
    node.body[-1].value = ast.Tuple(elts=[ast.Name(id=k, ctx=ast.Load()) for k in
                                         ['z', 'mom', 'sector_b', 'returns', 'sector_r', 'r']], ctx=ast.Load())
    env = dict(np=np, pd=pd)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(p), 'exec'), env)
    (RUN / 'ORIGINAL_COMPUTE_RECOVERY_EXPOSED.py').write_text(ast.unparse(node) + '\n')
    save('ORIGINAL_FUNCTION_BINDING.json', dict(path=str(p), sha256=sha(p), original_AST_sha256=hashlib.sha256(original.encode()).hexdigest(),
                                              change='last return only: z,mom,sector_b,returns,sector_r,r'))
    return env['compute_recovery']


def load_eligible():
    p = remember(RR / 'pv-participation-response-20261020/code/data_utils.py')
    nodes = [n for n in ast.parse(p.read_text()).body if isinstance(n, ast.FunctionDef)
             and n.name in ['boolean_column', 'eligible_prices']]
    env = dict(np=np, pd=pd)
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(p), 'exec'), env)
    return env['eligible_prices']


def coverage(domain, roster, full_roster, mom, returns, index):
    pieces = []
    identities = full_roster.groupby('sector_id').size()
    for sector, group in roster.groupby('sector_id'):
        m = pd.concat({sid: mom[sid] for sid in group.symbol}, axis=1).reindex(index)
        r = pd.concat({sid: returns[sid] for sid in group.symbol}, axis=1).reindex(index)
        assert not np.isinf(m.to_numpy()).any() and not np.isinf(r.to_numpy()).any()
        n = m.notna().sum(axis=1)
        pos = m.gt(0).sum(axis=1)
        z = pd.DataFrame(dict(domain=domain, sector=sector, fixed_identities=int(identities[sector]),
                              source_roster=len(group), ready_m=n, positive_m=pos,
                              negative_m=m.lt(0).sum(axis=1), zero_m=m.eq(0).sum(axis=1),
                              unknown_m=int(identities[sector]) - n,
                              breadth=(pos / n).where(n >= 5), price_return_stocks=r.notna().sum(axis=1)), index=index)
        pieces.append(z)
    return pd.concat(pieces).rename_axis('date').reset_index().set_index(['date', 'sector']).sort_index()


def original_aggregate(roster, mom, returns, index):
    sector_r = []
    sector_b = []
    for _, group in roster.groupby('sector_id'):
        r = pd.concat({s: returns[s] for s in group.symbol}, axis=1).mean(axis=1)
        f = pd.concat({s: mom[s] for s in group.symbol}, axis=1)
        n = f.notna().sum(axis=1)
        sector_r.append(r)
        sector_b.append((f.gt(0).sum(axis=1) / n).where(n >= 5))
    raw_r = pd.concat(sector_r, axis=1).mean(axis=1).reindex(index)
    b = pd.concat(sector_b, axis=1)
    broad = b.mean(axis=1).where(b.notna().sum(axis=1) >= 8).reindex(index)
    price = (1 + np.expm1(raw_r.fillna(0))).cumprod()
    z = pd.DataFrame(dict(market=price, prior_high63=price.shift().rolling(63, min_periods=63).max(), breadth=broad))
    z['breakout'] = (z.market > z.prior_high63) & (z.market.diff() > 0) & (z.breadth > .6)
    return z, raw_r


def compare(z, ref, fields=('market', 'prior_high63', 'breadth')):
    result = {}
    assert z.index.equals(ref.index)
    for k in fields:
        np.testing.assert_allclose(z[k], ref[k], rtol=1e-12, atol=1e-12, equal_nan=True)
        result[k] = float((z[k] - ref[k]).abs().max())
    np.testing.assert_array_equal(z.breakout, ref.breakout)
    result['breakout_exact'] = True
    return result


def segments(sid, raw, eligible):
    entries = []
    for segment, g in eligible.groupby('segment_id', sort=False):
        entries.append(dict(segment=int(segment), first=g.index.min(), last=g.index.max(),
                            eligible_observations=len(g), first64_suppressed=min(64, len(g))))
    return dict(symbol=sid, source_rows=len(raw), eligible_rows=len(eligible), excluded_source_rows=len(raw)-len(eligible),
                segments=entries, missing_segment_id=int(eligible.segment_id.isna().sum()))


def rebuild_old_prefix(raws, cutoff):
    mom, returns = {}, {}
    for sid, full in raws.items():
        raw = full.loc[:cutoff]
        ms, rs = [], []
        for _, g in raw.groupby('segment_id', sort=False):
            r = np.log(g.close).diff()
            q = g.amount / g.amount.shift().rolling(21, min_periods=21).median()
            m = (r * np.minimum(1, np.sqrt(q))).ewm(span=21, adjust=False).mean()
            ready = np.arange(len(g)) >= 64
            rs.append(r.where(ready))
            ms.append(m.where(ready))
        if ms:
            mom[sid] = pd.concat(ms).sort_index()
            returns[sid] = pd.concat(rs).sort_index()
    return mom, returns


def write_domain(domain, ref, raw_r, cov, restart_counts, price_roster, full_count):
    # As-run price is authoritative. Exposure of r never substitutes it.
    z = ref[['market', 'prior_high63', 'breadth', 'breakout', 'fast_on']].copy()
    z = z.rename(columns={'market': 'market_as_run', 'prior_high63': 'prior_high63_as_run',
                          'breakout': 'breakout_as_run', 'fast_on': 'fast_on_original'})
    z['aggregate_log_return'] = raw_r.reindex(z.index)
    z['price_observed'] = z.aggregate_log_return.notna()
    z['price_input'] = z.market_as_run.where(z.price_observed)
    z['price_industries_ready'] = cov.price_return_stocks.gt(0).groupby('date').sum().reindex(z.index)
    z['price_stocks_ready'] = cov.price_return_stocks.groupby('date').sum().reindex(z.index)
    z['signed_m_stocks_ready'] = cov.ready_m.groupby('date').sum().reindex(z.index)
    z['breadth_industries_ready'] = cov.breadth.notna().groupby('date').sum().reindex(z.index)
    z['stock_segment_start_count'] = restart_counts.reindex(z.index, fill_value=0)
    z['fixed_stock_identities'] = full_count
    z['source_roster_nonempty'] = price_roster
    z['domain'] = domain
    z['source_segment_id'] = 0  # Continuous composite formula; stock resets are separate columns.
    table(f'{domain}/market', z)
    cov.to_parquet(RUN / domain / 'all_industry_coverage.parquet')
    return z


def industry_output(domain, sector, cov, base, primary=None, expected=None):
    if expected is not None:
        remember(base, expected)
    else:
        remember(base)
    raw = pd.read_parquet(base)
    cutoff = cov.index.get_level_values('date').max()
    raw = raw.loc[:cutoff]
    if primary is not None:
        remember(primary[0], primary[1])
        f = pd.read_parquet(primary[0], columns=['close', 'segment_id']).loc[:cutoff]
        pd.testing.assert_series_equal(f.close, raw.close.reindex(f.index), check_names=False, check_exact=True)
        pd.testing.assert_series_equal(f.segment_id, raw.segment_id.reindex(f.index), check_names=False, check_exact=True)
        index = f.index
        prices = f.close
        segment = f.segment_id
        valid = (raw.price_eligible & raw.observed_bar & ~raw.synthetic_event_bar).reindex(index).fillna(False)
    else:
        index = raw.index
        prices = raw.close
        segment = raw.segment_id
        valid = raw.price_eligible & raw.observed_bar & ~raw.synthetic_event_bar
    price_data = pd.DataFrame(dict(industry_close_as_source=prices, price_observed=valid,
                                   price_input=prices.where(valid), price_source_segment_id=segment), index=index)
    counts = cov.xs(sector, level='sector')
    z = price_data.join(counts, how='outer').sort_index()
    z['price_observed'] = z.price_observed.fillna(False).astype(bool)
    # The pre-2013 price prefix has no stock breadth observations: unknown, not zero.
    z['breadth_universe'] = domain
    z['industry_price_series'] = sector
    z['industry_name'] = TARGETS[sector]
    z['breadth_is_complete_index_constituents'] = False
    table(f'{domain}/industry_{sector}', z)
    return z, dict(domain=domain, sector=sector, price_source=str(base), primary_price_source=str(primary[0]) if primary else str(base),
                    price_first=index.min(), price_last=index.max(), price_rows=len(index),
                    price_segments=[int(x) for x in segment.dropna().unique()],
                    breadth_first=counts.breadth.first_valid_index(), breadth_last=counts.breadth.last_valid_index(),
                    original_fixed_identities=int(counts.fixed_identities.iloc[0]), source_roster=int(counts.source_roster.iloc[0]),
                    interpretation='real industry index price; breadth only fixed research-pool components, never full index membership')


def main():
    started = time.monotonic()
    RUN.mkdir(exist_ok=False)
    frozen_before = {str(p): sha(p) for p in FROZEN.iterdir() if p.is_file()}
    remember(O / 'PROTOCOL.md')
    remember(Path(__file__))
    for name in ['analyze_readonly.py', 'ORIGINAL_M_EXPORT_GATE.json', 'M_EXPORT_CACHE_BINDING.json',
                 'OLD_CACHED_COMPONENT_GATE.json', 'SOURCE_SHA256.json']:
        remember(PROOF / name)
    meta = read(RR / 'a-share-selection-e0-20261024/inputs-v2/metadata.json')
    stock_manifest = read(W / 'universe-cp1-inputs-20261031/STOCK_MANIFEST.json')
    industry_manifest = {r['series']: r for r in read(W / 'universe-cp1-inputs-20261031/INDUSTRY_MANIFEST.json')}
    expected_ids = read(W / 'native-I-cache-interface-20261031/FREEZE.json')['stocks']
    assert set(expected_ids) == {r['symbol'] for r in stock_manifest} and len(expected_ids) == 1709
    full_native_roster = pd.DataFrame([dict(symbol=s, sector_id=meta[s]['sector_id']) for s in expected_ids])
    references = {}
    for domain, path in [('OLD407', RR / 'actual-risk-recovery-20261027/recovery.csv'),
                          ('NATIVE1709', W / 'mainline-absolute-Q4-20261031/recovery.csv')]:
        references[domain] = pd.read_csv(remember(path), index_col=0, parse_dates=True)
    native_end = str(references['NATIVE1709'].index.max().date())
    old_end = str(references['OLD407'].index.max().date())
    assert native_end == '2026-06-30' and old_end == '2026-10-26'
    fn = load_function()
    eligible = load_eligible()

    signals, native_segments, native_absent, native_restarts = {}, [], [], []
    for j, entry in enumerate(stock_manifest):
        sid = entry['symbol']
        p = next(Path(k) for k in entry['source_sha256'] if k.endswith('/signal.parquet'))
        raw = pd.read_parquet(remember(p, entry['source_sha256'][str(p)]),
                              columns=['close', 'amount', 'price_eligible', 'observed_bar', 'synthetic_event_bar', 'segment_id']).loc[:native_end]
        valid = raw.price_eligible & raw.observed_bar & ~raw.synthetic_event_bar
        raw_valid = raw.loc[valid]
        native_segments.append(segments(sid, raw, raw_valid))
        for _, g in raw_valid.groupby('segment_id', sort=False):
            native_restarts.append(g.index.min())
        if valid.any():
            signals[sid] = raw
        else:
            native_absent.append(sid)
        if j == 9:
            estimate = (time.monotonic() - started) / 10 * 1709
            print('NATIVE_LOADING_PILOT_ESTIMATE_SECONDS', round(estimate, 2), flush=True)
            if estimate > 150:
                raise RuntimeError('bounded source-loading pilot exceeded 150 seconds')
    native_roster = full_native_roster[full_native_roster.symbol.isin(signals)].copy()
    z, nm, nb, nr, nsr, native_r = fn(signals, native_roster)
    native_gate = compare(z, references['NATIVE1709'])
    native_cov = coverage('NATIVE1709', native_roster, full_native_roster, nm, nr, z.index)
    # Full coverage must reconstruct both original breadth and price availability.
    nre = pd.Series(native_restarts).value_counts().sort_index()
    native_market = write_domain('NATIVE1709', references['NATIVE1709'], native_r, native_cov, nre, len(signals), 1709)
    save('NATIVE_SOURCE_SEGMENTS.json', native_segments)
    save('NATIVE_ABSENT_IDENTITIES.json', native_absent)
    print('NATIVE_ORIGINAL_INPUTS_READY', len(native_market), len(signals), flush=True)

    old_roster = pd.read_csv(remember(RR / 'tech-compound-design-20261026/proposed-pool.csv'))
    assert len(old_roster) == 407
    old_m, old_r, old_raws, old_segments, old_restarts = {}, {}, {}, [], []
    for sid in old_roster.symbol:
        cached = pd.read_parquet(remember(RR / f'tech-drawdown-regime-20261027/diagnostic-v1/traces/{sid}.parquet'),
                                 columns=['r', 'm', 'ready', 'close', 'amount']).loc[:old_end]
        p = remember(RR / f'tech-finite-compound-20261026/prepared-v2/signals/{sid}.parquet')
        raw = pd.read_parquet(p).loc[:old_end]
        valid = eligible(raw)
        pd.testing.assert_series_equal(cached.close, valid.close, check_exact=True)
        pd.testing.assert_series_equal(cached.amount, valid.amount, check_exact=True)
        old_raws[sid] = valid
        old_m[sid] = cached.m.where(cached.ready)
        old_r[sid] = cached.r.where(cached.ready)
        old_segments.append(segments(sid, raw, valid))
        for _, g in valid.groupby('segment_id', sort=False):
            old_restarts.append(g.index.min())
    oz, old_agg_r = original_aggregate(old_roster, old_m, old_r, references['OLD407'].index)
    old_gate = compare(oz, references['OLD407'])
    old_cov = coverage('OLD407', old_roster, old_roster, old_m, old_r, oz.index)
    old_market = write_domain('OLD407', references['OLD407'], old_agg_r, old_cov,
                               pd.Series(old_restarts).value_counts().sort_index(), 407, 407)
    save('OLD_SOURCE_SEGMENTS.json', old_segments)
    print('OLD_CACHED_INPUTS_READY', len(old_market), flush=True)

    # Original global high/BREAK independently reconstructed from as-run prices.
    high_gates = {}
    for domain, ref in references.items():
        high = ref.market.shift().rolling(63, min_periods=63).max()
        np.testing.assert_allclose(high, ref.prior_high63, rtol=1e-12, atol=1e-12, equal_nan=True)
        br = (ref.market > high) & (ref.market.diff() > 0) & (ref.breadth > .6)
        np.testing.assert_array_equal(br, ref.breakout)
        high_gates[domain] = dict(prior_high63_max_abs=float((high-ref.prior_high63).abs().max()), breakout_exact=True)

    snapshots = read(PROOF / 'CHECKPOINT_LIFECYCLE.json')
    assert len(snapshots) == 37
    checkpoint_checks = []
    for row in snapshots:
        ref = references[row['domain']].loc[row['day']]
        errors = {k: float(abs(ref[k] - row['market'][k])) for k in ['market', 'prior_high63', 'breadth']}
        assert max(errors.values()) == 0, (row['case'], row['day'], errors)
        assert bool(ref.breakout) == row['market']['breakout']
        checkpoint_checks.append(dict(case=row['case'], domain=row['domain'], day=row['day'], errors=errors, breakout_exact=True))
    component_checks = []
    for row in read(PROOF / 'INDUSTRY_M_BREADTH_SELECTED.json'):
        r = native_cov.loc[(pd.Timestamp(row['day']), row['sector'])]
        for key, col in [('identities', 'source_roster'), ('ready', 'ready_m'), ('positive', 'positive_m'), ('negative', 'negative_m'), ('zero', 'zero_m')]:
            assert int(r[col]) == row[key], (row['day'], row['sector'], key)
        if row['breadth'] is None:
            assert pd.isna(r.breadth)
        else:
            assert abs(r.breadth-row['breadth']) <= 1e-15
        component_checks.append(dict(day=row['day'], sector=row['sector'], passed=True))
    old_component_checks = []
    for row in read(PROOF / 'OLD407_CACHED_INDUSTRY_BREADTH.json'):
        r = old_cov.loc[(pd.Timestamp(row['day']), row['sector'])]
        assert int(r.ready_m) == row['ready'] and int(r.fixed_identities) == row['identities']
        assert abs(r.breadth-row['breadth']) <= 1e-15 or (pd.isna(r.breadth) and row['breadth'] is None)
        old_component_checks.append(dict(day=row['day'], sector=row['sector'], passed=True))
    save('CHECKPOINT_37_GATE.json', dict(passed=True, checkpoints=checkpoint_checks, native_components=len(component_checks), old_components=len(old_component_checks)))

    # Three independently physically truncated original raw-input exports.
    prefix_gates = []
    for cut in CUTS:
        small = {s: f.loc[:cut].copy() for s, f in signals.items()
                 if (f.loc[:cut].price_eligible & f.loc[:cut].observed_bar & ~f.loc[:cut].synthetic_event_bar).any()}
        rost = full_native_roster[full_native_roster.symbol.isin(small)]
        pz, pm, pb, pr, psr, par = fn(small, rost)
        pd.testing.assert_frame_equal(pz, z.loc[:cut], check_exact=True)
        pcov = coverage('NATIVE1709', rost, full_native_roster, pm, pr, pz.index)
        cols = ['ready_m', 'positive_m', 'negative_m', 'zero_m', 'unknown_m', 'breadth', 'price_return_stocks']
        pd.testing.assert_frame_equal(pcov[cols], native_cov.loc[pd.IndexSlice[:pd.Timestamp(cut), :], cols], check_exact=True)
        om, ore = rebuild_old_prefix(old_raws, cut)
        orost = old_roster[old_roster.symbol.isin(om)]
        for s in om:
            pd.testing.assert_series_equal(om[s], old_m[s].loc[:cut], check_exact=True)
            pd.testing.assert_series_equal(ore[s], old_r[s].loc[:cut], check_exact=True)
        op, opr = original_aggregate(orost, om, ore, oz.loc[:cut].index)
        pd.testing.assert_frame_equal(op, oz.loc[:cut], check_exact=True)
        prefix_gates.append(dict(cutoff=cut, native_rows=len(pz), native_stock_sources=len(small),
                                 native_global_exact=True, native_all_industry_counts_exact=True,
                                 old_stock_signed_m_and_returns_exact=len(om), old_global_exact=True))
        print('ORIGINAL_INPUT_PHYSICAL_PREFIX_PASS', cut, flush=True)
    save('INPUT_PHYSICAL_PREFIX_GATE.json', dict(passed=True, cutoffs=CUTS, checks=prefix_gates))

    # Declared index price sources, separate from research-pool breadth.
    old_input = read(RR / 'pvr-act-comparison-20261027/input.json')
    old_prepared = Path(old_input['snapshot']['path'])
    old_index_manifest = read(old_prepared / 'manifest.json')
    index_reports = []
    for sector in TARGETS:
        manifest = industry_manifest[sector]
        source = next(Path(p) for p in manifest['source_sha256'] if p.endswith('/signal.parquet'))
        primary = Path(manifest['refs']['CP1_input'])
        _, report = industry_output('NATIVE1709', sector, native_cov, source,
                                     (primary, manifest['output_sha256'][str(primary)]), manifest['source_sha256'][str(source)])
        index_reports.append(report)
        old_path = old_prepared / 'signals' / (sector + '.parquet')
        _, report = industry_output('OLD407', sector, old_cov, old_path)
        old_baseline = remember(RR / f'tech-finite-compound-20261026/prepared-v2/signals/{sector}.parquet')
        old_data = pd.read_parquet(old_path).loc[:old_end, ['close', 'segment_id']]
        old_original = pd.read_parquet(old_baseline).loc[:old_end, ['close', 'segment_id']]
        pd.testing.assert_frame_equal(old_data, old_original, check_exact=True)
        report['old_runtime_vs_original_industry_price_exact'] = True
        report['manifest_kind'] = next(r['kind'] for r in old_index_manifest['series'] if r['series_id'] == sector)
        index_reports.append(report)
    save('INDUSTRY_PRICE_SOURCE_GATE.json', dict(passed=True, reports=index_reports))

    cases = []
    for case in read(PROOF / 'FIXED_CASES_BEFORE_COMPONENT_EXPORT.json'):
        domain = case['domain']
        cases.append(dict(case=case['name'], domain=domain, existing_primary_window=case['primary_window'],
                          market_file=f'{domain}/market.parquet', complete_prefix_first=references[domain].index.min(),
                          complete_prefix_last=references[domain].index.max(),
                          never_seed_from_account=True, calendar_context_windows={'OLD407': ['2024-09-01', '2024-12-31'],
                                                                               'NATIVE1709': ['2022-01-01', '2026-06-30']}[domain],
                          industry_files=[f'{domain}/industry_{s}.parquet' for s in TARGETS]))
    save('FIXED_CASE_INPUT_REGISTRY.json', cases)
    summaries = {}
    for domain, f in [('NATIVE1709', native_market), ('OLD407', old_market)]:
        summaries[domain] = dict(first=f.index.min(), last=f.index.max(), rows=len(f),
                                 first_observed_price=f.price_input.first_valid_index(),
                                 first_known_breadth=f.breadth.first_valid_index(), price_unknown=int((~f.price_observed).sum()),
                                 breadth_unknown=int(f.breadth.isna().sum()), post_first_observed_price_unknown=int(f.loc[f.price_input.first_valid_index():].price_input.isna().sum()),
                                 price_source_segment='continuous original composite, component resets separately audited',
                                 left_state='pre-source context unknown; no FSM state computed or seeded; full available prefix exported',
                                 original_formula_match=native_gate if domain == 'NATIVE1709' else old_gate,
                                 high_BREAK_gate=high_gates[domain])
    changed = [p for p, h in SOURCES.items() if sha(p) != h]
    assert not changed, ('original source changed during input export', changed)
    assert {str(p): sha(p) for p in FROZEN.iterdir() if p.is_file()} == frozen_before
    save('SOURCE_SHA256.json', SOURCES)
    save('INPUT_GATE.json', dict(passed=True, input_only=True, historical_new_FSM_outputs=0,
                                 stock_indicator_formula='original signed-m only, new FSM never imported',
                                 domains=summaries, fixed_cases=5, existing_checkpoints_exact=37,
                                 native_component_checks=len(component_checks), old_component_checks=len(old_component_checks),
                                 physical_raw_prefixes=prefix_gates, sources_unchanged=len(SOURCES),
                                 v2_frozen_unchanged=True, source_gaps=native_absent,
                                 source_gap_handling='22 native identities retained but no eligible history through cutoff; never zero-filled m or silently deleted from fixed roster',
                                 industry_interpretation='index close plus research-pool breadth, not full-index constituent breadth',
                                 elapsed_seconds=time.monotonic()-started))
    save('ARTIFACT_SHA256.json', {str(p.relative_to(RUN)): sha(p) for p in sorted(RUN.rglob('*')) if p.is_file() and p.name != 'ARTIFACT_SHA256.json'})
    print('INPUT_GATE_PASS', json.dumps(clean(summaries), ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if RUN.exists():
            save('ERROR.json', dict(reason=repr(exc), traceback=traceback.format_exc(), new_FSM_never_imported=True))
        raise
