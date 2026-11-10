"""Account return inside each fixed20 up leg, using the frozen background-hold state.

No new parameter. 2018-2021 is not opened.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from trend_segment_revision import fixed_label
from trend_background_hold import path_scores, hold_state, account
from market_state_phase2 import CUT, load_symbol

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'trend-leg-capture'
PHASE2 = ROOT/'results'/'market-state-phase2'
BATCH = ROOT/'data'/'ths-index-history-20261018'
LARGE = math.log(1.5)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def leg_account_return(nav, start, end):
    before = nav[nav.index <= start]
    inside = nav[(nav.index > start) & (nav.index <= end)]
    if before.empty or inside.empty:
        return None
    return float(inside.iloc[-1]/before.iloc[-1]-1)


def main():
    digest = sha(OUT/'protocol.json')
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    if digest != freeze['sha256']:
        raise SystemExit('leg-capture protocol changed after freeze')
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
        metrics, path, _ = account(frame, state, start, 15, 0)
        if path.index.max() > CUT:
            raise SystemExit('account passed the cut')
        for leg in legs.itertuples():
            if leg.kind != 'up' or leg.start_date < start:
                continue
            gained = leg_account_return(path.nav, leg.start_date, leg.end_date)
            if gained is None:
                continue
            rows.append(dict(symbol=symbol, group=group, start=str(pd.Timestamp(leg.start_date).date()), end=str(pd.Timestamp(leg.end_date).date()),
                                provisional=bool(leg.provisional), price_return=math.exp(leg.move)-1, account_return=gained,
                                large=bool(leg.move >= LARGE), hit_80=bool(gained >= 0.80)))
    table = pd.DataFrame(rows)
    table.to_csv(OUT/'legs.csv', index=False)
    done = table[~table.provisional]
    large = done[done.large]
    summary = dict(protocol_sha256=digest, evaluation_opened=False, max_loaded=str(max(pd.Timestamp(r['end']) for r in rows).date()) if rows else None,
                   completed_legs=int(len(done)), completed_hit_80=int(done.hit_80.sum()) if len(done) else 0,
                   completed_median_account=float(done.account_return.median()) if len(done) else None,
                   completed_max_account=float(done.account_return.max()) if len(done) else None,
                   large_legs=int(len(large)), large_hit_80=int(large.hit_80.sum()) if len(large) else 0,
                   large_median_account=float(large.account_return.median()) if len(large) else None,
                   large_max_account=float(large.account_return.max()) if len(large) else None,
                   large_median_price=float(large.price_return.median()) if len(large) else None)
    (OUT/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2)+'\n')
    lines = ['# 冻结状态在单段上行里的账户涨幅', '', '规则是 background_hold，没有新参数。段的划分用到未来价格。2018–2021 没有计算。', '']
    lines.append(f"已完成的上行段 {summary['completed_legs']} 段，账户涨幅中位 {summary['completed_median_account']:.3f}，最大 {summary['completed_max_account']:.3f}，达到 80% 的 {summary['completed_hit_80']} 段。")
    lines.append(f"其中价格涨幅至少 50% 的 {summary['large_legs']} 段，价格中位 {summary['large_median_price']:.3f}，账户中位 {summary['large_median_account']:.3f}，最大 {summary['large_max_account']:.3f}，达到 80% 的 {summary['large_hit_80']} 段。")
    lines.append('')
    (OUT/'README.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
