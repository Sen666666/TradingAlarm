"""Tradable-proxy account of frozen positive-connect on CSI300 ETF.

The state is not changed. Adjustment semantics stay unverified.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from trend_background_hold import path_scores
from trend_positive_connect import positive_state
from trend_cash_book import WINDOWS, simulate, window_stats

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'trend-etf-proxy'
DATA = ROOT/'data'/'USHJ510300.json'
LOT = 100
FAT = 0.30
KEEP = ('2013-2016', '2018-2021', '2022-2026')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_etf():
    payload = json.loads(DATA.read_text())
    frame = pd.DataFrame(payload['bars'])
    frame['date'] = pd.to_datetime(frame['date'])
    ok = (frame[['open', 'high', 'low', 'close']] > 0).all(axis=1) & np.isfinite(frame[['open', 'high', 'low', 'close', 'volume', 'amount']]).all(axis=1)
    frame = frame[ok].drop_duplicates('date').sort_values('date').set_index('date')
    if frame.index.min() != pd.Timestamp('2012-05-28') or frame.index.max() < pd.Timestamp('2026-10-01'):
        raise SystemExit('510300 coverage is not the expected file')
    return frame


def shape(rows):
    if not rows:
        return None
    wins = [row['ret'] for row in rows if row['ret'] > 0]
    losses = [row['ret'] for row in rows if row['ret'] <= 0]
    fat = [row for row in rows if row['ret'] >= FAT]
    ordinary = [row for row in rows if row['ret'] < FAT]
    payoff = None
    if wins and losses:
        payoff = (sum(wins)/len(wins)) / abs(sum(losses)/len(losses))
    return dict(n=len(rows), win_rate=len(wins)/len(rows), payoff=payoff, fat_n=len(fat),
                fat_pnl=sum(row['pnl'] for row in fat), ordinary_pnl=sum(row['pnl'] for row in ordinary))


def main():
    digest = sha(OUT/'protocol.json')
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    if digest != freeze['sha256'] or freeze.get('results_viewed') is not False:
        raise SystemExit('etf-proxy protocol changed after freeze')
    frame = load_etf()
    scores = path_scores(frame.close, frame.amount)
    state = pd.Series(positive_state(scores.fast.to_numpy(), scores.slow.to_numpy()), index=frame.index)
    cut = pd.Timestamp('2016-06-30')
    sub = frame[frame.index <= cut]
    got = positive_state(path_scores(sub.close, sub.amount).fast.to_numpy(), path_scores(sub.close, sub.amount).slow.to_numpy())
    if not np.array_equal(got, state.to_numpy()[frame.index <= cut]):
        raise SystemExit('510300 prefix mismatch')
    start = frame.index[0]
    held = state
    flat = pd.Series(1.0, index=frame.index)
    summary = dict(protocol_sha256=digest, not_out_of_sample=True, not_a_pass=True, adjustment='Q, semantics unverified', lot=LOT)
    for name, signal in (('positive_connect', held), ('buy_and_hold', flat)):
        ledger = []
        nav = simulate({'510300': frame}, {'510300': signal}, {'510300': start}, ledger, lot=LOT)
        summary[name] = dict(windows={}, trades=shape(ledger))
        for label, begin, stop in WINDOWS:
            if label not in KEEP:
                continue
            got_window = window_stats(nav, begin, stop)
            if got_window:
                summary[name]['windows'][label] = got_window
    (OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
