"""Two preselected THS index trajectories using immutable frozen PV functions.

Offline only. No account/ranking engine, source mutations, or mechanism changes.
Use --freeze before --run. Keep original source strings and failures.
"""
from __future__ import annotations

import argparse
import datetime as dt
from decimal import Decimal, localcontext, ROUND_HALF_EVEN
import hashlib
import json
from pathlib import Path
import shutil
import sys

sys.dont_write_bytecode = True
WORK = Path('/Users/bytedance/Documents/ChatGPT/money')
REPO = Path('/Users/bytedance/repos/TradingAlarm/TradingAlarm')
ROUND = WORK / 'research_rounds/sector-stock-20261021'
SOURCE_ROUND = REPO / 'research_rounds/pv-participation-response-20261020'
OUT = ROUND / 'coverage/sector-trajectory-v1'
SYMBOLS = {'URFI881155': 'THS Bank', 'URFI881121': 'THS Semiconductor'}
SOURCE_DIR = REPO / 'TradingAlarm/research/data/ths-index-history-9603-20261018/canonical'
DEPS = ('prepare_input.py', 'data_utils.py', 'numeric.py', 'participation.py')
CUTS = ('2015-12-31', '2021-12-31', '2024-09-30')
SCALES = ('0.1', '100')
WINDOWS = (
    ('full', '2013-01-01', '2026-10-16'),
    ('2014-2016', '2014-01-01', '2016-12-31'),
    ('2024-2026', '2024-01-01', '2026-10-16'),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')


def freeze():
    if OUT.exists():
        raise FileExistsError('Do not overwrite prior evidence: ' + str(OUT))
    old = json.loads((SOURCE_ROUND / 'freeze.json').read_text())
    source_review = ROUND / 'coverage/revalidation-20261022/sector-input-review/review-summary.json'
    evidence = json.loads(source_review.read_text())
    paths = [Path(__file__).resolve(), SOURCE_ROUND / 'freeze.json', SOURCE_ROUND / 'reviews/algorithm-contract.md',
             ROUND / 'protocol.proposed.json', WORK / 'docs/RESEARCH_CONSENSUS.md', source_review,
             ROUND / 'coverage/revalidation-20261022/sector-input-review/PRIMARY_VISUAL_JUDGMENT.md',
             ROUND / 'coverage/revalidation-20261022/sector-membership/next-capability.md']
    for name in DEPS:
        path = SOURCE_ROUND / 'code' / name
        assert sha(path) == old['core_code_sha256'][name], name
        paths.append(path)
    for symbol in SYMBOLS:
        path = SOURCE_DIR / (symbol + '.csv')
        assert sha(path) == evidence['symbols'][symbol]['source_sha256'], symbol
        paths.append(path)
    protocol = {
        'frozen_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'status': 'frozen_before_new_trajectory_calculation',
        'purpose': 'Finite new-index input and trajectory technical review, not economic admission',
        'symbols': SYMBOLS, 'selection': 'Existing metadata pilot; no return-based selection',
        'source_priority': 'Immutable native 9603 canonical CSV; no blending with web revisions',
        'known_price_discrepancy': {'URFI881121': {'2020-06-29': {'native': '6046.605', 'web': '6053.913'},
                                                 '2020-06-30': {'native': '6176.074', 'web': '6181.235'}}},
        'state_start': '2007-08-01, original full source start for both series; no reset at plot start',
        'end': '2026-10-16', 'plot_windows': WINDOWS,
        'account_warmup_decision': 'Not decided here: this technical study preserves full source origin, not a 2013 account initialization certification',
        'input_precision': 'Source CSV strings -> frozen native_strings (40 digits, HALF_EVEN) -> float(decimal_text); index prices and volume preserved; no factor recomputation, fill, or new numeric tolerance',
        'prepare_frame_scope': 'Old prepare_frame whitelist excludes these indices; explicit unadjusted_index-equivalent adapter below invokes frozen helpers without extending old whitelist',
        'mechanism': {'upstream': 'event_frame_numeric(close, volume, joint=True, event_exit=False)',
                      'candidate': 'participation_frame(bars, upstream, mode=volume)',
                      'diagnostic_control': 'Same PV upstream baseline plus mode=none identity only',
                      'changes': 0, 'accounts': 0, 'network': 0, 'ranking_computed': False},
        'checks': {'prefix_cutoffs': CUTS, 'prefix_scope': 'Reparse source prefix and compare all upstream/candidate columns exactly; ledger lifetime checked separately',
                   'volume_multipliers': SCALES,
                   'unit_invariance': 'Exact discrete states, price references, dates and IDs; continuous confirmation/volume ratios checked with 32*binary64_epsilon relative tolerance only in validation, never model decisions; no promise of universal float invariance',
                   'source_bytes_unchanged': True, 'original_pv_none_identity': True},
        'known_limits': ['Previously seen development history', 'Two index lines only, not whole-market eligibility',
                         'No same-taxonomy historical members certified', 'No shareholder/market cap or execution certification',
                         'THS aggregate volume field usable for relative-volume technical review; historical aggregation changes not independently certified',
                         'Old 18-window admission cannot substitute for this new-input validation',
                         'State markers are not trades; no return-based judgement or new filter'],
        'input_code_evidence_sha256': {str(path): sha(path) for path in paths},
    }
    OUT.mkdir(parents=True)
    write_json(OUT / 'protocol.json', protocol)
    print(json.dumps({'frozen': str(OUT / 'protocol.json'), 'sha256': sha(OUT / 'protocol.json')}))


def run():
    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    protocol = json.loads((OUT / 'protocol.json').read_text())
    if set(p.name for p in OUT.iterdir()) != {'protocol.json'}:
        raise FileExistsError('Run refuses existing output; keep failures in place')
    for path, digest in protocol['input_code_evidence_sha256'].items():
        assert sha(path) == digest, path
    sys.path.insert(0, str(SOURCE_ROUND / 'code'))
    from prepare_input import native_strings, decimal_text
    from data_utils import eligible_prices
    from numeric import event_frame_numeric
    from participation import participation_frame
    for name in ('inputs', 'prepared', 'figures', 'code'):
        (OUT / name).mkdir()
    for name in DEPS:
        shutil.copy2(SOURCE_ROUND / 'code' / name, OUT / 'code' / name)
    shutil.copy2(__file__, OUT / 'code' / Path(__file__).name)
    checks, failures, summaries = [], [], []

    def check(symbol, kind, fn, **details):
        try:
            fn()
            checks.append({'symbol': symbol, 'check': kind, 'passed': True, **details})
        except Exception as exc:
            checks.append({'symbol': symbol, 'check': kind, 'passed': False,
                           'error': str(exc), **details})
            failures.append(checks[-1])

    def prepare(raw, volume_scale='1'):
        # This deliberately mirrors prepare_frame's existing unadjusted_index
        # branch. No invocation with an unaudited whitelist alias is used.
        strings = native_strings(raw)
        assert str(strings.index[0].date()) == '2007-08-01'
        frame = pd.DataFrame(index=strings.index)
        for name in ('open', 'high', 'low', 'close'):
            frame[name] = strings[name].map(lambda x: float(decimal_text(x)))
        with localcontext() as context:
            context.prec, context.rounding = 40, ROUND_HALF_EVEN
            factor = decimal_text(volume_scale)
            frame['volume'] = strings.volume.map(lambda x: float(decimal_text(x) * factor))
        if not np.isfinite(frame.to_numpy()).all() or not frame.gt(0).all().all():
            raise ValueError('Unexpected invalid source value; stop, do not silently filter/fill')
        eligible = eligible_prices(frame)
        pd.testing.assert_frame_equal(eligible, frame, check_exact=True)
        return frame

    def calculate(bars):
        upstream = event_frame_numeric(bars.close, bars.volume, joint=True, event_exit=False)
        candidate, ledger = participation_frame(bars, upstream, mode='volume')
        return upstream, candidate, ledger

    def draw(symbol, name, bars, upstream, candidate, window):
        suffix, start, end = window
        q = bars.loc[start:end]
        c, u = candidate.loc[q.index], upstream.loc[q.index]
        x = q.index
        fig, axes = plt.subplots(4, 1, figsize=(18, 11), sharex=True,
                                 gridspec_kw={'height_ratios': [4, 1.2, 1.2, 1.4]})
        axes[0].fill_between(x, q.low, q.high, color='#b9c2c8', alpha=.45, label='Daily low-high')
        axes[0].plot(x, q.close, color='#233d52', lw=.85, label='Close')
        axes[0].plot(x, c.floor, color='#18854b', lw=1.05, label='Frozen candidate floor')
        axes[0].plot(x, u.structure_floor_price, color='#717171', lw=.8, ls=':', label='Original PV floor')
        axes[0].plot(x, c.pending_reclaim, color='#b48311', lw=1, ls='--', label='Pending reclaim / lower')
        axes[0].plot(x, c.pending_lower, color='#b48311', lw=1, ls='--')
        for mask, marker, color, label, size in [
            (c.entered.eq(1) & c.independent_entry.eq(0), '^', '#078a47', 'Original-channel establishment', 24),
            (c.independent_entry.eq(1), '*', '#7445b7', 'Independent volume-memory recovery', 80),
            (c.exited.eq(1), 'v', '#ba3036', 'Structure invalidated', 24),
            (c.created.eq(1), 's', '#c6921f', 'High-participation decline memory', 19),
        ]:
            axes[0].scatter(x[mask], q.close[mask], marker=marker, color=color, s=size, zorder=4, label=label)
        axes[0].set_yscale('log')
        axes[0].set_ylabel('Provider index points (log)')
        axes[0].legend(loc='upper left', ncol=3, fontsize=8)
        axes[0].set_title(f'{name} | {symbol} | {start} to {end}\nFrozen PV structure; source origin 2007-08-01; signal marks are NOT trades')
        up = q.close.diff().fillna(0).ge(0)
        axes[1].bar(x, q.volume / 1e9, width=1, color=np.where(up, '#79a7b7', '#bc8e80'))
        axes[1].set_ylabel('Source volume / 1e9\nunit unverified')
        axes[2].bar(x, c.volume_ratio, width=1, color='#9eaaa8')
        axes[2].axhline(2, color='#c6921f', ls='--', lw=1)
        axes[2].set_ylabel('V / prior 21 median\nno display cap')
        axes[3].step(x, c.target + 2, where='post', color='#18854b', lw=1.1, label='Candidate state')
        axes[3].step(x, u.target, where='post', color='#717171', lw=1, label='Original PV state')
        axes[3].set_yticks([0, 1, 2, 3], ['0', '1', '0', '1'])
        axes[3].set_ylim(-.15, 3.2)
        axes[3].set_ylabel('Upper: candidate\nLower: original PV')
        axes[3].legend(loc='upper left', ncol=2, fontsize=8)
        locator = mdates.AutoDateLocator(minticks=7, maxticks=14)
        axes[3].xaxis.set_major_locator(locator)
        axes[3].xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        for axis in axes:
            axis.grid(alpha=.16)
        fig.text(.01, .007, 'Seen historical development material. No account, ranking, or member-based admission. State 0 means no live UP hypothesis, not a bearish forecast.', fontsize=9)
        fig.tight_layout(rect=(0, .025, 1, 1))
        fig.savefig(OUT / 'figures' / f'{symbol}-{suffix}.png', dpi=140)
        plt.close(fig)

    for symbol, name in SYMBOLS.items():
        source = SOURCE_DIR / (symbol + '.csv')
        shutil.copy2(source, OUT / 'inputs' / source.name)
        raw = pd.read_csv(source, dtype=str, keep_default_na=False)
        bars = prepare(raw)
        bars.to_csv(OUT / 'prepared' / source.name, index_label='date')
        reread = pd.read_csv(OUT / 'prepared' / source.name, index_col='date', parse_dates=True, float_precision='round_trip')
        check(symbol, 'prepared_roundtrip', lambda: pd.testing.assert_frame_equal(bars, reread, check_exact=True))
        upstream, candidate, ledger = calculate(bars)
        upstream.to_csv(OUT / f'{symbol}-upstream.csv', index_label='date')
        states = bars.join(candidate).join(upstream.add_prefix('upstream_'))
        states.to_csv(OUT / f'{symbol}-states.csv', index_label='date')
        ledger.to_csv(OUT / f'{symbol}-volume-events.csv', index=False)
        def ledger_lifetimes():
            assert ledger.id.is_unique
            for _, row in ledger.iterrows():
                created_at = pd.Timestamp(row.created_date)
                assert candidate.loc[created_at, 'created'] == 1
                assert int(row.created_observation) == bars.index.get_loc(created_at)
                if pd.notna(row.resolved_date):
                    resolved_at = pd.Timestamp(row.resolved_date)
                    assert resolved_at > created_at
                    assert int(row.waiting_observations) == bars.index.get_loc(resolved_at) - int(row.created_observation)
                else:
                    assert row.outcome == 'open'
                    assert int(row.waiting_observations) == len(bars) - 1 - int(row.created_observation)
            assert not (candidate.target.eq(1) & candidate.pending.eq(1)).any()
        check(symbol, 'ledger_clock_lifetimes_and_no_active_pending', ledger_lifetimes)
        none, _ = participation_frame(bars, upstream, mode='none')
        for col in ('target', 'entered', 'exited'):
            check(symbol, 'none_identity_' + col, lambda col=col: np.testing.assert_array_equal(none[col], upstream[col]))
        check(symbol, 'none_floor_identity', lambda: np.testing.assert_allclose(none.floor, upstream.structure_floor_price, rtol=0, atol=0, equal_nan=True))
        for cutoff in CUTS:
            prefix = prepare(raw.loc[raw.date.le(cutoff)])
            pu, pc, _ = calculate(prefix)
            check(symbol, 'prefix_preparation_exact', lambda: pd.testing.assert_frame_equal(prefix, bars.loc[:cutoff], check_exact=True), cutoff=cutoff)
            check(symbol, 'prefix_upstream_exact', lambda: pd.testing.assert_frame_equal(pu, upstream.loc[:cutoff], check_exact=True), cutoff=cutoff)
            check(symbol, 'prefix_candidate_exact', lambda: pd.testing.assert_frame_equal(pc, candidate.loc[:cutoff], check_exact=True), cutoff=cutoff)
        for scale in SCALES:
            scaled = prepare(raw, volume_scale=scale)
            su, sc, sl = calculate(scaled)
            check(symbol, 'volume_scale_upstream_discrete_and_price_exact', lambda: pd.testing.assert_frame_equal(su.drop(columns='confirmation'), upstream.drop(columns='confirmation'), check_exact=True), scale=scale)
            check(symbol, 'volume_scale_upstream_confirmation_numeric', lambda: np.testing.assert_allclose(su.confirmation, upstream.confirmation, rtol=32*np.finfo(float).eps, atol=0, equal_nan=True), scale=scale)
            check(symbol, 'volume_scale_candidate_discrete_and_price_exact', lambda: pd.testing.assert_frame_equal(sc.drop(columns='volume_ratio'), candidate.drop(columns='volume_ratio'), check_exact=True), scale=scale)
            check(symbol, 'volume_scale_candidate_ratio_numeric', lambda: np.testing.assert_allclose(sc.volume_ratio, candidate.volume_ratio, rtol=32*np.finfo(float).eps, atol=0, equal_nan=True), scale=scale)
            variable = ['event_volume', 'volume_baseline', 'volume_ratio', 'resolution_volume_ratio']
            check(symbol, 'volume_scale_ledger_identity', lambda: pd.testing.assert_frame_equal(sl.drop(columns=variable), ledger.drop(columns=variable), check_exact=True), scale=scale)
            for col in variable:
                divisor = float(Decimal(scale)) if col in ('event_volume', 'volume_baseline') else 1
                check(symbol, 'volume_scale_ledger_numeric_' + col, lambda col=col, divisor=divisor: np.testing.assert_allclose(sl[col] / divisor, ledger[col], rtol=32*np.finfo(float).eps, atol=0, equal_nan=True), scale=scale)
        for window in WINDOWS:
            draw(symbol, name, bars, upstream, candidate, window)
        def summarize(first, last):
            c = candidate.loc[first:last]
            u = upstream.loc[c.index]
            return {'first': str(c.index[0].date()), 'last': str(c.index[-1].date()), 'observations': len(c),
                    'state_1_observations': int(c.target.sum()), 'entries': int(c.entered.sum()), 'exits': int(c.exited.sum()),
                    'memory_created': int(c.created.sum()), 'independent_recovery_entries': int(c.independent_entry.sum()),
                    'base_consumptions': int(c.consumed_by_base.sum()),
                    'changed_state_vs_original': int(c.target.ne(u.target).sum()),
                    'extra_state_vs_original': int((c.target.eq(1) & u.target.eq(0)).sum()),
                    'less_state_vs_original': int((c.target.eq(0) & u.target.eq(1)).sum())}
        summaries.append({'symbol': symbol, 'name': name, 'source_rows': len(bars),
                          'full': summarize('2007-08-01', '2026-10-16'),
                          'plot_windows': {window[0]: summarize(window[1], window[2]) for window in WINDOWS},
                          'ledger_outcomes': {str(k): int(v) for k, v in ledger.outcome.value_counts().items()},
                          'independent_recovery_dates': candidate.index[candidate.independent_entry.eq(1)].strftime('%Y-%m-%d').tolist()})
    for path, digest in protocol['input_code_evidence_sha256'].items():
        assert sha(path) == digest, ('Source changed during study', path)
    write_json(OUT / 'validation.json', {'checks': checks, 'passed': sum(x['passed'] for x in checks), 'failed': len(failures),
                                       'account_runs': 0, 'mechanism_changes': 0, 'network_requests': 0})
    write_json(OUT / 'summary.json', {'series': summaries, 'account_runs': 0, 'mechanism_changes': 0,
                                    'figures': 6, 'prefix_dates': CUTS, 'validation_failed': len(failures),
                                    'disposition': 'technical evidence only; parent visual review pending; no economic admission'})
    write_json(OUT / 'manifest.json', {str(p.relative_to(OUT)): sha(p) for p in sorted(OUT.rglob('*')) if p.is_file()})
    print(json.dumps({'output': str(OUT), 'passed': sum(x['passed'] for x in checks), 'failed': failures, 'summaries': summaries}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze', action='store_true')
    mode.add_argument('--run', action='store_true')
    args = parser.parse_args()
    freeze() if args.freeze else run()
