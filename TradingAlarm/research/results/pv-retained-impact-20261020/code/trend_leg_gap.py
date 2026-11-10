"""Split each fixed20 up leg into before entry, held, mid-flat and after exit.

Uses the frozen background_hold state. 2018-2021 is not opened.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from trend_segment_revision import fixed_label
from trend_background_hold import path_scores, hold_state
from market_state_phase2 import CUT, load_symbol

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'trend-leg-gap'
PHASE2 = ROOT/'results'/'market-state-phase2'
BATCH = ROOT/'data'/'ths-index-history-20261018'
LARGE = math.log(1.5)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def split_leg(y, state, start, end):
    """Returns before, held, gap, after. The return into bar t uses the state at t-1."""
    r = np.diff(y[start:end+1])
    held_at = state[start:end]
    if len(r) != len(held_at):
        raise SystemExit('leg slice mismatch')
    on = np.flatnonzero(held_at > 0)
    before = held = gap = after = 0.0
    if not len(on):
        return float(r.sum()), 0.0, 0.0, 0.0
    first, last = int(on[0]), int(on[-1])
    before = float(r[:first].sum())
    after = float(r[last+1:].sum())
    mid = r[first:last+1]
    flag = held_at[first:last+1] > 0
    held = float(mid[flag].sum())
    gap = float(mid[~flag].sum())
    return before, held, gap, after


def main():
    digest = sha(OUT/'protocol.json')
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    if digest != freeze['sha256']:
        raise SystemExit('leg-gap protocol changed after freeze')
    phase2 = json.loads((PHASE2/'protocol.json').read_text())
    coverage = {r['symbol']: r for r in json.loads((BATCH/'coverage.json').read_text())['per_symbol']}
    groups = {}
    for symbol in phase2['index_sets']['decisive_broad']:
        groups[symbol] = 'broad'
    for symbol in phase2['index_sets']['decisive_sector']:
        groups[symbol] = 'sector'
    rows = []
    for symbol, group in groups.items():
        launch = coverage[symbol]['publication'].get('launch_date')
        frame, start = load_symbol(symbol, launch)
        if frame.index.max() > CUT or start is None:
            raise SystemExit(f'{symbol} is outside the modeling cut')
        labels, legs = fixed_label(frame.close, .2)
        scores = path_scores(frame.close, frame.amount)
        state = hold_state(scores.fast, scores.slow)
        y = labels.y.to_numpy()
        for leg in legs.itertuples():
            if leg.kind != 'up' or leg.provisional or leg.start_date < start:
                continue
            before, held, gap, after = split_leg(y, state, leg.start, leg.end)
            move = float(leg.move)
            if not np.isclose(before+held+gap+after, move, atol=1e-8):
                raise SystemExit(f'split does not add up {symbol} {leg.start_date}')
            rows.append(dict(symbol=symbol, group=group, start=str(pd.Timestamp(leg.start_date).date()), end=str(pd.Timestamp(leg.end_date).date()),
                                move=move, price_return=math.exp(move)-1, large=bool(move >= LARGE),
                                before=before, held=held, gap=gap, after=after,
                                before_share=before/move, held_share=held/move, gap_share=gap/move, after_share=after/move))
    table = pd.DataFrame(rows)
    table.to_csv(OUT/'gaps.csv', index=False)

    def pool(part):
        move = float(part['move'].sum())
        return dict(legs=int(len(part)), move=move,
                    before=float(part.before.sum()/move), held=float(part.held.sum()/move),
                    gap=float(part.gap.sum()/move), after=float(part.after.sum()/move),
                    median_held_share=float(part.held_share.median()), median_before_share=float(part.before_share.median()),
                    median_after_share=float(part.after_share.median()))

    summary = dict(protocol_sha256=digest, evaluation_opened=False, max_bar='2017-12-31',
                   all=pool(table), large=pool(table[table.large]), small=pool(table[~table.large]))
    (OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    lines = ['# 上行段涨幅落在哪里，建模期', '', '状态是 background_hold。四份份额按对数涨幅加权，加总为 1。2018–2021 没有计算。', '']
    for name in ('all', 'large', 'small'):
        row = summary[name]
        lines.append(f"- {name}: {row['legs']} 段，进场前 {row['before']:.3f}，持仓 {row['held']:.3f}，中途空仓 {row['gap']:.3f}，离场后 {row['after']:.3f}")
    lines.append('')
    (OUT/'README.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
