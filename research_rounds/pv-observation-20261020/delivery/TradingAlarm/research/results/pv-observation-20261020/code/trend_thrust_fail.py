"""A hold that never closes above its signal ends when the fast score is back at 5.

The opener stays the quieter opposing-day scale. A later higher close leaves this exit unused.
"""
import hashlib
import json
import math
from pathlib import Path
import numpy as np
import pandas as pd
from pairwise_trend_strength import pairwise_frame
from trend_segment_revision import fixed_label
from trend_background_hold import ENTRY, VIOLENT, one_score, passes, round_trips, book_of, draw, pooled_parts
from trend_equal_weight import equal_scores
from trend_positive_connect import NEUTRAL
from trend_fresh_window import fresh_state
from trend_shock_scale import shock_entry
from trend_quiet_scale import quiet_entry
from trend_slow_pause import pause_state
from trend_leg_gap import LARGE, split_leg
from trend_leg_capture import leg_account_return
from trend_cash_book import WINDOWS, simulate, window_stats
from trend_etf_proxy import load_etf, LOT, shape
from trend_quiet_book import load_one, NAMES
from market_state_phase2 import CUT, load_symbol, pairwise_state, account

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'trend-thrust-fail'
ETF_BASE = ROOT/'results'/'trend-quiet-scale'/'validation.json'
PHASE2 = ROOT/'results'/'market-state-phase2'
BATCH = ROOT/'data'/'ths-index-history-20261018'
PREFIX_CUTS = ('2009-06-30', '2013-06-28', '2016-06-30')
KEEP = ('2013-2016', '2018-2021', '2022-2026')


def thrust_state(entry, fast, slow, close):
    """Slow-pause state, plus an exit when price has not traded above the signal close."""
    entry = np.asarray(entry, float)
    fast = np.asarray(fast, float)
    slow = np.asarray(slow, float)
    close = np.asarray(close, float)
    held = False
    confirmed = False
    seen = False
    armed = False
    signal = np.nan
    lifted = False
    out = np.zeros(len(fast))
    for i, (opener, level, slope, px) in enumerate(zip(entry, fast, slow, close)):
        violent = np.isfinite(level) and level <= VIOLENT
        strong_open = np.isfinite(opener) and opener >= ENTRY
        strong_fast = np.isfinite(level) and level >= ENTRY
        if held and strong_fast:
            seen = True
        if held and seen and np.isfinite(slope) and slope > 0:
            confirmed = True
        if held and np.isfinite(px) and np.isfinite(signal) and px > signal:
            lifted = True
        dead = confirmed and np.isfinite(slope) and slope <= 0
        background = np.isfinite(slope) and slope > 0
        nonpositive = (not confirmed) and np.isfinite(opener) and opener <= NEUTRAL and not background
        failed = held and (not lifted) and np.isfinite(level) and level <= NEUTRAL
        if held and (violent or dead or nonpositive or failed):
            held = False
            confirmed = False
            seen = False
            signal = np.nan
            lifted = False
        elif (not held) and strong_open and not armed and not violent:
            held = True
            seen = bool(strong_fast)
            confirmed = bool(seen and np.isfinite(slope) and slope > 0)
            signal = px
            lifted = False
        if violent:
            armed = False
        elif np.isfinite(opener):
            armed = strong_open
        out[i] = float(held)
    return out


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def prefix_check(frame, full):
    cuts = []
    for cut in PREFIX_CUTS:
        if (frame.index <= cut).sum() < 100:
            continue
        sub = frame[frame.index <= cut]
        plain = equal_scores(sub.close, sub.amount)
        opener = quiet_entry(sub.close, sub.amount, plain)
        got = thrust_state(opener.to_numpy(), plain.fast.to_numpy(), plain.slow.to_numpy(), sub.close.to_numpy())
        mask = np.asarray(frame.index <= cut)
        if not np.array_equal(got, full[mask]):
            raise AssertionError(f'prefix mismatch {cut}')
        cuts.append(cut)
    return cuts


def main():
    digest = sha(OUT/'protocol.json')
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    if digest != freeze['sha256'] or freeze.get('results_viewed') is not False:
        raise SystemExit('thrust-fail protocol changed after freeze')
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
        plain = equal_scores(frame.close, frame.amount)
        shock_open = shock_entry(frame.close, frame.amount, plain)
        opener = quiet_entry(frame.close, frame.amount, plain)
        fast = plain.fast.to_numpy()
        slow = plain.slow.to_numpy()
        opened = opener.to_numpy()
        state = thrust_state(opened, fast, slow, frame.close.to_numpy())
        pause_held = pause_state(opened, fast, slow)
        shock_held = fresh_state(shock_open.to_numpy(), fast, slow)
        if role == 'decisive':
            changed += int(np.sum(state != pause_held))
        pairwise = pairwise_state(frame.close, frame.amount, NEUTRAL)
        pairwise_score = pairwise_frame(frame.close, frame.amount.where(frame.amount > 0))['strength']
        prefix.extend(dict(symbol=symbol, cut=cut) for cut in prefix_check(frame, state))
        base, _ = one_score(labels, leg_table, pairwise, start)
        summary, daily = one_score(labels, leg_table, state, start)
        _pause_summary, pause_daily = one_score(labels, leg_table, pause_held, start)
        t_u, t_d = passes(summary, base)
        up, down = daily[daily.label.eq('up')], daily[daily.label.eq('down')]
        rows.append(dict(symbol=symbol, role=role, group=group, T_U=t_u, T_D=t_d, up=summary['up_participation'], down=summary['down_participation'],
                         range_time=summary['range_time'], up_base=base['up_participation'], down_base=base['down_participation'],
                         up_num=float(up.hr.sum()), up_den=float(up.r.sum()), down_num=float(down.hr.sum()), down_den=float(down.r.sum())))
        exposure = float(state[frame.index >= start].mean())
        pause_up, pause_down = pause_daily[pause_daily.label.eq('up')], pause_daily[pause_daily.label.eq('down')]
        item = dict(frame=frame, start=start, role=role, group=group, labels=(labels, leg_table), scores=plain, state=state,
                    old_parts=dict(up_num=float(pause_up.hr.sum()), up_den=float(pause_up.r.sum()),
                                   down_num=float(pause_down.hr.sum()), down_den=float(pause_down.r.sum())),
                    pairwise=pairwise, pairwise_score=pairwise_score, exposure=exposure, paths={})
        cache[symbol] = item
        y = labels.y.to_numpy()
        for name, held, scenarios in (
            ('thrust_fail', state, (('base', 15, 0), ('cost2', 30, 0), ('delay1', 15, 1))),
            ('quiet_scale', pause_held, (('base', 15, 0),)),
            ('shock_scale', shock_held, (('base', 15, 0),)),
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
                    if name == 'thrust_fail':
                        trips = round_trips(orders, frame.close.iloc[-1])
                        row = book_of(trips, exposure)
                        row.update(symbol=symbol, role=role, group=group, state=name)
                        books.append(row)
                        item['book'] = row
                        item['trips'] = trips
                    if role == 'decisive' and name in ('thrust_fail', 'quiet_scale', 'shock_scale'):
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
    verdict['adopt'] = changed > 0
    verdict['against_quiet_scale'] = {}
    for group in ('broad', 'sector'):
        members = [s for s, item in cache.items() if item['group'] == group and item['role'] == 'decisive']
        _up_old, down_old = pooled_parts([cache[s]['old_parts'] for s in members])
        verdict['against_quiet_scale'][group] = dict(D=verdict['groups'][group]['D'], D_quiet=down_old)
    accounts = pd.DataFrame(account_rows)
    verdict['accounts'] = {}
    base_accounts = accounts[(accounts.role == 'decisive') & (accounts.scenario == 'base')]
    for (group, state_name), part in base_accounts.groupby(['group', 'state']):
        verdict['accounts'][f'{group}:{state_name}'] = dict(median_return=float(part.total_return.median()), median_drawdown=float(part.max_drawdown.median()))
    higher = False
    for group in ('broad', 'sector'):
        ret_new = verdict['accounts'][f'{group}:thrust_fail']['median_return']
        ret_old = verdict['accounts'][f'{group}:quiet_scale']['median_return']
        dd_new = verdict['accounts'][f'{group}:thrust_fail']['median_drawdown']
        dd_old = verdict['accounts'][f'{group}:quiet_scale']['median_drawdown']
        ok = ret_new >= ret_old and dd_new >= dd_old - 0.03
        higher = higher or ret_new > ret_old
        verdict['against_quiet_scale'][group].update(median_return=ret_new, median_return_quiet=ret_old, drawdown=dd_new, drawdown_quiet=dd_old, ok=bool(ok), higher=bool(ret_new > ret_old))
        verdict['adopt'] = verdict['adopt'] and bool(ok)
    verdict['adopt'] = bool(verdict['adopt'] and higher)
    leg_frame = pd.DataFrame(legs)
    leg_report = {}
    if len(leg_frame):
        for name, part in leg_frame.groupby('state'):
            leg_report[name] = dict(legs=int(len(part)), median_account=float(part.account_return.median()), hit_80=int(part.hit_80.sum()),
                                    before_share=float(np.average(part.before_share, weights=np.log1p(part.price_return))),
                                    held_share=float(np.average(part.held_share, weights=np.log1p(part.price_return))))
    verdict['large_legs'] = leg_report
    etf = load_etf()
    etf_plain = equal_scores(etf.close, etf.amount)
    etf_open = quiet_entry(etf.close, etf.amount, etf_plain)
    etf_state = pd.Series(thrust_state(etf_open.to_numpy(), etf_plain.fast.to_numpy(), etf_plain.slow.to_numpy(), etf.close.to_numpy()), index=etf.index)
    etf_nav = simulate({'510300': etf}, {'510300': etf_state}, {'510300': etf.index[0]}, lot=LOT)
    verdict['etf'] = {}
    for label, begin, stop in WINDOWS:
        if label not in KEEP:
            continue
        got = window_stats(etf_nav, begin, stop)
        if got:
            verdict['etf'][label] = got
    baseline = json.loads(ETF_BASE.read_text())['selected']['etf']['2013-2016']
    bull = verdict['etf'].get('2013-2016')
    verdict['etf_keeps_bull'] = bool(bull and bull['total_return'] >= baseline['total_return'] and bull['max_drawdown'] >= baseline['max_drawdown'] - 0.001)
    verdict['adopt'] = bool(verdict['adopt'] and verdict['etf_keeps_bull'])
    frames, states, starts = {}, {}, {}
    book_ledger = []
    for code, _label, first in NAMES:
        frame = load_one(code, first)
        plain = equal_scores(frame.close, frame.amount)
        opener = quiet_entry(frame.close, frame.amount, plain)
        states[code] = pd.Series(thrust_state(opener.to_numpy(), plain.fast.to_numpy(), plain.slow.to_numpy(), frame.close.to_numpy()), index=frame.index)
        frames[code] = frame
        starts[code] = frame.index[0]
    book_nav = simulate(frames, states, starts, book_ledger, lot=LOT)
    verdict['etf_book'] = dict(windows={}, trades=shape(book_ledger), not_an_adopt_gate=True, adjustment='Q, semantics unverified')
    for label, begin, stop in WINDOWS:
        if label not in KEEP:
            continue
        got = window_stats(book_nav, begin, stop)
        if got:
            verdict['etf_book']['windows'][label] = got
    figures = []
    for symbol in ('USHI1A0001', 'USHI1B0300'):
        fig = OUT/f'{symbol}-thrust-fail.png'
        draw(symbol, cache[symbol], fig, name='thrust_fail')
        figures.append(str(fig.relative_to(ROOT)))
    pd.DataFrame(rows).to_csv(OUT/'trajectory.csv', index=False)
    accounts.to_csv(OUT/'accounts.csv', index=False)
    pd.DataFrame(books).to_csv(OUT/'books.csv', index=False)
    pd.DataFrame(decisions).to_csv(OUT/'decisions.csv', index=False)
    leg_frame.to_csv(OUT/'large-legs.csv', index=False)
    validation = dict(protocol_sha256=digest, evaluation_opened=False, not_a_pass=not verdict['passed'], tail_rows_after_cut=0, prefix_checks=len(prefix),
                      selected=verdict, figures=figures, max_loaded=max(str(item['frame'].index.max().date()) for item in cache.values()))
    (OUT/'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2)+'\n')
    lines = ['# 收盘从未高于信号收盘时，快分数回到 5 就结束', '',
             '开仓分仍是更安静的反向日尺度。已经出现过更高收盘的持仓不使用这条。慢斜率为正并且快分数到过开仓线，仍然不能单独挡住这条：价格没有走出信号收盘，快分数小于等于 5，当根结束。', '',
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
    book = verdict['etf_book']
    trades = book['trades'] or {}
    lines.append(f"- 七只 ETF 同一现金账户：交易 {trades.get('n')}，胜率 {trades.get('win_rate')}，盈亏比 {trades.get('payoff')}，肥尾盈亏 {trades.get('fat_pnl')}，普通盈亏 {trades.get('ordinary_pnl')}。这一栏不参与采用。")
    for label, row in book['windows'].items():
        lines.append(f"- 七只 ETF {label}: 收益 {row['total_return']:.3f}，高点 {row['peak_return']:.3f}，回撤 {row['max_drawdown']:.3f}")
    lines.append('')
    (OUT/'README.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps(dict(adopt=verdict['adopt'], passed=verdict['passed'], etf_keeps_bull=verdict['etf_keeps_bull'],
                          against=verdict['against_quiet_scale'], etf=verdict['etf'], book=verdict['etf_book']), ensure_ascii=False))


if __name__ == '__main__':
    main()
