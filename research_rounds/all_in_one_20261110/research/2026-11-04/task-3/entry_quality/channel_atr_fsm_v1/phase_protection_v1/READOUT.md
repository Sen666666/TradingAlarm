# 固定2S后TREND4：五股291原CP锚

已实际运行291个新phase保护影子尝试，290有完整步骤，1保留原入口报价未知。未重跑原E0/I/CP FSM、原账户；控制CP分支逐锚直接复用saved pair，未重选母体、未调整2S/4ATR。

152锚达到2S且当close切TREND4；275退出（132 EARLY、143 TREND4），15阶段影子右截尾，1不可评。双方已退出的275对：200同日、64阶段更晚、11阶段更早。所有路径输入ever_unknown=0；未知处理、2S被硬退出抢先等未出现分支只经静审，不声称运行覆盖。

| 股/固定最早锚 | E/S（调整坐标） | 首2S/切换 | CP退出 | 新phase退出 | 新next raw OPEN参考 |
|---|---|---|---|---|---:|
|000620.SZ 2022-01-07|2.92701590 / 0.12461986|2022-01-11|2022-01-19|2022-01-19 EXIT_STORED_LINE|2.95|
|002583.SZ 2024-09-20|26.75087268 / 0.72941885|2024-09-24|2024-11-04|2024-11-04 EXIT_NEW_TREND4_PROPOSAL|23.0|
|300085.SZ 2024-09-12|45.91754137 / 1.74134465|2024-09-19|2024-10-10|2024-10-11 EXIT_STORED_LINE|30.98|
|603061.SH 2025-12-04|135.01404008 / 5.46022600|2025-12-25|2026-02-11|2026-03-11 EXIT_ORIGINAL_I_INVALID_CURRENT|240.22|
|300623.SZ 2026-01-09|208.89182380 / 4.36106547|2026-01-21|2026-02-02|2026-02-02 EXIT_STORED_LINE|32.99|

这些是市场锚后下一观察OPEN的条件层，不是实际fill/资金许可；E、S、P0同调整坐标冻结，第一持有bar只用完成C更新峰，之后H才供下一close提线。实际每fill子合同、T+1、live改单/撤单ACK均没有在此冒充实现。新层方案不能迁改旧实仓，不保证按线卖出。

切换同close存在原CP收据121次，按预先合同忽略尚未安装的新candidate；不会撤掉此前已生效P。TREND4可判提线步骤的driver为继承旧P1452、I硬底86、ATR4主导888，因此“进入TREND”并不自动变成更松止损。

所有11个更早退出反例完整保存。首例盈2023-6/1锚在6/9切；8/14 ATR收缩使4ATR提案抬P到2.0146347081，8/21收盘1.9361583753触旧P，原CP到8/24才退。金海通最早case更晚到3/11才退，但next原价参考240.22低于CP2/12参考270.24；不能把更晚或共同后续峰称为收益提升。

银原实际失败入场信号10/9也是本固定母体：从未达到2S或切换TREND4，10/10仍EARLY旧P退出，与CP同日。最早9/12锚的phase更晚，不可拿它替代原10/9入场条件来声称避开损失。

原CP/新phase退出期限可能不同，15阶段右截尾与入口不可评另列，未填为风险0；没有计算新收益、数量、现金、手续费或账户反馈。

控制/新phase结果分母：`{'EXIT_SIGNAL / EXIT_SIGNAL': 275, 'RIGHT_CENSORED / RIGHT_CENSORED': 10, 'NOT_EVALUATED / NOT_EVALUABLE_ORIGINAL_ENTRY_STATE': 1, 'EXIT_SIGNAL / RIGHT_CENSORED': 5}`。

入口：[RUN_RECEIPT.json](run_v1/RUN_RECEIPT.json)、[SUMMARY.json](run_v1/SUMMARY.json)、[5固定案例全steps](run_v1/FIVE_FIXED_EARLIEST_CASES.json)、[11更早反例](run_v1/ALL_11_EARLIER_COUNTEREXAMPLES.json)、[单调/峰/unknown复核](run_v1/POSTPROCESS_INVARIANTS.json)。每股`*_ANCHOR_SHADOWS.json`保留所有锚与每一步oldP/Q/CP未采用/phase/2S/exit/nextOPEN。

代码已绑定且不改：phase.py `3beb9045c40d7be116a1580dc6608e65c8c52de13c64b868f2a7dff7b2a72540`；run_phase.py `3c09354622717953a1664bff2e75c97878bfcf49a5baef398057567c3fc5c4d1`；FREEZE `9e1c953f94c8d12e4610f39bc8ea136a3f7fdc8b9686e9af39125632e8abb525`。
