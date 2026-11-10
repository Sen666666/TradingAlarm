"""Background-scaled pairwise fit with a one-quarter hold.

The scale, the 21/63 windows and the pass lines are frozen in protocol.json
before this module computes any score. 2018-2021 is not opened.
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
from pairwise_trend_strength import pair_slope, pairwise_frame
from trend_target_labels import trajectory, summarize
from trend_segment_revision import fixed_label
from market_state_phase2 import CUT, load_symbol, pairwise_state, account

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'trend-background-hold'
PHASE2 = ROOT/'results'/'market-state-phase2'
BATCH = ROOT/'data'/'ths-index-history-20261018'
ENTRY = 5+5*math.tanh(1)
VIOLENT = 5-5*math.tanh(1)
PREFIX_CUTS = ('2009-06-30', '2013-06-28', '2016-06-30')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def path_scores(close, amount):
    """Fast score uses the RMS before the 21-bar window. Slow slope is the equal-weighted 63-bar fit."""
    frame = pd.concat([close.rename('close'), amount.rename('amount')], axis=1)
    valid = frame.loc[(frame > 0).all(axis=1) & np.isfinite(frame).all(axis=1)]
    y = np.log(valid.close.to_numpy())
    v = valid.amount.to_numpy()
    ret = np.r_[np.nan, np.diff(y)]
    fast = np.full(len(valid), np.nan)
    slow = np.full(len(valid), np.nan)
    background = np.full(len(valid), np.nan)
    for i in range(len(valid)):
        if i >= 62:
            slow[i] = pair_slope(y[i-62:i+1], v[i-62:i+1], recency=False)
        if i >= 83:
            slope = pair_slope(y[i-20:i+1], v[i-20:i+1], recency=True)
            window = ret[i-82:i-19]
            rms = float(np.sqrt(np.mean(window*window)))
            background[i] = rms
            if rms > 1e-12:
                fast[i] = 5+5*np.tanh(math.sqrt(5)*slope/rms)
            elif slope > 0:
                fast[i] = 10.
            elif slope < 0:
                fast[i] = 0.
            else:
                fast[i] = 5.
    out = pd.DataFrame(dict(fast=fast, slow=slow, background_rms=background), index=valid.index)
    return out.reindex(close.index)


def hold_state(fast, slow):
    """Enter on the first bar both conditions hold; exit on a dead quarter or a violent fast score."""
    fast = np.asarray(fast, float)
    slow = np.asarray(slow, float)
    held = False
    armed = False
    out = np.zeros(len(fast))
    for i, (f, s) in enumerate(zip(fast, slow)):
        violent = np.isfinite(f) and f <= VIOLENT
        dead = np.isfinite(s) and s <= 0
        ready = np.isfinite(f) and np.isfinite(s) and f >= ENTRY and s > 0
        if held and (violent or dead):
            held = False
        elif ready and not armed:
            held = True
        if np.isfinite(f) and np.isfinite(s):
            armed = ready
        out[i] = float(held)
    return out


def one_score(frame, legs, state, start):
    daily, events, entries = trajectory(frame, legs, pd.Series(state, index=frame.index), start, CUT)
    return summarize(daily, events, entries), daily


def passes(summary, base):
    up, down = summary['up_participation'], summary['down_participation']
    t_u = bool(np.isfinite(up) and np.isfinite(base['up_participation']) and up >= base['up_participation']+0.10)
    t_d = bool(np.isfinite(down) and np.isfinite(base['down_participation']) and down <= base['down_participation']+0.10)
    return t_u, t_d


def round_trips(orders, mark_price):
    """Closed trips plus a mark of anything still open at the cut."""
    cost = units = proceeds = 0.0
    trips = []
    for order in orders:
        price = float(order['raw_open'])*float(order['fx'])
        qty = float(order['units'])
        fee = float(order['fee'])
        if qty > 0:
            cost += qty*price+fee
            units += qty
        elif qty < 0 and units > 1e-8:
            sell = min(-qty, units)
            proceeds += sell*price-fee*(sell/-qty)
            units -= sell
            if units <= 1e-6 and cost > 0:
                trips.append(dict(ret=proceeds/cost-1, pnl=proceeds-cost, marked=False))
                cost = units = proceeds = 0.0
    if units > 1e-6 and cost > 0:
        fee = max(units*float(mark_price)*0.0015, 5.)
        proceeds += units*float(mark_price)-fee
        trips.append(dict(ret=proceeds/cost-1, pnl=proceeds-cost, marked=True))
    return trips


def book_of(trips, exposure):
    fat = [t for t in trips if t['ret'] >= 0.30]
    ordinary = [t for t in trips if t['ret'] < 0.30]
    wins = [t['ret'] for t in trips if t['ret'] > 0]
    losses = [t['ret'] for t in trips if t['ret'] <= 0]
    fat_pnl = float(sum(t['pnl'] for t in fat))
    ordinary_pnl = float(sum(t['pnl'] for t in ordinary))
    payoff = float(np.mean(wins)/abs(np.mean(losses))) if wins and losses else np.nan
    return dict(trades=len(trips), win_rate=float(len(wins)/len(trips)) if trips else np.nan, payoff=payoff,
                fat_pnl=fat_pnl, ordinary_pnl=ordinary_pnl, fat_trades=len(fat),
                F1=bool(fat_pnl > 0 and ordinary_pnl >= -0.25*fat_pnl),
                F2=bool(np.isfinite(payoff) and payoff >= 2), exposure=float(exposure),
                G1=bool(np.isfinite(exposure) and exposure <= 0.70))


def prefix_check(frame, scores, full):
    cuts = []
    for cut in PREFIX_CUTS:
        if (frame.index <= cut).sum() < 100:
            continue
        sub = frame[frame.index <= cut]
        got_scores = path_scores(sub.close, sub.amount)
        got = hold_state(got_scores.fast, got_scores.slow)
        mask = np.asarray(frame.index <= cut)
        ref = full[mask]
        if not np.array_equal(got, ref) or not np.allclose(got_scores.fast.to_numpy(), scores.fast.to_numpy()[mask], equal_nan=True):
            raise AssertionError(f'prefix mismatch {cut}')
        cuts.append(cut)
    return cuts


def draw(symbol, item, path, name='background_hold'):
    frame = item['frame']
    labels, legs = item['labels']
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    axes[0].plot(frame.index, labels.y, color='black', lw=.7)
    for leg in legs.itertuples():
        axes[0].axvspan(frame.index[leg.start], frame.index[leg.end], color={'up': '#b7e1cd', 'down': '#f4c7c3', 'range': '#fff2cc'}[leg.kind], alpha=.85, lw=0)
    axes[0].axvspan(frame.index[0], item['start'], color='#bbbbbb', alpha=.35, lw=0)
    axes[0].set_ylabel('log price')
    axes[1].plot(frame.index, item['scores'].fast, lw=.7, label='fast score')
    axes[1].plot(frame.index, item['pairwise_score'], lw=.6, alpha=.7, label='pairwise')
    axes[1].axhline(ENTRY, color='green', lw=.4)
    axes[1].axhline(VIOLENT, color='red', lw=.4)
    axes[1].legend(fontsize=7)
    axes[1].set_ylabel('score')
    axes[2].plot(frame.index, item['state'], lw=.7, label=name)
    axes[2].plot(frame.index, item['pairwise'], lw=.6, alpha=.7, label='pairwise_volume')
    axes[2].legend(fontsize=7)
    axes[2].set_ylim(-.05, 1.05)
    for name, series in item['paths'].items():
        axes[3].plot(series.index, series.nav, label=name)
    axes[3].legend(fontsize=7)
    axes[3].set_ylabel('NAV')
    fig.suptitle(f'{symbol} fixed20 through 2017-12-31; gray warmup is not scored')
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def pooled_parts(rows):
    up_den = sum(r['up_den'] for r in rows)
    down_den = sum(r['down_den'] for r in rows)
    up = sum(r['up_num'] for r in rows)/up_den if up_den else np.nan
    down = sum(r['down_num'] for r in rows)/down_den if down_den else np.nan
    return up, down


def main():
    digest = sha(OUT/'protocol.json')
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    if digest != freeze['sha256']:
        raise SystemExit('background-hold protocol changed after freeze')
    phase2 = json.loads((PHASE2/'protocol.json').read_text())
    coverage = {r['symbol']: r for r in json.loads((BATCH/'coverage.json').read_text())['per_symbol']}
    groups = {}
    for symbol in phase2['index_sets']['decisive_broad']:
        groups[symbol] = ('decisive', 'broad')
    for symbol in phase2['index_sets']['decisive_sector']:
        groups[symbol] = ('decisive', 'sector')
    for symbol in phase2['index_sets']['separate_report_only']:
        if symbol != 'reason':
            groups[symbol] = ('separate', 'csi_l1')
    rows = []
    books = []
    account_rows = []
    decisions = []
    prefix = []
    cache = {}
    for symbol, (role, group) in groups.items():
        launch = coverage[symbol]['publication'].get('launch_date')
        frame, start = load_symbol(symbol, launch)
        if frame.index.max() > CUT or start is None:
            raise SystemExit(f'{symbol} is outside the modeling cut')
        labels, legs = fixed_label(frame.close, .2)
        scores = path_scores(frame.close, frame.amount)
        state = hold_state(scores.fast, scores.slow)
        pairwise = pairwise_state(frame.close, frame.amount, 5.)
        pairwise_score = pairwise_frame(frame.close, frame.amount.where(frame.amount > 0))['strength']
        prefix.extend(dict(symbol=symbol, cut=cut) for cut in prefix_check(frame, scores, state))
        base, _ = one_score(labels, legs, pairwise, start)
        summary, daily = one_score(labels, legs, state, start)
        t_u, t_d = passes(summary, base)
        up = daily[daily.label.eq('up')]
        down = daily[daily.label.eq('down')]
        rows.append(dict(symbol=symbol, role=role, group=group, T_U=t_u, T_D=t_d, up=summary['up_participation'], down=summary['down_participation'],
                         range_time=summary['range_time'], up_base=base['up_participation'], down_base=base['down_participation'],
                         up_num=float(up.hr.sum()), up_den=float(up.r.sum()), down_num=float(down.hr.sum()), down_den=float(down.r.sum())))
        exposure = float(state[frame.index >= start].mean())
        item = dict(frame=frame, start=start, role=role, group=group, labels=(labels, legs), scores=scores, state=state,
                    pairwise=pairwise, pairwise_score=pairwise_score, exposure=exposure, paths={})
        cache[symbol] = item
        for name, held, scenarios in (
            ('background_hold', state, (('base', 15, 0), ('cost2', 30, 0), ('delay1', 15, 1))),
            ('pairwise_volume', pairwise, (('base', 15, 0),)),
            ('buy_and_hold', np.ones(len(frame)), (('base', 15, 0),)),
        ):
            for scenario, cost, delay in scenarios:
                metrics, path, orders = account(frame, held, start, cost, delay)
                if path.index.max() > CUT:
                    raise SystemExit('account passed the cut')
                account_rows.append(dict(symbol=symbol, role=role, group=group, state=name, scenario=scenario, total_return=metrics['total_return'],
                                         log_return=math.log1p(metrics['total_return']), max_drawdown=metrics['max_drawdown'], orders=metrics['orders'],
                                         last=str(path.index.max().date())))
                if scenario == 'base':
                    item['paths'][name] = path
                    if name == 'background_hold':
                        trips = round_trips(orders, frame.close.iloc[-1])
                        row = book_of(trips, exposure)
                        row.update(symbol=symbol, role=role, group=group, state=name)
                        books.append(row)
                        item['book'] = row
                        item['trips'] = trips
    verdict = dict(groups={})
    for group, need in (('broad', 6), ('sector', 7)):
        members = [s for s, item in cache.items() if item['group'] == group and item['role'] == 'decisive']
        part = [r for r in rows if r['group'] == group and r['role'] == 'decisive']
        up, down = pooled_parts(part)
        base_rows = []
        for symbol in members:
            item = cache[symbol]
            summary, daily = one_score(item['labels'][0], item['labels'][1], item['pairwise'], item['start'])
            up_d = daily[daily.label.eq('up')]
            down_d = daily[daily.label.eq('down')]
            base_rows.append(dict(up_num=float(up_d.hr.sum()), up_den=float(up_d.r.sum()), down_num=float(down_d.hr.sum()), down_den=float(down_d.r.sum())))
        b_up, b_down = pooled_parts(base_rows)
        both = sum(r['T_U'] and r['T_D'] for r in part)
        group_books = [cache[s]['book'] for s in members]
        trips_view = dict(fat_pnl=sum(b['fat_pnl'] for b in group_books), ordinary_pnl=sum(b['ordinary_pnl'] for b in group_books))
        wins = []
        losses = []
        for symbol in members:
            for trip in cache[symbol]['trips']:
                (wins if trip['ret'] > 0 else losses).append(trip['ret'])
        payoff = float(np.mean(wins)/abs(np.mean(losses))) if wins and losses else np.nan
        exposure = float(np.mean([cache[s]['exposure'] for s in members]))
        t_u = bool(np.isfinite(up) and up >= b_up+0.10)
        t_d = bool(np.isfinite(down) and down <= b_down+0.10)
        f1 = bool(trips_view['fat_pnl'] > 0 and trips_view['ordinary_pnl'] >= -0.25*trips_view['fat_pnl'])
        f2 = bool(np.isfinite(payoff) and payoff >= 2)
        g1 = bool(exposure <= 0.70)
        verdict['groups'][group] = dict(pooled_T_U=t_u, pooled_T_D=t_d, both=both, need=need, U=up, D=down, U_base=b_up, D_base=b_down,
                                        F1=f1, F2=f2, G1=g1, payoff=payoff, win_rate=float(len(wins)/(len(wins)+len(losses))) if wins or losses else np.nan,
                                        fat_pnl=trips_view['fat_pnl'], ordinary_pnl=trips_view['ordinary_pnl'], exposure=exposure, trades=len(wins)+len(losses),
                                        pass_group=bool(t_u and t_d and both >= need and f1 and f2 and g1))
        for row in part:
            decisions.append(dict(symbol=row['symbol'], group=group, role='decisive', T_U=row['T_U'], T_D=row['T_D'], up=row['up'], down=row['down']))
    for row in rows:
        if row['role'] != 'decisive':
            decisions.append(dict(symbol=row['symbol'], group=row['group'], role=row['role'], T_U=row['T_U'], T_D=row['T_D'], up=row['up'], down=row['down']))
    verdict['passed'] = all(v['pass_group'] for v in verdict['groups'].values())
    figures = []
    for symbol in ('USHI1A0001', 'USHI1B0300'):
        fig = OUT/f'{symbol}-background-hold.png'
        draw(symbol, cache[symbol], fig)
        figures.append(str(fig.relative_to(ROOT)))
    pd.DataFrame(rows).to_csv(OUT/'trajectory.csv', index=False)
    pd.DataFrame(account_rows).to_csv(OUT/'accounts.csv', index=False)
    pd.DataFrame(books).to_csv(OUT/'books.csv', index=False)
    pd.DataFrame(decisions).to_csv(OUT/'decisions.csv', index=False)
    validation = dict(protocol_sha256=digest, evaluation_opened=False, tail_rows_after_cut=0, prefix_checks=len(prefix),
                      selected=verdict, figures=figures, max_loaded=max(str(item['frame'].index.max().date()) for item in cache.values()))
    (OUT/'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2)+'\n')
    (OUT/'README.md').write_text(readme(verdict))
    print(json.dumps(verdict, ensure_ascii=False, default=str))


def readme(verdict):
    lines = ['# 背景尺度持有，建模期', '', '量价斜率的尺度用窗口之前 63 根的波动。慢斜率用 63 日等权拟合。2018–2021 没有计算。', '',
             f"建模期{'通过' if verdict['passed'] else '未通过'}。", '']
    for group, row in verdict['groups'].items():
        lines.append(f"- {group}: 上行 {row['U']:.3f}（对照 {row['U_base']:.3f}），下行 {row['D']:.3f}（对照 {row['D_base']:.3f}），T_U/T_D = {row['pooled_T_U']}/{row['pooled_T_D']}，单指数两项都过 {row['both']}/{row['need']}")
        lines.append(f"  胜率 {row['win_rate']:.3f}，盈亏比 {row['payoff']:.3f}，肥尾盈亏 {row['fat_pnl']:.0f}，普通盈亏 {row['ordinary_pnl']:.0f}，持仓比例 {row['exposure']:.3f}，F1/F2/G1 = {row['F1']}/{row['F2']}/{row['G1']}")
    lines.append('')
    return '\n'.join(lines)+'\n'


if __name__ == '__main__':
    main()
