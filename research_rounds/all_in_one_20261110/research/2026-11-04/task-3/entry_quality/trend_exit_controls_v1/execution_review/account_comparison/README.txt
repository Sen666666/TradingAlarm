最终状态：全部 5 臂 x 2 账户比较已完成，最终 results_v2/READOUT.txt。
VALIDATION 与父35行 NAV_MATRIX 独立交叉核对均 PASS。results_v1 仅报告字段
closed 重名错误保留；修正后只重跑只读分析，经济账户重放 0。

脚本 compare_accounts.py 不导入 Runner、Account、ledger 或执行器；只读已完成
runs/<arm>/<2022_2024,strong>/pair/{B.json.gz,daily.jsonl.gz}、TIMING、metadata，
以及冻结原事实和只读指标 provider。缺失/未完成时拒绝发布结果。

固定臂 BASELINE、EARLY_EMA20/60、EARLY_BOLL20_MID/LOWER 全列。
固定日历：连续 2022—24 全段、各年、2024-09-24起至年末、10-08后至年末；
strong 2025-07-01—2026-06-30。年度起点用该臂前一真实收盘，不重置账户。
报告 NAV、净财富变化、strict realized/open unrealized/AR、区间重基回撤、
账户全历史峰值回撤、真实暴露/现金、费用/周转/买卖款、ACT 暂停与恢复。

每个原生日账以已实际闭合层的 cash、持有层原实际买款、原生 inventory、
分红 AR 做只读拆分，并以冻结 raw_close 对原生持仓总值精确核对。
已处理 EMA20三年603826与MID strong301338两处100→140送转后的部分卖出：
只读原buy/split/sell.parts算术逐时分配含买费basis，保留两part理由与原单clock，
逐日财富桥及独审终值核同。其他未知basis/实际分红支付仍停止，不占零或重造引擎。

跨臂完整键为 sid + role + CP receipt（core空）+真实 decision_at +实际 entry。
layerID 只在本账中关联实际买卖，不用于跨臂匹配。原 BASELINE 3436 层的
键、实际买款、原损益都须与既有已核母本一致。原 83/94 尾部全体保留，
当前基线精确匹配必须为 45/67。其余成员不补成已参与或可赚交易。

输出区分相同入场键退出提前/同日/延后、数量费用变化、未参与原键、
候选新路径、同股其他层在原赢家持有区间是否存在、早退后是否再有持仓。
全账户差额可精确分解为匹配层差额+候选新路径-基线缺席层，但这只是
实际路径恒等式，不把静态差额称为纯退出因果改善。资金释放后的投入、
仓位与ACT变化必须在账户层比较，不预设释放资金能赚钱。

退出单项消融不加 EMA 入场门：单列 decision CLOSE 已below、实际 OPEN
相对原决策已知线的位置，以及买入日 CLOSE below（明确买后才可见）。
按已记录的实际持有区间合并全股周期，保留工具实际清仓后新周期、再次
工具清仓与净额。原 core 同watch_epoch最多一个真实订单作必要一致性核查，
mobile 新 CP 可以重进；不替结果新增筛选或自动重开 core 权限。

本次实际使用以下命令并加 --out .../results_v2：
/Users/bytedance/.cache/uv/archive-v0/BCk79KzaN8dGdkNqEjF-9/bin/python \
  entry_quality/trend_exit_controls_v1/execution_review/account_comparison/compare_accounts.py

默认写本目录 results_v1，拒绝覆盖已有结果。输出带 source/deliverable SHA，
失败保留。无账户推进、无下单、无参数选择、无外部分享。
