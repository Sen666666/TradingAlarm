"""One cash account of the local equity ETFs under the quiet-scale state.

The state and the cash rule are not changed. Adjustment semantics stay unverified.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from trend_cash_book import WINDOWS, simulate, window_stats
from trend_equal_weight import equal_scores
from trend_etf_proxy import shape
from trend_quiet_scale import quiet_entry
from trend_slow_pause import pause_state

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'trend-quiet-book'
DATA = ROOT/'data'
ETF_BASE = ROOT/'results'/'trend-quiet-scale'/'validation.json'
LOT = 100
KEEP = ('2013-2016', '2018-2021', '2022-2026')
BULL = ('2013-07-01', '2016-06-30')
NAMES = (
    ('510300', '沪深300', '2012-05-28'),
    ('512010', '医药', '2013-10-28'),
    ('512660', '军工', '2016-08-08'),
    ('512800', '银行', '2017-08-03'),
    ('513050', '中概互联网', '2017-01-18'),
    ('512480', '半导体', '2019-06-12'),
    ('515030', '新能源', '2020-03-04'),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_one(code, first):
    payload = json.loads((DATA/f'USHJ{code}.json').read_text())
    frame = pd.DataFrame(payload['bars'])
    frame['date'] = pd.to_datetime(frame['date'])
    ok = (frame[['open', 'high', 'low', 'close']] > 0).all(axis=1) & np.isfinite(frame[['open', 'high', 'low', 'close', 'volume', 'amount']]).all(axis=1)
    frame = frame[ok].drop_duplicates('date').sort_values('date').set_index('date')
    if frame.empty or frame.index.min() != pd.Timestamp(first) or frame.index.max() < pd.Timestamp('2026-10-01'):
        raise SystemExit(f'{code} coverage is not the expected file')
    return frame


def state_of(frame):
    scores = equal_scores(frame.close, frame.amount)
    opener = quiet_entry(frame.close, frame.amount, scores)
    return pd.Series(pause_state(opener.to_numpy(), scores.fast.to_numpy(), scores.slow.to_numpy()), index=frame.index)


def prefix_ok(frame, state):
    cut = pd.Timestamp('2016-06-30')
    sub = frame[frame.index <= cut]
    if len(sub) < 100:
        return True
    got = state_of(sub)
    return np.array_equal(got.to_numpy(), state.to_numpy()[frame.index <= cut])


def windows_of(nav):
    out = {}
    for label, begin, stop in WINDOWS:
        if label not in KEEP:
            continue
        got = window_stats(nav, begin, stop)
        if got:
            out[label] = got
    return out


def names_in_window(ledger, begin, end):
    start, stop = pd.Timestamp(begin), pd.Timestamp(end)
    found = set()
    for row in ledger:
        if pd.Timestamp(row['entry']) <= stop and pd.Timestamp(row['exit']) >= start:
            found.add(row['symbol'])
    return sorted(found)


def main():
    digest = sha(OUT/'protocol.json')
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    if digest != freeze['sha256'] or freeze.get('results_viewed') is not False:
        raise SystemExit('quiet-book protocol changed after freeze')
    frames, states, starts = {}, {}, {}
    summary = dict(protocol_sha256=digest, not_out_of_sample=True, not_a_pass=True,
                   adjustment='Q, semantics unverified', lot=LOT, names={})
    for code, label, first in NAMES:
        frame = load_one(code, first)
        state = state_of(frame)
        if not prefix_ok(frame, state):
            raise SystemExit(f'{code} prefix mismatch')
        frames[code] = frame
        states[code] = state
        starts[code] = frame.index[0]
        alone = []
        nav = simulate({code: frame}, {code: state}, {code: frame.index[0]}, alone, lot=LOT)
        summary['names'][code] = dict(label=label, first=first, windows=windows_of(nav), trades=shape(alone))
    baseline = json.loads(ETF_BASE.read_text())['selected']['etf']['2013-2016']['total_return']
    got = summary['names']['510300']['windows']['2013-2016']['total_return']
    if abs(got - baseline) > 1e-9:
        raise SystemExit(f'510300 bull window drifted: {got} vs {baseline}')
    book_ledger = []
    flat = {code: pd.Series(1.0, index=frame.index) for code, frame in frames.items()}
    for name, signal, sink in (('quiet_scale', states, book_ledger), ('buy_and_hold', flat, [])):
        nav = simulate(frames, signal, starts, sink, lot=LOT)
        trades = shape(sink)
        bull_names = names_in_window(sink, *BULL)
        summary[name] = dict(windows=windows_of(nav), trades=trades, bull_names=bull_names)
    book = summary['quiet_scale']
    bull = book['windows'].get('2013-2016')
    bull_rows = [row for row in book_ledger if pd.Timestamp(row['entry']) <= pd.Timestamp(BULL[1]) and pd.Timestamp(row['exit']) >= pd.Timestamp(BULL[0])]
    window_trades = shape(bull_rows) or {}
    fat = window_trades.get('fat_pnl') or 0.0
    ordinary = window_trades.get('ordinary_pnl') or 0.0
    summary['bull_window_trades'] = window_trades
    summary['research_window_clears_80'] = bool(
        bull and bull['total_return'] > 0.80 and fat > 0 and ordinary >= -0.25 * fat and len(book['bull_names']) >= 2)
    summary['single_name_window'] = bool(len(book['bull_names']) < 2)
    summary['not_a_pass'] = True
    (OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
