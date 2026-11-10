"""Post-result aggregations only; no financial path or decision is rerun."""
import csv
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'analysis-v1'
ORDER = ['F100', 'F10', 'F30', 'A', 'B', 'C', 'D']
NAMES = dict(zip(ORDER, ['固定100万', '固定10万', '固定30万', '阶梯只加', '温度只加', '温度双向', '强冷削层']))

def read(name):
    with (OUT / name).open() as f:
        yield from csv.DictReader(f)

def table(headers, rows):
    return '| ' + ' | '.join(headers) + ' |\n| ' + ' | '.join(['---'] * len(headers)) + ' |\n' + ''.join('| ' + ' | '.join(map(str, r)) + ' |\n' for r in rows)

def main():
    stocks = list(read('stocks.csv'))
    sectors = defaultdict(lambda: [0.0, 0.0, 0])
    for r in stocks:
        key = (r['account'], r['policy'], r['scenario'], r['industry'])
        a = sectors[key]
        a[0] += float(r['net_profit']); a[1] += float(r['tail_profit']); a[2] += 1
    with (OUT / 'industries.csv').open('x') as f:
        w = csv.writer(f); w.writerow(['account', 'policy', 'scenario', 'industry', 'net_profit', 'tail_profit', 'stocks'])
        for k, v in sorted(sectors.items()): w.writerow([*k, *v])
    base_stocks = sorted([r for r in stocks if r['policy'] == 'F100' and r['scenario'] == 'base'], key=lambda r: float(r['net_profit']), reverse=True)
    chosen = [r['symbol'] for r in base_stocks[:5]]
    text = '# 资金峰值、固定赢家和实际周期复查\n\n本文件仅聚合既有21条路径，不重跑资金，不据结果调参。个股正反例沿经济前图检名单；行业与年度全量CSV保留。\n\n'
    text += '## 资金需求为何反而上升\n\n'
    peaks = []
    curves = defaultdict(list)
    for r in read('curves.csv'):
        if r['scenario'] == 'base': curves[r['policy']].append(r)
    for p in ORDER:
        rs = curves[p]; peak = max(float(r['funding_to_date']) for r in rs)
        r = next(r for r in rs if float(r['funding_to_date']) >= peak - 0.01)
        peaks.append([NAMES[p], r['date'], f'{peak/1e8:.2f}', f'{float(r["market_value"])/1e8:.2f}', f'{float(r["pnl"])/1e8:.2f}', r['holdings']])
    text += table(['方案', '首次达到最终K日期', 'K亿元', '当日收盘市值亿元', '当日累计净利润亿元', '当日股数'], peaks)
    text += '\n四动态方案最终资金峰值都出现在2024-10-08，收盘同时持有约1611—1612股。温度加仓没有全账户预算，强行情中各股能一起升档。平均暴露低并不约束同步追加时的峰值；先前盈利较少也减少了可循环的内部资金。K还含预约/结算，不能用收盘市值减累计利润精确替代。以上是现有流水的机制解释，不是另一次控制变量实验。\n\n'
    text += '## 固定原基准前五贡献股\n\n全区间净利润，单位万元；名单取原F100，仅供事后诊断，从未参与开仓或参数选择。\n\n'
    rows = []
    for s in chosen:
        rs = [r for r in stocks if r['symbol'] == s and r['scenario'] == 'base']; by = {r['policy']: r for r in rs}
        rows.append([s, by['F100']['name'], *[f'{float(by[p]["net_profit"])/1e4:.2f}' for p in ORDER]])
    text += table(['代码', '名称', *[NAMES[p] for p in ORDER]], rows)
    examples = defaultdict(list)
    fixed_examples = {'688498.SH', '301377.SZ', '000620.SZ', '000063.SZ'}
    for r in read('campaigns.csv'):
        if r['scenario'] == 'base' and r['symbol'] in fixed_examples: examples[r['symbol']].append(r)
    text += '\n## 实际大盈利周期\n\n沿经济前两只正例，各展示原F100净利润最大的实际持仓周期；其他方案以相同首次成交时刻匹配，缺失时明确空白。这是结果后的交易解释，不代表预先知道最大周期。单位万元。\n\n'
    for s in ['688498.SH', '301377.SZ']:
        ref = max([r for r in examples[s] if r['policy'] == 'F100'], key=lambda r: float(r['net_pnl']))
        text += f'### {ref["name"]}：{ref["entry_at"][:10]}起，' + (f'{ref["exit_at"][:10]}退出' if ref['closed'] == 'True' else '期末仍开放') + '\n\n'
        rs = {r['policy']: r for r in examples[s] if r['entry_at'] == ref['entry_at']}
        text += table(['方案', '首仓款', '累计追加款', '实际买入次数', '实际卖出次数', '周期净损益', '期末剩余股数'], [[NAMES[p], *[f'{float(rs[p][k])/1e4:.2f}' for k in ['initial_gross', 'add_gross']], rs[p]['buy_fills'], rs[p]['sell_fills'], f'{float(rs[p]["net_pnl"])/1e4:.2f}', rs[p]['final_shares']] if p in rs else [NAMES[p], '未匹配', '', '', '', '', ''] for p in ORDER])
    text += '\n累计追加款可以超过100万元，因为卖出释放平均成本额度；不是突破当前未卖持仓成本上限。C/D按平均成本留10万元，并非保留原始10万元股份不动。温度削减会降低长趋势后半段的股份，恢复又受旧买入信号锚与盈利约束，不能由本轮否定所有其他分层仓位规则。\n\n'
    text += '## 全年份与行业\n\n年度为逐日权益增量，2026截至10月22日，金额亿元，不是年收益率。\n\n'
    annual = defaultdict(dict)
    for r in read('annual.csv'):
        if r['scenario'] == 'base': annual[r['year']][r['policy']] = float(r['net_profit'])
    text += table(['年份', *[NAMES[p] for p in ORDER]], [[y, *[f'{a[p]/1e8:+.3f}' for p in ORDER]] for y, a in sorted(annual.items())])
    text += '\n按原F100净利润排序的前五及后五行业，名单只作诊断；完整全部方案/情景/行业见industries.csv，单位亿元。\n\n'
    inds = sorted([(k[3], v[0]) for k, v in sectors.items() if k[1] == 'F100' and k[2] == 'base'], key=lambda x: x[1], reverse=True)
    selected = [i for i, _ in inds[:5]] + [i for i, _ in inds[-5:]]
    text += table(['行业', *[NAMES[p] for p in ORDER]], [[i, *[f'{sectors[(p+"__S0_base", p, "base", i)][0]/1e8:+.3f}' for p in ORDER]] for i in selected])
    text += '\n当前行业快照固定回看，不是历史时点已知行业归属。没有根据本表重选行业池。\n'
    (HERE / 'ATTRIBUTION.md').write_text(text)
    print('Post-result aggregation complete; no financial replay.')

if __name__ == '__main__': main()
