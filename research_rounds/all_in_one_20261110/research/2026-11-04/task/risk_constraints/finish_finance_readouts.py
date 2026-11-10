"""Bind completed saved-book analyses and their independent audits; no accounts."""
from pathlib import Path
from decimal import Decimal as D
import hashlib
import json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def load(p):
    return json.loads(p.read_text())


def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def save(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, indent=2, default=str) + '\n')


def fmt(x, places=2):
    return f'{D(str(x)):,.{places}f}'


def main():
    year_path = HERE / 'no60_continuation2023_finance/COMPARISON.json'
    d1_path = HERE / 'no60_d1_strong_finance/COMPARISON.json'
    year = load(year_path)
    d1 = load(d1_path)
    yr_audit_path = ROOT / 'independent_review/PVR_2023_INDEPENDENT_AUDIT.json'
    d1_audit_path = ROOT / 'independent_review/PVR_D1_STRONG_INDEPENDENT_AUDIT.json'
    yr_audit = load(yr_audit_path)
    d1_audit = load(d1_audit_path)
    checks = []

    def same(scope, name, x, y):
        error = abs(D(str(x)) - D(str(y)))
        assert error < D('0.000000001'), (scope, name, error)
        checks.append(dict(scope=scope, metric=name, absolute_error=error))

    for ref in ('PVR_SLOT1', 'PVR_NO_CONFIRMED60'):
        a, b = year[ref], yr_audit[ref]
        same(ref + '_2023', 'NAV', a['end_NAV'], b['NAV'])
        same(ref + '_2023', 'year_return_pct', a['year2023_return_pct'], D(b['own_year_segment']['return_on_own_parent']) * 100)
        same(ref + '_2023', 'year_DD_pct', a['year2023_DD']['percent'], D(b['own_year_segment']['own_year_close_DD']) * 100)
        same(ref + '_2023', 'cumulative_DD_pct', a['cumulative_2022_2023_DD']['percent'], D(b['close_DD']) * 100)
        same(ref + '_2023', 'cumulative_fees', a['cumulative_fees'], b['fees'])
        assert a['source_parent_prefix_exact'] and a['original_1m_not_reset'] and a['Jan3_included_in_year']
        assert not a['terminal_positions'] and a['pending_exit_stocks'] == 0
        assert not a['cumulative_money_split']['open_layers_with_partial_sales']
    for ref, audit_ref in (('PVR_SLOT1_D1', 'PVR_D1'), ('PVR_NO_CONFIRMED60_D1', 'NO60_D1')):
        a, b = d1[ref], d1_audit[audit_ref]
        m, money = a['metrics'], a['money_split']
        same(ref, 'NAV', D(m['return_pct']) * 10000 + 1000000, b['NAV'])
        same(ref, 'DD_pct', m['global_DD']['percent'], D(b['close_DD']) * 100)
        same(ref, 'mean_exposure_pct', m['mean_exposure_pct'], D(b['mean_exposure']) * 100)
        same(ref, 'fees', m['fees'], b['fees'])
        same(ref, 'actual_trade_money_bridge', sum((D(money[k]) for k in ('position_closed_layer_cash_net', 'open_layer_cash_plus_mark', 'recognized_dividend')), D(0)), D(b['NAV']) - 1000000)
        assert not money['open_layers_with_partial_sales']
        assert not money['explicit_nontrade_journal']
        assert a['verification']['daily_native_financial_bridges'] == 242
        assert a['verification']['account_runs'] == 0
        semi = load(HERE / f'no60_d1_strong_finance/{ref}_THEMES.json')[0]
        assert semi['sector'] == 'URFI881121'
        for k, other in [('actual_buy_cash', 'actual_buy_cash'), ('interval_net_contribution', 'interval_contribution')]:
            same(ref, 'semiconductor_H1_' + k, semi[k], b['semiconductor_H1'][other])
        same(ref, 'semiconductor_H1_mean_weight_pct', semi['mean_weight_pct'], D(b['semiconductor_H1']['mean_weight']) * 100)
    same('2023', 'delta_NAV', year['end_NAV_difference'], yr_audit['delta_NAV'])
    same('D1', 'delta_NAV', d1['matched_D1_delta_NAV'], d1_audit['delta_NAV'])

    manifests = [HERE / 'no60_continuation2023_finance/SOURCE_MANIFEST.json', HERE / 'no60_d1_strong_finance/SOURCE_MANIFEST.json']
    rechecked = {}
    for p in manifests:
        for path, expected in load(p)['sources'].items():
            actual = sha(Path(path))
            assert actual == expected, ('changed_source', path)
            rechecked[path] = actual
    guards = [HERE / 'PVR_2023_SPLIT_QUANTITY_CHECK.json', HERE / 'PVR_D1_SPLIT_QUANTITY_CHECK.json']
    for p in guards:
        guard = load(p)
        assert guard['passed'] and guard['financial_events'] == 0
        for row in guard['rows']:
            assert not row['fractional_conversion_events'] and row['terminal_each_layer_quantity_exact']
            assert sha(Path(row['source'])) == row['source_sha256']
    bindings = [year_path, d1_path, yr_audit_path, d1_audit_path, *manifests, *guards, Path(__file__)]
    save(HERE / 'NO60_LATEST_FINANCE_AUDIT_BINDING.json', dict(
        passed=True, financial_events=0, independent_metric_checks=checks,
        saved_source_sha_rechecks=len(rechecked), unchanged_sources=rechecked,
        bound_deliverables={str(p): sha(p) for p in bindings},
        scope='Read-only numeric cross-check of our saved-book analyses against independent raw-book audit. Split guards reuse the earlier algorithm and are not an independent second quantity algorithm.'))

    old, new = year['PVR_SLOT1'], year['PVR_NO_CONFIRMED60']
    yrows = [
        ('2022-12-30 自身净值（元）', old['initial_2023_own_Dec30_NAV'], new['initial_2023_own_Dec30_NAV']),
        ('2023-12-29 净值（元）', old['end_NAV'], new['end_NAV']),
        ('2023 自身本金段收益率（%）', old['year2023_return_pct'], new['year2023_return_pct']),
        ('2023 段最大收盘回撤（%）', old['year2023_DD']['percent'], new['year2023_DD']['percent']),
        ('2022→2023 累计收益率（%）', old['original_1m_cumulative_return_pct'], new['original_1m_cumulative_return_pct']),
        ('2022→2023 累计最大收盘回撤（%）', old['cumulative_2022_2023_DD']['percent'], new['cumulative_2022_2023_DD']['percent']),
        ('2023 平均持仓暴露（%）', old['year_mean_exposure_pct'], new['year_mean_exposure_pct']),
        ('2023 平均名义风险 / NAV（%）', old['year_mean_nominal_risk_pct'], new['year_mean_nominal_risk_pct']),
        ('2023 累计含费买入款（元，可循环使用资金）', old['year_buy_cash'], new['year_buy_cash']),
        ('2023 买卖费用（元）', old['year_fees'], new['year_fees']),
        ('两年累计买卖费用（元）', old['cumulative_fees'], new['cumulative_fees']),
        ('2023 ACT 暂停收盘数', old['year_paused_closes'], new['year_paused_closes']),
    ]
    ytext = '''# No60 自身 2023 连续账财务收口

No60 在自身 2022 账上继续至 2023 年末，终值高于原 PVR 82,869.05 元；两年仍亏 25.46%。这是继承自身资本、持仓和 ACT 状态的连续路径证据，不能称单独的 2023 alpha。

| 指标 | 原 PVR | No60 |
|---|---:|---:|
'''
    ytext += '\n'.join(f'| {name} | {fmt(a)} | {fmt(b)} |' for name, a, b in yrows)
    ytext += '''

两条路径均从 2022 年原始 100 万出发；2023 各自以自身 2022-12-30 净值计算段收益。年内 242 收盘（含 Jan3），全年累计账 484 收盘；No60 接自己的 Jan3 完整技术检查点后续跑，已验证 2022 前缀和交易前缀完全一致，没有重置本金、替换策略中途状态或重复 Jan3。

2023 年末两臂均已空仓，未实现贡献为零。累计实际交易净损益原 PVR −343,546.85 / No60 −261,335.88 元；未收股息应收款 6,104.76 / 6,762.84 元单列，二者分别与原始本金桥接至最终财富。实际卖出成本只扣一次。逐层拆股回放各有 5 个持仓拆股层事件，零碎股核销均为零，终态每层数量精确一致，支持这次严格实际交易损益口径。

原 PVR 于 Sep21 ACT 暂停，No60 于 Jul20 暂停，之后均未恢复；No60 更早暂停且有 111 个暂停收盘，原 PVR 为 66 个。因此较低累计回撤并不等于持续捕获行情。记录型累计亏损 ledger 是统计字段，不是新的可用预算，未并入财富或重复扣除。

主数据：`no60_continuation2023_finance/COMPARISON.json`；逐日：同目录 `*_2023_DAILY.json`；源指纹：`SOURCE_MANIFEST.json`；拆股收据：`PVR_2023_SPLIT_QUANTITY_CHECK.json`。独立审核：`../independent_review/PVR_2023_INDEPENDENT_AUDIT.json`。最新 source SHA 及 2023/D1 数值交叉绑定：`NO60_LATEST_FINANCE_AUDIT_BINDING.json`。没有启动账户事件。

此结果仍限现有 1709 股开发样本、当前幸存者/行业定义和原日线执行近似。120 万实际本金、港股和样本外尚未验证；35% 回撤边界不构成成功标准。
'''
    (HERE / 'NO60_2023_CONTINUATION_READOUT.md').write_text(ytext)

    old, new = d1['PVR_SLOT1_D1'], d1['PVR_NO_CONFIRMED60_D1']
    drows = [
        ('终值（元，初始 100 万）', d1_audit['PVR_D1']['NAV'], d1_audit['NO60_D1']['NAV']),
        ('全段收益率（%）', old['metrics']['return_pct'], new['metrics']['return_pct']),
        ('最大收盘回撤（%）', old['metrics']['global_DD']['percent'], new['metrics']['global_DD']['percent']),
        ('平均持仓暴露（%）', old['metrics']['mean_exposure_pct'], new['metrics']['mean_exposure_pct']),
        ('平均名义风险 / NAV（%）', old['mean_nominal_risk_pct'], new['mean_nominal_risk_pct']),
        ('平均可支用现金 / NAV（%）', old['mean_available_cash_pct'], new['mean_available_cash_pct']),
        ('平均已预留资产 / NAV（%，含预留费用）', old['mean_reserved_assets_pct'], new['mean_reserved_assets_pct']),
        ('累计实际含费买入款（元，可循环使用资金）', old['metrics']['buy_cash'], new['metrics']['buy_cash']),
        ('累计实际买卖费用（元）', old['metrics']['fees'], new['metrics']['fees']),
        ('严格已实现交易净损益（元）', old['money_split']['position_closed_layer_cash_net'], new['money_split']['position_closed_layer_cash_net']),
        ('未实现净贡献（元，含分摊买费）', old['money_split']['open_layer_cash_plus_mark'], new['money_split']['open_layer_cash_plus_mark']),
        ('未收股息应收（元）', old['money_split']['unpaid_dividend_AR'], new['money_split']['unpaid_dividend_AR']),
    ]
    dtext = '''# No60 同压力 D1 强窗财务收口

在各自原生 D1v2 路径上，No60 增加最终财富 467,280.68 元；收益由 63.68% 增至 110.41%，最大收盘回撤由 8.82% 增至 11.70%。更多资本实际进入账户是收益增加的重要经济取舍，尚不能用暴露线性缩放或费用机械相除解释为 alpha。普通亏损和半导体参与质量仍未解决。

| 指标 | 原 PVR D1 | No60 D1 |
|---|---:|---:|
'''
    dtext += '\n'.join(f'| {name} | {fmt(a)} | {fmt(b)} |' for name, a, b in drows)
    dtext += '''

两个匹配路径均覆盖 2025-07-01→2026-06-30 共 242 收盘；No60 继承自身 D1 Jul3 技术前缀，其余信号、排序、2% 目标、原风险/行业合同、退出与 ACT 按授权保留。主对照是同一 D1 压力下原 PVR。正常路径原 PVR / No60 收益 94.90% / 126.33%，政策收益差 31.43 个百分点；D1 匹配差 46.73 个百分点，交互差为 15.30 个百分点。这是整段路径差，不能理解为将每笔收益简单扣一天。

日均预留资产包括本金和预留费用，不能算可支用闲置现金；卖出未结算回款亦非可支用。两臂预留订单 1,481 / 1,401 个，实际成交 960 / 1,014 个；零成交预留 521 / 387 个含终态仍 pending，不能全部叫取消。两臂均无 ACT 暂停。

242 个收盘的现金、预算/资本/池占用、独立数量与累计费用桥均通过，截止 Jun30 15:10，无未来交易或 audit。无仍持仓且已部分卖出的层；逐层拆股回放 old 7 / new 9 个持仓拆股层事件，碎股核销均零且终态每层数量精确一致，故表中实际交易/未实现口径成立。股息应收全未支付；未并入可用现金，也未二次减费。闭合的是财富与资金账，不是交易可实现性认证。

严格半导体 `URFI881121` 的 2026H1 单独重算：含费买款 192,214.74→344,741.85 元，成交买单 12→19，平均权重 1.09975%→1.89566%，期末权重 1.42225%→3.32205%；但区间净贡献 −5,851.74→−7,765.69 元。电子化学品贡献 152,689.76→87,737.14 元，元件 76,042.03→141,634.48 元均单列，没有归入半导体。因此 D1 也不支持“半导体参与问题已修复”。

主数据：`no60_d1_strong_finance/COMPARISON.json`；主题逐日：同目录 `*_THEMES.json`；全股票财富桥：`ALL_STOCK_WEALTH_BRIDGE.json`；源指纹：`SOURCE_MANIFEST.json`；拆股收据：`PVR_D1_SPLIT_QUANTITY_CHECK.json`。独立审核：`../independent_review/PVR_D1_STRONG_INDEPENDENT_AUDIT.json`。最新 source SHA 及数值交叉绑定：`NO60_LATEST_FINANCE_AUDIT_BINDING.json`。没有启动账户事件。

仍限现有 1709 股开发样本、当前幸存者/行业定义和原日线执行近似。120 万实际本金、港股和样本外尚未验证。主要收益包含开放持仓账面贡献，不能只凭当期正收益或低于 35% 回撤判断成功；普通亏损、趋势识别和买错纠偏继续按独立行为审查推进。
'''
    (HERE / 'NO60_D1_MATCHED_READOUT.md').write_text(dtext)
    sources = {str(p.relative_to(HERE)): sha(p) for p in HERE.rglob('*') if p.is_file() and p.name != 'MANIFEST.json' and '__pycache__' not in p.parts}
    save(HERE / 'MANIFEST.json', sources)
    print('PASS', len(checks), 'numeric cross-checks;', len(rechecked), 'source SHA rechecks;', len(sources), 'deliverables')


if __name__ == '__main__':
    main()
