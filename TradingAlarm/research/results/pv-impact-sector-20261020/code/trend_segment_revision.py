"""Relabel modeling-window index paths with a fixed-percentage trend segment.

The segment rule reads future prices and is an evaluation target only. Frozen
states are rescored; their parameters are not changed and 2018-2021 is not opened.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from trend_target_labels import zigzag, legs_from, label_frame, oracle_state, trajectory, summarize
from market_state_phase2 import CUT, load_symbol, states_for, account

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'trend-segment-revision'
PHASE2 = ROOT/'results'/'market-state-phase2'
BATCH = ROOT/'data'/'ths-index-history-20261018'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fixed_label(close, retrace):
    """Zigzag whose reversal bar is a constant log move, not a multiple of trailing sigma."""
    y = np.log(close.astype(float))
    level = math.log(1+retrace)
    threshold = np.full(len(y), level)
    pivots, prov = zigzag(y.to_numpy(), threshold)
    legs = legs_from(y.index, y.to_numpy(), threshold, pivots, prov, 1.)
    label = np.full(len(y), '', dtype=object)
    for row in legs.itertuples():
        label[row.start+1:row.end+1] = row.kind
    return pd.DataFrame(dict(y=y, label=label), index=y.index), legs


def overlap(legs, start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    return legs[(legs.end_date >= start) & (legs.start_date <= end)]


def pooled(cache, members, state_name, labels_name):
    daily, events, entries = [], [], []
    for symbol in members:
        item = cache[symbol]
        frame, legs = item['labels'][labels_name]
        state = pd.Series(item['states'][state_name], index=item['frame'].index)
        d, e, n = trajectory(frame, legs, state, item['start'], CUT)
        daily.append(d)
        events.append(e)
        entries.append(n)
    return summarize(pd.concat(daily, ignore_index=True), pd.concat(events, ignore_index=True), pd.concat(entries, ignore_index=True))


def draw(symbol, item, path):
    frame = item['frame']
    fig, axes = plt.subplots(2, 1, figsize=(12, 7), sharex=True)
    for ax, name, title in ((axes[0], 'settingA', 'setting A: reversal = 2 monthly sigma'), (axes[1], 'fixed20', 'fixed20: reversal = 20 percent')):
        labels, legs = item['labels'][name]
        ax.plot(frame.index, labels.y, color='black', lw=.7)
        for leg in legs.itertuples():
            ax.axvspan(frame.index[leg.start], frame.index[leg.end], color={'up': '#b7e1cd', 'down': '#f4c7c3', 'range': '#fff2cc'}[leg.kind], alpha=.85, lw=0)
        ax.axvspan(frame.index[0], item['start'], color='#bbbbbb', alpha=.35, lw=0)
        ax.set_ylabel('log price')
        ax.set_title(title, fontsize=9)
    fig.suptitle(f'{symbol} through 2017-12-31; gray warmup is not scored')
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    digest = sha(OUT/'protocol.json')
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    if digest != freeze['sha256']:
        raise SystemExit('segment protocol changed after freeze')
    protocol = json.loads((PHASE2/'protocol.json').read_text())
    coverage = {r['symbol']: r for r in json.loads((BATCH/'coverage.json').read_text())['per_symbol']}
    groups = {}
    for symbol in protocol['index_sets']['decisive_broad']:
        groups[symbol] = ('decisive', 'broad')
    for symbol in protocol['index_sets']['decisive_sector']:
        groups[symbol] = ('decisive', 'sector')
    for symbol, name in protocol['index_sets']['separate_report_only'].items():
        if symbol != 'reason':
            groups[symbol] = ('separate', 'csi_l1')
    definitions = [('fixed20', .2), ('fixed10', .1), ('fixed30', .3)]
    cache = {}
    leg_rows = []
    for symbol, (role, group) in groups.items():
        launch = coverage[symbol]['publication'].get('launch_date')
        frame, start = load_symbol(symbol, launch)
        if frame.index.max() > CUT or start is None:
            raise SystemExit(f'{symbol} is outside the modeling cut')
        states, _, _ = states_for(frame)
        labels = {'settingA': label_frame(frame.close, 2., 2.)}
        for name, retrace in definitions:
            labels[name] = fixed_label(frame.close, retrace)
        cache[symbol] = dict(frame=frame, start=start, role=role, group=group, states=states, labels=labels)
        for name in ('settingA', 'fixed20', 'fixed10', 'fixed30'):
            for window, w0, w1 in (('2008', '2007-10-01', '2009-03-31'), ('2015', '2014-07-01', '2016-01-31')):
                for leg in overlap(labels[name][1], w0, w1).itertuples():
                    leg_rows.append(dict(symbol=symbol, role=role, group=group, definition=name, window=window, kind=leg.kind, move=float(leg.move), provisional=bool(leg.provisional), start=str(pd.Timestamp(leg.start_date).date()), end=str(pd.Timestamp(leg.end_date).date())))
    score_rows = []
    for labels_name in ('settingA', 'fixed20', 'fixed10', 'fixed30'):
        for group in ('broad', 'sector'):
            members = [s for s, item in cache.items() if item['group'] == group and item['role'] == 'decisive']
            for state_name in ('M1_2_2', 'M2_2_2', 'pairwise_volume', 'medium63'):
                summary = pooled(cache, members, state_name, labels_name)
                score_rows.append(dict(definition=labels_name, group=group, state=state_name, up=summary['up_participation'], down=summary['down_participation'], range_time=summary['range_time'], up_legs=summary['up_legs']))
    reclass = []
    for symbol, item in cache.items():
        old = item['labels']['settingA'][1]
        ranges = old[old.kind.eq('range') & old.provisional.eq(False)]
        big = ranges[ranges.move.abs() >= math.log(1.2)]
        reclass.append(dict(symbol=symbol, group=item['group'], completed_range_legs=int(len(ranges)), range_legs_at_least_20pct=int(len(big))))
    oracle_rows = []
    for symbol, item in cache.items():
        frame, legs = item['labels']['fixed20']
        state, _ = oracle_state(frame.y, legs, 10, .1)
        metrics, path, _ = account(item['frame'], state.to_numpy(), item['start'], 15, 0)
        if path.index.max() > CUT:
            raise SystemExit('oracle account passed the cut')
        oracle_rows.append(dict(symbol=symbol, role=item['role'], group=item['group'], total_return=metrics['total_return'], max_drawdown=metrics['max_drawdown'], orders=metrics['orders'], last=str(path.index.max().date()), non_tradable=True))
    figures = []
    for symbol in ('USHI1A0001', 'USHI1B0300'):
        fig = OUT/f'{symbol}-segments.png'
        draw(symbol, cache[symbol], fig)
        figures.append(str(fig.relative_to(ROOT)))
    pd.DataFrame(leg_rows).to_csv(OUT/'window-legs.csv', index=False)
    pd.DataFrame(score_rows).to_csv(OUT/'scores.csv', index=False)
    pd.DataFrame(reclass).to_csv(OUT/'range-reclass.csv', index=False)
    pd.DataFrame(oracle_rows).to_csv(OUT/'oracle-fixed20.csv', index=False)
    validation = dict(protocol_sha256=digest, evaluation_opened=False, parameters_changed=False, tail_rows_after_cut=0, max_loaded=max(str(item['frame'].index.max().date()) for item in cache.values()), figures=figures, symbols=len(cache))
    (OUT/'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(score_rows, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
