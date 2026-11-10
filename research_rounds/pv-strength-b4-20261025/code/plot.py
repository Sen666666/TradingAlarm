"""Read-only B4 figures. No model or account execution, no global temperature."""
import os
import sys

os.environ.setdefault('MPLCONFIGDIR', '/private/tmp/pvs-b4-mpl')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter
import numpy as np
import pandas as pd

from common import ROOT, B3, NAMES, read, write, sha, now

plt.rcParams.update({'font.family': 'Arial Unicode MS', 'axes.unicode_minus': False,
                     'font.size': 10})
UP, DOWN, INK = '#b86233', '#3579a1', '#253f4b'
OLD_LABELS = ['freeze', 'cold', 'neutral', 'warm', 'hot']


def col(f, name):
    return f[name] if name in f else pd.Series(np.nan, index=f.index, name=name)


def flags(f, name):
    return col(f, name).fillna(0).ne(0)


def draw(f, title, path):
    """Draw already computed rows. All public B4 indicators retain unknowns."""
    if f.empty:
        raise ValueError('Cannot draw an empty window')
    fig, axs = plt.subplots(7, 1, figsize=(15.5, 16), sharex=True,
                            gridspec_kw={'height_ratios': [3.2, .8, 1.7, 1.25, 1.35, 1.1, .8]})
    ax = axs[0]
    ax.plot(f.index, f.close, color=INK, lw=1.15, label='研究收盘（对数轴）')
    if 'e0_target' in f:
        active = f.e0_target.eq(1)
        ax.fill_between(f.index, 0, 1, where=active,
                        transform=ax.get_xaxis_transform(), color='#d6a770', alpha=.16,
                        label='E0结构有效（非持仓）')
        ax.plot(f.index, col(f, 'e0_floor').where(active), color='#a58159', lw=.7,
                label='原E0保护点')
    for h, marker, size in [(21, 'o', 24), (63, 'D', 37)]:
        is_new = flags(f, f'confirmed_{h}')
        direction = col(f, f'confirmed_direction_{h}')
        for d, color, label in [(1, UP, '向上'), (-1, DOWN, '向下')]:
            mask = is_new & direction.eq(d)
            ax.scatter(f.index[mask], f.close[mask], marker=marker, s=size,
                       edgecolors=color, facecolors='none', linewidths=1.1, zorder=5,
                       label=f'S{h}新{label}确认')
    ax.set_yscale('log')
    shown_prices = pd.concat([f.close, col(f, 'e0_floor').where(col(f, 'e0_target').eq(1))])
    shown_prices = shown_prices[np.isfinite(shown_prices) & shown_prices.gt(0)]
    lo, hi = float(shown_prices.min()), float(shown_prices.max())
    if lo == hi:
        lo, hi = lo / 1.01, hi * 1.01
    ax.set_yticks(np.geomspace(lo, hi, 5))
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: f'{x:,.4g}'))
    ax.minorticks_off()
    ax.set_title(title, loc='left', fontsize=13, pad=12)
    ax.set_ylabel('价格')
    ax.legend(loc='upper left', ncol=3, fontsize=8)

    daily = col(f, 'r')
    axs[1].bar(f.index, f.volume / 1e6, width=1,
               color=np.where(daily.ge(0), '#bd8e6e', '#80a2b5'), alpha=.8)
    axs[1].set_ylabel('量 / 百万')

    ax = axs[2]
    ax.plot(f.index, col(f, 'mu5_bp'), color=UP, lw=1.1, label='μ5 × 10000')
    ax.plot(f.index, col(f, 'mu21_bp'), color=DOWN, lw=1.15, label='μ21 × 10000')
    ax.axhline(0, color='#687d85', lw=.7)
    ax.set_ylabel('平滑净推进\nlog基点 / 有效观察')
    ax.legend(loc='upper left', ncol=3, fontsize=8)
    ax.text(.995, .04, '当日log收益见交互勾选项与逐日CSV；此面板只比较μ',
            transform=ax.transAxes, ha='right', fontsize=8, color='#62747b')

    ax = axs[3]
    # Small visual offsets separate the two discrete structures without changing labels.
    for h, offset, color, marker in [(21, .06, UP, 'o'), (63, -.06, DOWN, 'D')]:
        series = col(f, f'S{h}')
        ax.step(f.index, series + offset, where='post', color=color, lw=1.05,
                label=f'S{h} 最近事件确认方向')
        mask = flags(f, f'confirmed_{h}')
        ax.scatter(f.index[mask], series[mask] + offset, s=25, marker=marker,
                   color=color, edgecolors='white', linewidths=.35, zorder=4)
    ax.set_yticks([-1, 0, 1], ['下', '未确认', '上'])
    ax.set_ylim(-1.4, 1.4)
    ax.set_ylabel('事件结构\n可能陈旧，非当前速度')
    ax.legend(loc='upper left', ncol=2, fontsize=8)
    ax.text(.995, .04, '点 = 当日新前沿完成确认；线 = 上次确认延续',
            transform=ax.transAxes, ha='right', fontsize=8, color='#62747b')

    ax = axs[4]
    q, qe = col(f, 'q'), col(f, 'qeff')
    ax.bar(f.index, q, width=1, color=np.where(q.ge(0), '#c6a789', '#9ab7c8'),
           alpha=.65, label='q = 日变化 / 滞后典型尺度')
    ax.plot(f.index, qe, color='#725b83', lw=.75, label='q_eff 参与调整')
    for v in [-2, 2]:
        ax.axhline(v, color='#9b9891', ls='--', lw=.7)
    for field, color, marker, label in [('acute_down', DOWN, 'v', '当日急跌'),
                                        ('acute_up', UP, '^', '当日急涨')]:
        mask = flags(f, field)
        ax.scatter(f.index[mask], qe[mask], s=27, color=color, marker=marker,
                   label=label, zorder=3)
    ax.set_ylabel('当日急性冲击\n事件消失不等于收复')
    ax.legend(loc='upper left', ncol=2, fontsize=8)

    ax = axs[5]
    if 'b3_grade' in f:
        ax.step(f.index, f.b3_grade, where='post', color='#8b8d8d', lw=.9,
                label='旧B3类别，仅作失败/代价对照')
        ax.set_yticks([-2, -1, 0, 1, 2], OLD_LABELS)
        ax.set_ylim(-2.4, 2.4)
    else:
        ax.text(.5, .5, '此路径未附旧B3结果', transform=ax.transAxes,
                ha='center', va='center', color='#77858b')
        ax.set_yticks([])
    ax.set_ylabel('旧B3对照\n不是B4总温度')

    ax = axs[6]
    if 'b1_strength' in f:
        ax.plot(f.index, f.b1_strength, color='#9b83b5', lw=.85, label='旧B1分数')
        ax.legend(loc='upper left', fontsize=8)
    else:
        ax.plot(f.index, col(f, 'activity'), color='#71978a', lw=.8,
                label='当日量 / 滞后量中位数')
        ax.axhline(1, color='#aaa', ls='--', lw=.6)
        ax.legend(loc='upper left', fontsize=8)
    ax.set_ylabel('旧B1对照' if 'b1_strength' in f else '相对量')
    for ax in axs:
        ax.grid(alpha=.15)
        ax.margins(x=.01)
    fig.text(.99, .008,
             '方向/推进/结构/急性事件分开；结构可陈旧；不是上涨概率或交易信号；E0未改；账户0',
             ha='right', fontsize=9, color='#60727b')
    fig.tight_layout(rect=(0, .025, 1, 1))
    fig.savefig(path, dpi=120)
    plt.close(fig)


def synthetic_source(sid):
    candidates = [ROOT / 'validation' / f'{sid}.parquet',
                  ROOT / 'validation' / 'derived' / f'{sid}.parquet']
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError(f'Missing fixed synthetic result {sid}')


def main(kind):
    if kind not in {'real', 'synthetic', 'derived'}:
        raise ValueError('kind must be real, synthetic, or derived')
    target = ROOT / 'figures' / kind
    target.mkdir(parents=True, exist_ok=False)
    records = []
    if kind == 'real':
        windows = read(B3 / 'figures' / 'real-manifest.json')['plots']
        for w in windows:
            f = pd.read_parquet(ROOT / 'results' / (w['asset'] + '.parquet')).loc[w['start']:w['end']]
            p = target / (w['id'] + '.png')
            draw(f, f"{w['name']} {w['asset']} · {f.index[0].date()}—{f.index[-1].date()}", p)
            records.append({**{k: w[k] for k in ['id', 'asset', 'name', 'start', 'end']},
                            'actual_start': str(f.index[0].date()), 'actual_end': str(f.index[-1].date()),
                            'path': str(p), 'sha256': sha(p)})
        assert len(records) == 22
    else:
        ids = ([x['id'] for x in read(B3 / 'figures' / 'synthetic-manifest.json')['plots']]
               if kind == 'synthetic' else ['shock_then_slow_decline'])
        for sid in ids:
            src = synthetic_source(sid)
            f = pd.read_parquet(src)
            old_path = B3 / 'validation' / f'{sid}.parquet'
            old_attached = False
            if kind == 'synthetic' and old_path.exists():
                old = pd.read_parquet(old_path)
                if 'grade' in old:
                    f = f.join(old[['grade']].rename(columns={'grade': 'b3_grade'}))
                    old_attached = True
            p = target / f'{sid}.png'
            draw(f, ('固定派生压力路径 · ' if kind == 'derived' else '固定合成 · ') + sid, p)
            records.append({'id': sid, 'source': str(src), 'path': str(p), 'sha256': sha(p),
                            'b3_comparison_attached': old_attached,
                            'b3_source': str(old_path) if old_attached else None})
        assert len(records) == (24 if kind == 'synthetic' else 1)
    write(ROOT / 'figures' / f'{kind}-manifest.json', {'recorded_at': now(), 'plots': records})
    print({'kind': kind, 'plots': len(records)}, flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
