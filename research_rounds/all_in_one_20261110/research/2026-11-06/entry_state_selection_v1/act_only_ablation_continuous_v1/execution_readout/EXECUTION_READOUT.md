# ACT 单因素连续账户：执行与精确回归报告

## 已完成结果

唯一一次 native paired run 完成，2022-01-01至2026-05-15；共1054个交易收盘。两臂从120万元空仓连续推进，不导入旧账户，不年度重置。执行本体及所有最终检查约1109.5秒，无失败、无重跑、无实盘订单。此报告为执行工作自验，最终独立审计及完整回合归因另列。

- 原 PVR：末NAV 1,254,596.96元，累计收益4.55%，全期最大回撤47.72%。
- NOACT：末NAV 1,403,251.97元，累计收益16.94%，全期最大回撤42.45%。
- NOACT末NAV高148,655.00元，收益差12.39个百分点；这不是ACT暂停机会逐条可追回利润。
- 平均持仓资产/NAV由64.16%升至82.94%，平均持股52.01升至68.62只；暂停收盘252降至0。
- 全期成交笔数 PVR 6472 / NOACT 7575；手续费 PVR 66832.86 / NOACT 77621.20元。

## 年度NAV与收益（前一年末NAV为下一年起点）

|年|PVR年末NAV|PVR年度收益|NOACT年末NAV|NOACT年度收益|
|---|---:|---:|---:|---:|
|2022|840,906.26|-29.92%|899,981.95|-25.00%|
|2023|856,424.20|1.85%|859,025.82|-4.55%|
|2024|770,085.81|-10.08%|770,956.69|-10.25%|
|2025|981,630.11|27.47%|1,109,812.32|43.95%|
|2026至5/15|1,254,596.96|27.81%|1,403,251.97|26.44%|

2023年NOACT年度收益比PVR更差，不能把全期改善描述成每段都更好。2026为截至5月15日的部分年度。最大回撤由整个连续NAV路径计算，非年度DD相加；年度明细另见ANNUAL_NAV.csv。

## 唯一策略差异

只对标签NOACT把原risk_policy.step的ACT20_BREAK调用分发到原CONTROL早退，保留初始on=True。因此ACT不再强卖、暂停买入或等待BREAK63恢复。PVR仍调用原ACT20_BREAK。双方原PVR排序一致，无E31重排。原planning/opening、CORE epoch、MOBILE/加减仓、所有原route和预算、账本、费用、公司行动、会计桥均保持native绑定。

原基线本来已移除全户3%名义风险和confirmed60%资本上限；本次两臂均沿用，绝未在此次另行移除或意外恢复。无参数扫描。

## 验证与隔离

1. 源及依赖：旧PVR的44项声明源当前一致；新运行共89项实际依赖/输入/私有代码冻结项前后不变。旧run整树29个文件前后SHA一致。原数据与源文件未写入。
2. 初始账户深层mutable graph：各135节点，跨臂共享0；market/facts共享原只读视图。每event另检查实例与容器隔离。
3. PVR在线回归：1054逐日全字段、6472增量成交零容差一致。最终PVR账户全部11字段（含订单ID、成交ID、audit、budget）完全一致，不改ID、不豁免标签或序列。
4. 六类PVR日志完整复核：daily1054、opportunities1801286、funding208654、industry25247、balances1054、rank-policy144926，共2182221条。PVR全部年度指标也exact。
5. 2022-02-07非空OPEN和2022-04-22首次ACT后OPEN：同一checkpoint分别原序、逆两账户序、当前及未来HLCV毒化三次执行，完整账户状态和日志一致。只允许跨账户日志分组顺序规范化，不改经济值或同账户序。毒化含raw volume及positive/good未来索引。所有内存扰动恢复，未写原源。
6. OPEN公开行情只有open一列，facts.row/floor/packet访问均被拒；固定原ACT暂停/恢复日期只用于验证，不是NOACT输入。
7. 全部CLOSE独立现金/分红/NAV桥、预算镜像一致检查和2108次OPEN现金桥通过。

## 边界

当前原driver已经是已知正OPEN±5bp、过去20个正成交量观察1%容量代理，不是同日H/L/V准入。通过未来毒化证明的是该代理的工程时钟，不是现实可成交。涨跌停排队、停牌/可交易性及真实成交仍UNKNOWN。

固定未来1709股池、当前行业映射、公司行动terms assumed preknown、幸存偏差和NON-PIT边界保留。所有历史为开发样本，不称OOS或生产策略，不据此承诺胜率。完整0→0回合、尾部参与及资金占用归因由独立分析继续完成。

## 可核查产物

- run/DONE.json、OUTPUT_HASHES.json：完成与48项产物哈希，failure目录为空。
- run/pair/PVR.json.gz、NOACT.json.gz及六类明细日志。
- run/FINAL_PVR_EXACT_REGRESSION.json、BASELINE_DAILY_EXACT.json。
- run/RESTART_OPEN_ORDER_GATE_2022-02-07.json及2022-04-22.json。
- run/ORIGINAL_OUTPUTS_UNCHANGED.json、RUNTIME_DEPENDENCY_FREEZE.json。
- run/ANNUAL_METRICS.json、FULL_PERIOD_METRICS.json、PERIOD_METRICS.json。
- code/内私有驱动及验证代码，CONTRACT.md、STATIC_FREEZE.json、DRIVER_DIFF.patch；source_history/prelaunch_v1只为预启动准备版本，未运行账户。
