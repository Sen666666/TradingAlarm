"""Phase-2 market/sector state on the modeling window only.

The loader drops every row after 2017-12-31 before any label, state or account is
computed. 2018-2021 stays unopened. Index results here are development evidence.
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
from monthly_ah_engine import run
from pairwise_trend_strength import pairwise_frame
from geometric_strength import strength_exposure
from trend_target_labels import label_frame, oracle_state, trajectory, summarize, scale

ROOT = Path(__file__).resolve().parent
OUT = ROOT/'results'/'market-state-phase2'
BATCH = ROOT/'data'/'ths-index-history-20261018'
CUT = pd.Timestamp('2017-12-31')
FLOOR = pd.Timestamp('2004-01-01')
MODEL_FLOOR = pd.Timestamp('2005-01-01')
ENTRY = 5+5*math.tanh(1)
EXIT_SYM = 5-5*math.tanh(1)
GRID = [(a, b) for a in (1., 2.) for b in (2., 3.)]
PREFIX_CUTS = ['2009-06-30', '2013-06-28', '2016-06-30']


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def keep(prior, score, qty, pending):
    return dict(score)


def swing_state(y, sigma, a, b, gate=None):
    """Causal hysteresis. Flat tracks the trough; held tracks the peak. gate>=0 is an extra entry condition."""
    y = np.asarray(y, float)
    s = np.asarray(sigma, float)
    g = None if gate is None else np.asarray(gate, float)
    state = np.zeros(len(y))
    ready = np.flatnonzero(np.isfinite(s) & np.isfinite(y))
    if not len(ready):
        return state
    low = int(ready[0])
    held = False
    high = None
    for t in range(low+1, len(y)):
        if not (np.isfinite(y[t]) and np.isfinite(s[t])):
            state[t] = float(held)
            continue
        if not held:
            if y[t] < y[low]:
                low = t
            enter = np.isfinite(s[low]) and y[t]-y[low] >= a*s[low]
            if g is not None:
                enter = enter and np.isfinite(g[t]) and g[t] >= 0
            if enter:
                held = True
                high = t
        elif np.isfinite(s[high]) and y[high]-y[t] >= b*s[high]:
            held = False
            low = t
        elif y[t] > y[high]:
            high = t
        state[t] = float(held)
    return state


def turnover_gate(amount):
    """log(21-bar mean amount / 252-bar mean amount); nonpositive amount is missing."""
    amt = amount.where(amount > 0)
    fast = amt.rolling(21, min_periods=17).mean()
    slow = amt.rolling(252, min_periods=202).mean()
    return np.log(fast/slow)


def medium_state(close):
    change = np.log(close.astype(float)).diff(63)
    return change.gt(0).astype(float).fillna(0.).to_numpy()


def pairwise_state(close, amount, exit_threshold):
    strength = pairwise_frame(close, amount.where(amount > 0))['strength']
    return strength_exposure(strength, exit_threshold).to_numpy()


def load_symbol(symbol, launch):
    """Read one index and drop post-cut and pre-launch rows before anything else."""
    frame = pd.read_csv(BATCH/'canonical'/f'{symbol}.csv', usecols=['date', 'open', 'high', 'low', 'close', 'volume', 'amount'])
    frame['date'] = pd.to_datetime(frame['date'])
    if frame['date'].max() > CUT:
        frame = frame[frame['date'] <= CUT]
    if launch:
        frame = frame[frame['date'] >= pd.Timestamp(launch)]
    frame = frame[frame['date'] >= FLOOR]
    ok = (frame[['open', 'high', 'low', 'close']] > 0).all(axis=1) & np.isfinite(frame[['open', 'high', 'low', 'close', 'volume', 'amount']]).all(axis=1)
    frame = frame[ok].drop_duplicates('date').sort_values('date')
    if frame.empty or frame['date'].max() > CUT:
        raise ValueError(f'{symbol} failed the modeling cut')
    frame = frame.set_index('date')
    start_pos = 252
    modeling_start = frame.index[start_pos] if len(frame) > start_pos else None
    if modeling_start is not None:
        modeling_start = max(modeling_start, MODEL_FLOOR)
        if modeling_start > CUT:
            modeling_start = None
    return frame, modeling_start


def states_for(frame):
    y = np.log(frame.close.astype(float))
    sigma = scale(y).to_numpy()
    gate = turnover_gate(frame.amount).to_numpy()
    out = {}
    for a, b in GRID:
        out[f'M1_{a:g}_{b:g}'] = swing_state(y, sigma, a, b)
        out[f'M2_{a:g}_{b:g}'] = swing_state(y, sigma, a, b, gate)
    out['pairwise_volume'] = pairwise_state(frame.close, frame.amount, 5.)
    out['symmetric_pairwise_volume'] = pairwise_state(frame.close, frame.amount, EXIT_SYM)
    out['medium63'] = medium_state(frame.close)
    out['buy_and_hold'] = np.ones(len(frame))
    return out, y, sigma


def asset_of(frame):
    signal = frame[['open', 'high', 'low', 'close', 'volume']].astype(float).copy()
    return dict(raw=signal, signal=signal.copy(), currency='CNY', lot=1e-6, splits=[], dividends=[])


def cny_fx(index):
    return pd.Series(1., index=pd.date_range('2004-01-01', '2017-12-31'))


def account(frame, state, start, cost, delay):
    signal = pd.Series(state, index=frame.index)
    asset = asset_of(frame)
    metrics, path, orders, _ = run({'IDX': asset}, str(start.date()), '2017-12-31', policy='score_change', signals={'IDX': signal},
                                    cadence='daily', selection=keep, entry_fraction=1., cost=cost, delay=delay, initial_capital=1e6, fx_override=cny_fx(frame.index))
    return metrics, path, orders


def exposure_matched_log(frame, path):
    weight = float(path['w_IDX'].mean())
    ret = frame.close.astype(float).pct_change().reindex(path.index)
    growth = float(np.prod(1+weight*ret.fillna(0.)))
    return math.log(growth), weight


def score_window(frame, state, legs, start):
    held = pd.Series(state, index=frame.index)
    daily, events, entries = trajectory(frame, legs, held, start, CUT)
    return summarize(daily, events, entries), daily, events


def passes_trajectory(row, base, slow):
    u, d, r = row['up_participation'], row['down_participation'], row['range_time']
    t1 = np.isfinite(u) and u >= base['up_participation']+0.10
    t2 = np.isfinite(d) and np.isfinite(base['down_participation']) and d <= base['down_participation']+0.05
    t3 = np.isfinite(r) and np.isfinite(slow['range_time']) and r <= slow['range_time']-0.15
    return bool(t1), bool(t2), bool(t3)


def select(rows):
    """rows: list of dicts with mechanism, a, b, symbol, role, T1, T2, T3, up, down."""
    chosen = {}
    for mechanism in ('M1', 'M2'):
        best = None
        for a, b in GRID:
            part = [r for r in rows if r['mechanism'] == mechanism and r['a'] == a and r['b'] == b and r['role'] == 'decisive']
            n = sum(r['T1'] and r['T2'] and r['T3'] for r in part)
            up_den = sum(r['up_den'] for r in part)
            down_den = sum(r['down_den'] for r in part)
            gap = (sum(r['up_num'] for r in part)/up_den if up_den else -np.inf)-(sum(r['down_num'] for r in part)/down_den if down_den else np.inf)
            key = (n, gap, -a, -b)
            if best is None or key > best[0]:
                best = (key, a, b, n, gap)
        chosen[mechanism] = dict(a=best[1], b=best[2], decisive_T123=best[3], pooled_gap=best[4])
    return chosen


def prefix_ok(frame, full_states):
    y = np.log(frame.close.astype(float))
    out = []
    for cut in PREFIX_CUTS:
        if (frame.index < cut).sum() < 100:
            continue
        sub = frame[frame.index <= cut]
        sub_states, _, _ = states_for(sub)
        for name, full in full_states.items():
            if name == 'buy_and_hold':
                continue
            got = sub_states[name]
            ref = full[frame.index <= cut]
            if len(got) != len(ref) or not np.array_equal(got, ref):
                raise AssertionError(f'prefix mismatch {cut} {name}')
        out.append(dict(cut=cut, bars=len(sub), names=len(sub_states)-1, equal=True))
    return out


def large_decline(frame, legs, state):
    y = frame.y.to_numpy()
    held = np.asarray(state, float)
    rows = []
    for leg in legs.itertuples():
        if leg.move > math.log(0.7):
            continue
        r = np.diff(y[leg.start:leg.end+1])
        h = held[leg.start:leg.end]
        rows.append(dict(start=str(leg.start_date.date()), end=str(leg.end_date.date()), kind=leg.kind, move=leg.move,
                         held_fraction=float(np.sum(h*r)/np.sum(r)) if np.sum(r) else None, provisional=bool(leg.provisional)))
    return rows


def main():
    protocol_path = OUT/'protocol.json'
    freeze = json.loads((OUT/'protocol-freeze.json').read_text())
    digest = sha(protocol_path)
    if digest != freeze['sha256']:
        raise SystemExit(f'protocol changed after freeze: {digest}')
    protocol = json.loads(protocol_path.read_text())
    coverage = {r['symbol']: r for r in json.loads((BATCH/'coverage.json').read_text())['per_symbol']}
    groups = {}
    for symbol, name in protocol['index_sets']['decisive_broad'].items():
        groups[symbol] = ('decisive', 'broad', name)
    for symbol, name in protocol['index_sets']['decisive_sector'].items():
        groups[symbol] = ('decisive', 'sector', name)
    for symbol, name in protocol['index_sets']['separate_report_only'].items():
        if symbol == 'reason':
            continue
        groups[symbol] = ('separate', 'csi_l1', name)
    loaded = {}
    validation_dates = []
    for symbol, (role, group, name) in groups.items():
        launch = coverage[symbol]['publication'].get('launch_date')
        frame, modeling_start = load_symbol(symbol, launch)
        if frame.index.max() > CUT:
            raise SystemExit('cut failed')
        loaded[symbol] = dict(frame=frame, start=modeling_start, role=role, group=group, name=name, launch=launch)
        validation_dates.append(dict(symbol=symbol, role=role, first=str(frame.index.min().date()), last=str(frame.index.max().date()),
                                      modeling_start=None if modeling_start is None else str(modeling_start.date()), rows=len(frame), launch=launch))
    # States, labels and trajectory before any account, so selection cannot see account results.
    trajectory_rows = []
    cache = {}
    prefix = []
    decline_rows = []
    bear_rows = []
    for symbol, item in loaded.items():
        if item['start'] is None:
            continue
        frame = item['frame']
        series, y, sigma = states_for(frame)
        labels, legs = label_frame(frame.close, 2., 2.)
        item.update(states=series, labels=labels, legs=legs, y=y)
        prefix.extend(dict(symbol=symbol, **row) for row in prefix_ok(frame, series))
        base, _, _ = score_window(labels, series['pairwise_volume'], legs, item['start'])
        slow, _, _ = score_window(labels, series['medium63'], legs, item['start'])
        item['base'] = base
        item['slow'] = slow
        for mechanism in ('M1', 'M2'):
            for a, b in GRID:
                key = f'{mechanism}_{a:g}_{b:g}'
                summary, daily, events = score_window(labels, series[key], legs, item['start'])
                t1, t2, t3 = passes_trajectory(summary, base, slow)
                up = daily[daily.label.eq('up')]
                down = daily[daily.label.eq('down')]
                trajectory_rows.append(dict(symbol=symbol, role=item['role'], group=item['group'], mechanism=mechanism, a=a, b=b,
                                            T1=t1, T2=t2, T3=t3, up_participation=summary['up_participation'], down_participation=summary['down_participation'],
                                            range_time=summary['range_time'], up_num=float(up.hr.sum()), down_num=float(down.hr.sum()),
                                            up_den=float(up.r.sum()), down_den=float(down.r.sum())))
        for leg in large_decline(labels, legs, series['M1_2_2']):
            decline_rows.append(dict(symbol=symbol, state='M1_2_2', **leg))
        span = legs[(legs.end_date >= '2007-10-01') & (legs.start_date <= '2008-12-31')]
        for leg in span.itertuples():
            bear_rows.append(dict(symbol=symbol, setting='A', start=str(leg.start_date.date()), end=str(leg.end_date.date()), kind=leg.kind, move=float(leg.move), provisional=bool(leg.provisional)))
        cache[symbol] = item
    # Setting B (k=1, trend_ratio=2, the frozen phase-1 second setting) is report-only.
    for symbol, item in cache.items():
        labels_b, legs_b = label_frame(item['frame'].close, 1., 2.)
        # phase-1 setting B is the second registered setting. Read it from the phase-1 protocol rather than guessing.
        span = legs_b[(legs_b.end_date >= '2007-10-01') & (legs_b.start_date <= '2008-12-31')]
        for leg in span.itertuples():
            bear_rows.append(dict(symbol=symbol, setting='B_k1_ratio2', start=str(leg.start_date.date()), end=str(leg.end_date.date()), kind=leg.kind, move=float(leg.move), provisional=bool(leg.provisional)))
    chosen = select(trajectory_rows)
    decisions = []
    account_rows = []
    for mechanism, pick in chosen.items():
        key = f"{mechanism}_{pick['a']:g}_{pick['b']:g}"
        for symbol, item in cache.items():
            frame, start, state = item['frame'], item['start'], item['states'][key]
            for scenario, cost, delay in (('base', 15, 0), ('cost2', 30, 0), ('delay1', 15, 1)):
                metrics, path, orders = account(frame, state, start, cost, delay)
                row = dict(symbol=symbol, role=item['role'], group=item['group'], state=key, scenario=scenario,
                           total_return=metrics['total_return'], log_return=math.log1p(metrics['total_return']),
                           max_drawdown=metrics['max_drawdown'], orders=metrics['orders'], last=str(path.index.max().date()))
                if scenario == 'cost2':
                    matched, weight = exposure_matched_log(frame, path)
                    row.update(matched_log=matched, mean_weight=weight, A1=row['log_return'] >= matched)
                    item['cost2_path'] = path
                    item['A1'] = row['A1']
                if scenario == 'base':
                    item['base_path'] = path
                    item['base_dd'] = metrics['max_drawdown']
                if path.index.max() > CUT:
                    raise SystemExit('account passed the cut')
                account_rows.append(row)
            if 'bh' not in item:
                bh, bh_path, _ = account(frame, item['states']['buy_and_hold'], start, 15, 0)
                item['bh'] = bh
                account_rows.append(dict(symbol=symbol, role=item['role'], group=item['group'], state='buy_and_hold', scenario='base',
                                         total_return=bh['total_return'], log_return=math.log1p(bh['total_return']), max_drawdown=bh['max_drawdown'],
                                         orders=bh['orders'], last=str(bh_path.index.max().date())))
                asset = asset_of(frame)
                signal = pd.Series(1., index=frame.index)
                half, half_path, _, _ = run({'IDX': asset}, str(start.date()), '2017-12-31', policy='score_change', signals={'IDX': signal},
                                             cadence='daily', selection=keep, entry_fraction=.5, cost=15, delay=0, fx_override=cny_fx(frame.index))
                account_rows.append(dict(symbol=symbol, role=item['role'], group=item['group'], state='fixed_50', scenario='base',
                                         total_return=half['total_return'], log_return=math.log1p(half['total_return']), max_drawdown=half['max_drawdown'],
                                         orders=half['orders'], last=str(half_path.index.max().date())))
            item['A2'] = item['base_dd'] > item['bh']['max_drawdown']
            item.setdefault('paths', {})[key] = item['base_path']
            trow = next(r for r in trajectory_rows if r['symbol'] == symbol and r['mechanism'] == mechanism and r['a'] == pick['a'] and r['b'] == pick['b'])
            five = trow['T1'] and trow['T2'] and trow['T3'] and item['A1'] and item['A2']
            decisions.append(dict(symbol=symbol, group=item['group'], role=item['role'], state=key, T1=trow['T1'], T2=trow['T2'], T3=trow['T3'], A1=item['A1'], A2=item['A2'], five=five))
    # Sector pool for the selected states, report only.
    sector_symbols = [s for s, item in cache.items() if item['group'] == 'sector']
    pool_start = max(cache[s]['start'] for s in sector_symbols)
    for mechanism, pick in chosen.items():
        key = f"{mechanism}_{pick['a']:g}_{pick['b']:g}"
        assets = {s: asset_of(cache[s]['frame']) for s in sector_symbols}
        signals = {s: pd.Series(cache[s]['states'][key], index=cache[s]['frame'].index) for s in sector_symbols}
        metrics, path, _, _ = run(assets, str(pool_start.date()), '2017-12-31', policy='score_change', signals=signals, cadence='daily', selection=keep, entry_fraction=.1, cost=15, fx_override=cny_fx(None))
        hold = {s: pd.Series(1., index=cache[s]['frame'].index) for s in sector_symbols}
        bh, _, _, _ = run(assets, str(pool_start.date()), '2017-12-31', policy='score_change', signals=hold, cadence='daily', selection=keep, entry_fraction=.1, cost=15, fx_override=cny_fx(None))
        account_rows.append(dict(symbol='SSE10', role='report', group='sector', state=key, scenario='pool_base', total_return=metrics['total_return'],
                                 log_return=math.log1p(metrics['total_return']), max_drawdown=metrics['max_drawdown'], orders=metrics['orders'], last=str(path.index.max().date()),
                                 buy_and_hold_return=bh['total_return'], buy_and_hold_drawdown=bh['max_drawdown']))
    verdict = {}
    for mechanism, pick in chosen.items():
        key = f"{mechanism}_{pick['a']:g}_{pick['b']:g}"
        passed_groups = {}
        for group, need in (('broad', 6), ('sector', 7)):
            members = [s for s, item in cache.items() if item['group'] == group and item['role'] == 'decisive']
            cand = pooled_summary(cache, members, key)
            base = pooled_summary(cache, members, 'pairwise_volume')
            slow = pooled_summary(cache, members, 'medium63')
            t1, t2, t3 = passes_trajectory(cand, base, slow)
            five = sum(r['five'] for r in decisions if r['state'] == key and r['group'] == group)
            passed_groups[group] = dict(pooled_T1=t1, pooled_T2=t2, pooled_T3=t3, five=five, need=need, pass_group=bool(t1 and t2 and t3 and five >= need),
                                        U=cand['up_participation'], D=cand['down_participation'], R=cand['range_time'],
                                        U_base=base['up_participation'], D_base=base['down_participation'], R_slow=slow['range_time'])
        verdict[mechanism] = dict(state=key, a=pick['a'], b=pick['b'], groups=passed_groups,
                                  passed=all(v['pass_group'] for v in passed_groups.values()))
    figures = []
    wanted = ['USHI1A0001', 'USHI1B0300', 'USHI1B0905', 'USZI399006', 'USHI1B0039']
    for symbol in wanted:
        item = cache[symbol]
        m1 = f"M1_{chosen['M1']['a']:g}_{chosen['M1']['b']:g}"
        m2 = f"M2_{chosen['M2']['a']:g}_{chosen['M2']['b']:g}"
        fig_path = OUT/f'{symbol}-modeling.png'
        draw(symbol, item, m1, m2, fig_path)
        figures.append(str(fig_path.relative_to(ROOT)))
    pd.DataFrame(trajectory_rows).to_csv(OUT/'trajectory.csv', index=False)
    pd.DataFrame(account_rows).to_csv(OUT/'accounts.csv', index=False)
    pd.DataFrame(decisions).to_csv(OUT/'decisions.csv', index=False)
    pd.DataFrame(decline_rows).to_csv(OUT/'large-declines.csv', index=False)
    pd.DataFrame(bear_rows).to_csv(OUT/'bear-2008-labels.csv', index=False)
    validation = dict(protocol_sha256=digest, tail_rows_after_cut=0, max_loaded='2017-12-31', dates=validation_dates,
                      prefix_checks=len(prefix), prefix_failures=0, selected=verdict, evaluation_opened=False,
                      figures=figures, note='Modeling window only. 2018-2021 was not computed.')
    (OUT/'validation.json').write_text(json.dumps(validation, ensure_ascii=False, indent=2, default=str)+'\n')
    (OUT/'prefix-checks.json').write_text(json.dumps(prefix)+'\n')
    write_readme(verdict, validation_dates)
    print(json.dumps({k: dict(state=v['state'], passed=v['passed'], groups=v['groups']) for k, v in verdict.items()}, ensure_ascii=False, default=str))


def pooled_summary(cache, members, state_name):
    daily = []
    events = []
    entries = []
    for symbol in members:
        item = cache[symbol]
        d, e, n = trajectory(item['labels'], item['legs'], pd.Series(item['states'][state_name], index=item['frame'].index), item['start'], CUT)
        daily.append(d)
        events.append(e)
        entries.append(n)
    return summarize(pd.concat(daily, ignore_index=True), pd.concat(events, ignore_index=True) if events else pd.DataFrame(), pd.concat(entries, ignore_index=True) if entries else pd.DataFrame())


def draw(symbol, item, m1, m2, path):
    frame, labels, legs = item['frame'], item['labels'], item['legs']
    fig, axes = plt.subplots(4, 1, figsize=(12, 10), sharex=True)
    axes[0].plot(frame.index, labels.y, color='black', lw=.7)
    for leg in legs.itertuples():
        axes[0].axvspan(frame.index[leg.start], frame.index[leg.end], color={'up': '#b7e1cd', 'down': '#f4c7c3', 'range': '#fff2cc'}[leg.kind], alpha=.8, lw=0)
    axes[0].axvspan(frame.index[0], item['start'], color='#bbbbbb', alpha=.35, lw=0)
    axes[0].set_ylabel('log price')
    axes[1].plot(frame.index, turnover_gate(frame.amount), lw=.6)
    axes[1].axhline(0, color='gray', lw=.4)
    axes[1].set_ylabel('amount ratio')
    for name, color in ((m1, 'tab:blue'), (m2, 'tab:orange'), ('pairwise_volume', 'tab:green'), ('medium63', 'tab:red')):
        axes[2].plot(frame.index, item['states'][name], lw=.6, label=name, alpha=.8)
    axes[2].legend(fontsize=7, ncol=2)
    axes[2].set_ylim(-.05, 1.05)
    nav = item.get('paths', {}).get(m1)
    if nav is not None:
        axes[3].plot(nav.index, nav.nav, label=m1)
    axes[3].legend(fontsize=7)
    axes[3].set_ylabel('NAV')
    fig.suptitle(f'{symbol} through 2017-12-31; gray is warmup and is not scored')
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def write_readme(verdict, dates):
    lines = ['# 阶段 2 建模期结果', '', '只使用 2017-12-31 及之前的数据。2018–2021 评价期没有计算。', '']
    for mechanism, row in verdict.items():
        lines.append(f"- {row['state']}: 建模期{'通过' if row['passed'] else '未通过'}")
        for group, g in row['groups'].items():
            lines.append(f"  - {group}: 合并 T1/T2/T3 = {g['pooled_T1']}/{g['pooled_T2']}/{g['pooled_T3']}，五项都过的指数 {g['five']}/{g['need']} 所需")
    lines.append('')
    lines.append('通过线、参数网格和指数集合以冻结的 protocol.json 为准，本次运行没有改它们。')
    (OUT/'README.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    main()
