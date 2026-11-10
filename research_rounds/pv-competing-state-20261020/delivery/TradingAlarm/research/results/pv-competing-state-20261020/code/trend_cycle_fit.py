"""Fit of the frozen positive-connect state on hindsight cycles through 2026.

No new threshold. 2018-2021 is reviewed because the user asked. It is not unseen.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from trend_segment_revision import fixed_label
from trend_background_hold import path_scores
from trend_positive_connect import positive_state
from market_state_phase2 import CUT, FLOOR, MODEL_FLOOR, asset_of, keep, load_symbol
from monthly_ah_engine import run

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'trend-cycle-fit'
PHASE2 = ROOT/'results'/'market-state-phase2'
BATCH = ROOT/'data'/'ths-index-history-20261018'
ERAS = (('2005-2017', '2005-01-01', '2017-12-31'),
        ('2018-2021', '2018-01-01', '2021-12-31'),
        ('2022-2026', '2022-01-01', '2026-10-16'))
LARGE = math.log(1.5)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_full(symbol, launch):
    frame = pd.read_csv(BATCH/'canonical'/f'{symbol}.csv', usecols=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])
    frame['date'] = pd.to_datetime(frame['date'])
    if launch:
        frame = frame[frame['date'] >= pd.Timestamp(launch)]
    frame = frame[frame['date'] >= FLOOR]
    ok = (frame[['open', 'high', 'low', 'close']] > 0).all(axis=1) & np.isfinite(frame[['open', 'high', 'low', 'close', 'volume', 'amount']]).all(axis=1)
    frame = frame[ok].drop_duplicates('date').sort_values('date')
    if frame.empty:
        raise SystemExit(f'{symbol} has no rows')
    frame = frame.set_index('date')
    start = frame.index[252] if len(frame) > 252 else None
    if start is not None:
        start = max(start, MODEL_FLOOR)
    return frame, start


def account_path(frame, state, start):
    signal = pd.Series(state, index=frame.index)
    fx = pd.Series(1., index=pd.date_range('2004-01-01', '2026-10-16'))
    _, path, _, _ = run({'IDX': asset_of(frame)}, str(start.date()), '2026-10-16', policy='score_change',
                        signals={'IDX': signal}, cadence='daily', selection=keep, entry_fraction=1.,
                        cost=15, delay=0, initial_capital=1e6, fx_override=fx)
    return path.nav


def book(navs, start, end):
    if len(navs) < 2:
        return None
    frame = pd.DataFrame(navs).sort_index()
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    base_rows = frame.index[frame.index <= start]
    if not len(base_rows):
        return None
    sample = frame[(frame.index >= base_rows.max()) & (frame.index <= end)].dropna()
    if len(sample) < 2:
        return None
    rel = sample.div(sample.iloc[0])
    port = rel.mean(axis=1)
    return dict(n=int(rel.shape[1]), names=list(rel.columns),
                start=str(sample.index[0].date()), end=str(sample.index[-1].date()),
                total_return=float(port.iloc[-1] - 1),
                max_drawdown=float((port / port.cummax() - 1).min()))


def main():
    digest = sha(OUT/'protocol.json')
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    if digest != freeze['sha256'] or freeze.get('results_viewed') is not False:
        raise SystemExit('cycle-fit protocol changed after freeze')
    phase2 = json.loads((PHASE2/'protocol.json').read_text())
    coverage = {r['symbol']: r for r in json.loads((BATCH/'coverage.json').read_text())['per_symbol']}
    names = {}
    groups = {}
    for symbol, label in phase2['index_sets']['decisive_broad'].items():
        groups[symbol] = 'broad'
        names[symbol] = label.split(' (')[0]
    for symbol, label in phase2['index_sets']['decisive_sector'].items():
        groups[symbol] = 'sector'
        names[symbol] = label
    parts = {era: {group: {key: 0.0 for key in ('up_num', 'up_den', 'down_num', 'down_den')} for group in ('broad', 'sector')} for era, _, _ in ERAS}
    legs_out = []
    navs = {group: {} for group in ('broad', 'sector')}
    starts = {}
    checked = 0
    for symbol, group in groups.items():
        launch = coverage[symbol]['publication'].get('launch_date')
        full, start = load_full(symbol, launch)
        cut_frame, cut_start = load_symbol(symbol, launch)
        if not full.loc[:CUT].index.equals(cut_frame.index) or start != cut_start:
            raise SystemExit(f'{symbol} full history does not match the modeling loader')
        labels, leg_table = fixed_label(full.close, .2)
        scores = path_scores(full.close, full.amount)
        state = positive_state(scores.fast.to_numpy(), scores.slow.to_numpy())
        cut_scores = path_scores(cut_frame.close, cut_frame.amount)
        cut_state = positive_state(cut_scores.fast.to_numpy(), cut_scores.slow.to_numpy())
        aligned = pd.Series(state, index=full.index).reindex(cut_frame.index).to_numpy()
        if not np.array_equal(aligned, cut_state) or not np.allclose(scores.fast.reindex(cut_frame.index), cut_scores.fast, equal_nan=True):
            raise SystemExit(f'{symbol} state changed once later bars were added')
        checked += 1
        if start is None:
            raise SystemExit(f'{symbol} has no modeling start')
        y = labels.y.to_numpy()
        label = labels.label.to_numpy()
        ret = np.r_[np.nan, np.diff(y)]
        held = np.r_[np.nan, state[:-1]] > 0
        for era, begin, stop in ERAS:
            inside = (full.index >= start) & (full.index >= begin) & (full.index <= stop) & np.isfinite(ret)
            bucket = parts[era][group]
            for kind, num_key, den_key in (('up', 'up_num', 'up_den'), ('down', 'down_num', 'down_den')):
                mask = inside & (label == kind)
                bucket[den_key] += float(ret[mask].sum())
                bucket[num_key] += float(ret[mask & held].sum())
        start_pos = int(full.index.get_indexer([start])[0])
        for leg in leg_table.itertuples():
            if leg.provisional or leg.kind not in ('up', 'down') or leg.start < start_pos or abs(leg.move) < LARGE:
                continue
            move = np.diff(y[leg.start:leg.end+1])
            share = float(move[state[leg.start:leg.end] > 0].sum() / move.sum())
            era = 'before'
            for name, begin, stop in ERAS:
                if pd.Timestamp(begin) <= leg.start_date <= pd.Timestamp(stop):
                    era = name
                    break
            legs_out.append(dict(symbol=symbol, name=names[symbol], group=group, era=era, kind=leg.kind,
                                 start=str(pd.Timestamp(leg.start_date).date()), end=str(pd.Timestamp(leg.end_date).date()),
                                 price_return=float(math.exp(leg.move)-1), held_share=share))
        starts[symbol] = start
        navs[group][symbol] = account_path(full, state, start)
        if navs[group][symbol].index.max() < full.index.max():
            raise SystemExit(f'{symbol} account stopped before the last bar')
    summary = dict(protocol_sha256=digest, not_out_of_sample=True, not_a_pass=True, prefix_matches_cut=checked,
                   max_loaded=str(max(series.index.max() for group in navs.values() for series in group.values()).date()))
    summary['participation'] = {}
    for era, _, _ in ERAS:
        summary['participation'][era] = {}
        for group, row in parts[era].items():
            summary['participation'][era][group] = dict(
                up=row['up_num']/row['up_den'] if row['up_den'] else None,
                down=row['down_num']/row['down_den'] if row['down_den'] else None)
    leg_frame = pd.DataFrame(legs_out)
    summary['large_legs'] = {}
    for (era, group, kind), part in leg_frame.groupby(['era', 'group', 'kind']):
        weight = np.abs(np.log1p(part.price_return))
        summary['large_legs'][f'{era}:{group}:{kind}'] = dict(
            n=int(len(part)), held_share=float(np.average(part.held_share, weights=weight)),
            median_price=float(part.price_return.median()))
    summary['sleeves'] = {}
    for era, begin, stop in ERAS:
        summary['sleeves'][era] = {}
        for group, series in navs.items():
            eligible = {symbol: nav for symbol, nav in series.items() if starts[symbol] <= pd.Timestamp(begin)}
            got = book(eligible, begin, stop)
            if got:
                summary['sleeves'][era][group] = got
    leg_frame.to_csv(OUT/'large-legs.csv', index=False)
    (OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
