"""Pairwise slope with recency kept and amount weights removed.

Adoption uses the frozen CSI300 ETF bull window. Identical holds do not replace positive-connect.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from pairwise_trend_strength import pair_slope, pairwise_frame
from trend_segment_revision import fixed_label
from trend_background_hold import path_scores, one_score, passes, round_trips, book_of, draw, pooled_parts
from trend_positive_connect import NEUTRAL, positive_state
from trend_leg_gap import LARGE, split_leg
from trend_leg_capture import leg_account_return
from trend_cash_book import WINDOWS, simulate, window_stats
from trend_etf_proxy import load_etf, LOT
from market_state_phase2 import CUT, load_symbol, pairwise_state, account

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'trend-equal-weight'
ETF_BASE = ROOT/'results'/'trend-etf-proxy'/'summary.json'
PHASE2 = ROOT/'results'/'market-state-phase2'
BATCH = ROOT/'data'/'ths-index-history-20261018'
PREFIX_CUTS = ('2009-06-30', '2013-06-28', '2016-06-30')
KEEP = ('2013-2016', '2018-2021', '2022-2026')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def equal_scores(close, amount):
    """Same bars and background RMS as path_scores. Pair slopes ignore amount."""
    frame = pd.concat([close.rename('close'), amount.rename('amount')], axis=1)
    valid = frame.loc[(frame > 0).all(axis=1) & np.isfinite(frame).all(axis=1)]
    y = np.log(valid.close.to_numpy(dtype=float))
    ret = np.r_[np.nan, np.diff(y)]
    fast = np.full(len(valid), np.nan)
    slow = np.full(len(valid), np.nan)
    background = np.full(len(valid), np.nan)
    for i in range(len(valid)):
        if i >= 62:
            slow[i] = pair_slope(y[i - 62:i + 1], None, recency=False)
        if i >= 83:
            slope = pair_slope(y[i - 20:i + 1], None, recency=True)
            window = ret[i - 82:i - 19]
            rms = float(np.sqrt(np.mean(window * window)))
            background[i] = rms
            if rms > 1e-12:
                fast[i] = 5 + 5 * math.tanh(math.sqrt(5) * slope / rms)
            elif slope > 0:
                fast[i] = 10.
            elif slope < 0:
                fast[i] = 0.
            else:
                fast[i] = 5.
    out = pd.DataFrame(dict(fast=fast, slow=slow, background_rms=background), index=valid.index)
    return out.reindex(close.index)


def prefix_check(frame, scores, full):
    cuts = []
    for cut in PREFIX_CUTS:
        if (frame.index <= cut).sum() < 100:
            continue
        sub = frame[frame.index <= cut]
        got_scores = equal_scores(sub.close, sub.amount)
        got = positive_state(got_scores.fast.to_numpy(), got_scores.slow.to_numpy())
        mask = np.asarray(frame.index <= cut)
        if not np.array_equal(got, full[mask]) or not np.allclose(got_scores.fast.to_numpy(), scores.fast.to_numpy()[mask], equal_nan=True):
            raise AssertionError(f'prefix mismatch {cut}')
        cuts.append(cut)
    return cuts


def main():
    digest = sha(OUT/'protocol.json')
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    if digest != freeze['sha256'] or freeze.get('results_viewed') is not False:
        raise SystemExit('equal-weight protocol changed after freeze')
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
    rows, books, account_rows, decisions, prefix, legs, cache = [], [], [], [], [], [], {}
    changed = 0
    for symbol, (role, group) in groups.items():
        launch = coverage[symbol]['publication'].get('launch_date')
        frame, start = load_symbol(symbol, launch)
        if frame.index.max() > CUT or start is None:
            raise SystemExit(f'{symbol} is outside the modeling cut')
        labels, leg_table = fixed_label(frame.close, .2)
        reference = path_scores(frame.close, frame.amount)
        scores = equal_scores(frame.close, frame.amount)
        state = positive_state(scores.fast.to_numpy(), scores.slow.to_numpy())
        previous = positive_state(reference.fast.to_numpy(), reference.slow.to_numpy())
        if role == 'decisive':
            changed += int(np.sum(state != previous))
        pairwise = pairwise_state(frame.close, frame.amount, NEUTRAL)
        pairwise_score = pairwise_frame(frame.close, frame.amount.where(frame.amount > 0))['strength']
        prefix.extend(dict(symbol=symbol, cut=cut) for cut in prefix_check(frame, scores, state))
        base, _ = one_score(labels, leg_table, pairwise, start)
        summary, daily = one_score(labels, leg_table, state, start)
        _old_summary, old_daily = one_score(labels, leg_table, previous, start)
        t_u, t_d = passes(summary, base)
        up, down = daily[daily.label.eq('up')], daily[daily.label.eq('down')]
        rows.append(dict(symbol=symbol, role=role, group=group, T_U=t_u, T_D=t_d, up=summary['up_participation'], down=summary['down_participation'],
                         range_time=summary['range_time'], up_base=base['up_participation'], down_base=base['down_participation'],
                         up_num=float(up.hr.sum()), up_den=float(up.r.sum()), down_num=float(down.hr.sum()), down_den=float(down.r.sum())))
        exposure = float(state[frame.index >= start].mean())
        old_up_days, old_down_days = old_daily[old_daily.label.eq('up')], old_daily[old_daily.label.eq('down')]
        item = dict(frame=frame, start=start, role=role, group=group, labels=(labels, leg_table), scores=scores, state=state,
                    old_parts=dict(up_num=float(old_up_days.hr.sum()), up_den=float(old_up_days.r.sum()),
                                   down_num=float(old_down_days.hr.sum()), down_den=float(old_down_days.r.sum())),
                    pairwise=pairwise, pairwise_score=pairwise_score, exposure=exposure, paths={})
        cache[symbol] = item
        y = labels.y.to_numpy()
        for name, held, scenarios in (
            ('equal_weight', state, (('base', 15, 0), ('cost2', 30, 0), ('delay1', 15, 1))),
            ('positive_connect', previous, (('base', 15, 0),)),
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
                    if name == 'equal_weight':
                        trips = round_trips(orders, frame.close.iloc[-1])
                        row = book_of(trips, exposure)
                        row.update(symbol=symbol, role=role, group=group, state=name)
                        books.append(row)
                        item['book'] = row
                        item['trips'] = trips
                    if role == 'decisive' and name in ('equal_weight', 'positive_connect'):
                        for leg in leg_table.itertuples():
                            if leg.kind != 'up' or leg.provisional or leg.start_date < start or leg.move < LARGE:
                                continue
                            before, held_move, gap, after = split_leg(y, held, leg.start, leg.end)
                            gained = leg_account_return(path.nav, leg.start_date, leg.end_date)
                            if gained is None or not np.isclose(before+held_move+gap+after, leg.move, atol=1e-8):
                                continue
                            legs.append(dict(symbol=symbol, group=group, state=name, start=str(pd.Timestamp(leg.start_date).date()), end=str(pd.Timestamp(leg.end_date).date()),
                                             price_return=math.exp(leg.move)-1, account_return=gained, before_share=before/leg.move, held_share=held_move/leg.move,
                                             hit_80=gained >= 0.80))
    verdict = dict(groups={})
    for group, need in (('broad', 6), ('sector', 7)):
        members = [s for s, item in cache.items() if item['group'] == group and item['role'] == 'decisive']
        part = [r for r in rows if r['group'] == group and r['role'] == 'decisive']
        up, down = pooled_parts(part)
        base_rows = []
        for symbol in members:
            summary, daily = one_score(cache[symbol]['labels'][0], cache[symbol]['labels'][1], cache[symbol]['pairwise'], cache[symbol]['start'])
            up_d, down_d = daily[daily.label.eq('up')], daily[daily.label.eq('down')]
            base_rows.append(dict(up_num=float(up_d.hr.sum()), up_den=float(up_d.r.sum()), down_num=float(down_d.hr.sum()), down_den=float(down_d.r.sum())))
        b_up, b_down = pooled_parts(base_rows)
        both = sum(r['T_U'] and r['T_D'] for r in part)
        group_books = [cache[s]['book'] for s in members]
        wins, losses = [], []
        for symbol in members:
            for trip in cache[symbol]['trips']:
                (wins if trip['ret'] > 0 else losses).append(trip['ret'])
        payoff = float(np.mean(wins)/abs(np.mean(losses))) if wins and losses else np.nan
        exposure = float(np.mean([cache[s]['exposure'] for s in members]))
        fat_pnl = sum(b['fat_pnl'] for b in group_books)
        ordinary_pnl = sum(b['ordinary_pnl'] for b in group_books)
        t_u = bool(np.isfinite(up) and up >= b_up+0.10)
        t_d = bool(np.isfinite(down) and down <= b_down+0.10)
        f1 = bool(fat_pnl > 0 and ordinary_pnl >= -0.25*fat_pnl)
        f2 = bool(np.isfinite(payoff) and payoff >= 2)
        g1 = bool(exposure <= 0.70)
        verdict['groups'][group] = dict(pooled_T_U=t_u, pooled_T_D=t_d, both=both, need=need, U=up, D=down, U_base=b_up, D_base=b_down,
                                        F1=f1, F2=f2, G1=g1, payoff=payoff, win_rate=float(len(wins)/(len(wins)+len(losses))) if wins or losses else np.nan,
                                        fat_pnl=fat_pnl, ordinary_pnl=ordinary_pnl, exposure=exposure, trades=len(wins)+len(losses),
                                        pass_group=bool(t_u and t_d and both >= need and f1 and f2 and g1))
        for row in part:
            decisions.append(dict(symbol=row['symbol'], group=group, role='decisive', T_U=row['T_U'], T_D=row['T_D'], up=row['up'], down=row['down']))
    for row in rows:
        if row['role'] != 'decisive':
            decisions.append(dict(symbol=row['symbol'], group=row['group'], role=row['role'], T_U=row['T_U'], T_D=row['T_D'], up=row['up'], down=row['down']))
    verdict['passed'] = all(v['pass_group'] for v in verdict['groups'].values())
    verdict['state_changed_bars'] = changed
    verdict['adopt'] = True
    verdict['against_positive_connect'] = {}
    for group in ('broad', 'sector'):
        members = [s for s, item in cache.items() if item['group'] == group and item['role'] == 'decisive']
        _up_old, down_old = pooled_parts([cache[s]['old_parts'] for s in members])
        verdict['against_positive_connect'][group] = dict(D=verdict['groups'][group]['D'], D_positive=down_old)
    accounts = pd.DataFrame(account_rows)
    verdict['accounts'] = {}
    base_accounts = accounts[(accounts.role == 'decisive') & (accounts.scenario == 'base')]
    for (group, state_name), part in base_accounts.groupby(['group', 'state']):
        verdict['accounts'][f'{group}:{state_name}'] = dict(median_return=float(part.total_return.median()), median_drawdown=float(part.max_drawdown.median()))
    for group in ('broad', 'sector'):
        down_new = verdict['against_positive_connect'][group]['D']
        down_old = verdict['against_positive_connect'][group]['D_positive']
        dd_new = verdict['accounts'][f'{group}:equal_weight']['median_drawdown']
        dd_old = verdict['accounts'][f'{group}:positive_connect']['median_drawdown']
        ok = down_new <= down_old + 0.01 and dd_new >= dd_old - 0.03
        verdict['against_positive_connect'][group].update(drawdown=dd_new, drawdown_positive=dd_old, ok=bool(ok))
        verdict['adopt'] = verdict['adopt'] and bool(ok)
    leg_frame = pd.DataFrame(legs)
    leg_report = {}
    if len(leg_frame):
        for name, part in leg_frame.groupby('state'):
            leg_report[name] = dict(legs=int(len(part)), median_account=float(part.account_return.median()), hit_80=int(part.hit_80.sum()),
                                    before_share=float(np.average(part.before_share, weights=np.log1p(part.price_return))),
                                    held_share=float(np.average(part.held_share, weights=np.log1p(part.price_return))))
    verdict['large_legs'] = leg_report
    etf = load_etf()
    etf_scores = equal_scores(etf.close, etf.amount)
    etf_state = pd.Series(positive_state(etf_scores.fast.to_numpy(), etf_scores.slow.to_numpy()), index=etf.index)
    etf_nav = simulate({'510300': etf}, {'510300': etf_state}, {'510300': etf.index[0]}, lot=LOT)
    verdict['etf'] = {}
    for label, begin, stop in WINDOWS:
        if label not in KEEP:
            continue
        got = window_stats(etf_nav, begin, stop)
        if got:
            verdict['etf'][label] = got
    baseline = json.loads(ETF_BASE.read_text())['positive_connect']['windows']['2013-2016']
    bull = verdict['etf'].get('2013-2016')
    verdict['etf_keeps_bull'] = bool(bull and bull['total_return'] >= baseline['total_return'] and bull['max_drawdown'] >= baseline['max_drawdown'])
    verdict['adopt'] = bool(verdict['adopt'] and verdict['etf_keeps_bull'])
    figures = []
    for symbol in ('USHI1A0001', 'USHI1B0300'):
        fig = OUT/f'{symbol}-equal-weight.png'
        draw(symbol, cache[symbol], fig, name='equal_weight')
        figures.append(str(fig.relative_to(ROOT)))
    pd.DataFrame(rows).to_csv(OUT/'trajectory.csv', index=False)
    accounts.to_csv(OUT/'accounts.csv', index=False)
    pd.DataFrame(books).to_csv(OUT/'books.csv', index=False)
    pd.DataFrame(decisions).to_csv(OUT/'decisions.csv', index=False)
    leg_frame.to_csv(OUT/'large-legs.csv', index=False)
    validation = dict(protocol_sha256=digest, evaluation_opened=False, not_a_pass=not verdict['passed'], tail_rows_after_cut=0, prefix_checks=len(prefix),
                      selected=verdict, figures=figures, max_loaded=max(str(item['frame'].index.max().date()) for item in cache.values()))
    (OUT/'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2)+'\n')
    lines = ['# 配对斜率不再乘成交额', '', '样本、远近权重和背景波动都与正接仓相同。快慢斜率都不乘成交额权重。状态机仍是正接仓。', '',
             f"建模期阶段 2 {'通过' if verdict['passed'] else '未通过'}。{'采用' if verdict['adopt'] else '不采用'}。", '']
    for group, row in verdict['groups'].items():
        lines.append(f"- {group}: 上行 {row['U']:.3f}（对照 {row['U_base']:.3f}），下行 {row['D']:.3f}（对照 {row['D_base']:.3f}），T_U/T_D = {row['pooled_T_U']}/{row['pooled_T_D']}，单指数两项都过 {row['both']}/{row['need']}")
        lines.append(f"  胜率 {row['win_rate']:.3f}，盈亏比 {row['payoff']:.3f}，肥尾盈亏 {row['fat_pnl']:.0f}，普通盈亏 {row['ordinary_pnl']:.0f}，持仓比例 {row['exposure']:.3f}，F1/F2/G1 = {row['F1']}/{row['F2']}/{row['G1']}")
    for key, row in verdict['accounts'].items():
        lines.append(f"- 账户 {key}: 中位收益 {row['median_return']:.3f}，中位回撤 {row['median_drawdown']:.3f}")
    for name, row in leg_report.items():
        lines.append(f"- 大段 {name}: {row['legs']} 段，账户中位 {row['median_account']:.3f}，达到 80% 的 {row['hit_80']} 段，进场前份额 {row['before_share']:.3f}，持仓份额 {row['held_share']:.3f}")
    for label, row in verdict['etf'].items():
        lines.append(f"- 沪深300ETF {label}: 收益 {row['total_return']:.3f}，高点 {row['peak_return']:.3f}，回撤 {row['max_drawdown']:.3f}")
    lines.append('')
    (OUT/'README.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(verdict, ensure_ascii=False, default=str))


if __name__ == '__main__':
    main()
