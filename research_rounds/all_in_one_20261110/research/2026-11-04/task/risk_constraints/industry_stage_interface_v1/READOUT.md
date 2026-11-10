# 行业 pure trace / Stage 接口

原接口可以薄接。现有 assemble 已落的行业 `facts / q / CP1 / evidence` 足够，无须新增 full base 输出、旧 episode 编号或金融 Runner。这里只验证原三个行业：银行 URFI881155、电网设备 URFI881278、专用设备 URFI881118；没有运行90行业批次或账户。

可复用入口是 `dependency_fix_v2/pure_stage_wrapper.py::run_industry`。它只编译原 `cp1-evidence-trace-20261031/trace.py` 的 `ident/norm/trace`，以及原 `industry-mobile-stage-20261031/stage.py` 的 `Stage/run` AST；没有加载原模块顶层的 COM/common，也未复制改写状态机。Stage 的数值比较仍使用原 CP1 模型 `ge`。

行业 `q.e0_valid` 必须严格等于本臂 `facts.e0_target`，`q.i_floor` 等于本臂 E0 floor。原 trace 直接消费该布尔序列，原 Stage.run 自己重建 E0 episode；没有接受旧 episode、旧 probe/confirmed 金融level或旧观察日历的接口。原始 source segment、有效观察时钟、价格与 CP1 候选保持各臂原输入。

真量使用原 sid / 原 SCALE，以便核旧收据身份。中性 canonical 与 SCALE 带方法 namespace，避免两臂同 sid/day 的不同收据被错误合并。中性 trace 消费的是 CP1 输入副本 `m=effective_amount_multiplier=1`；原未消费的观测 `m` 单独存入 `AMOUNT_MULTIPLIER.parquet`，原 CP1 表未改。

验证结果：三行业真量 full-warm Stage 的4563 / 3031 / 4563行全部字段精确复现旧表，包含全warm每行的 receipt / episode / attempt / 授权身份。单独旧 compact receipt 表只保存既有审计日期，其10 / 24 / 19条全字段精确复现；没有把该表缺少的暖期行当成无事件。三行业中性在固定2024-09-23物理截断后，Stage状态、完整receipt以及已确认receipt内的原advance证据均等于全表对应前缀。

第一版在trace初始化时遗漏原标准库 `collections`，0.110756秒停止，尚无Stage输出；这不是模型或数据失配。原 wrapper/controller/freeze/FAILED 原样保留。root随后只授权一次依赖修复：新v2补import及AST环境注入，controller计时使用剩余预算，原算法、namespace和阈值未变。v2耗时4.440614秒，累计4.551370秒，小于共同30秒预算。`DEPENDENCY_ONLY_DIFF.patch` 与 `STATIC_GLOBAL_DEPENDENCIES.json` 保留差分及所有抽取节点外部全局依赖核对。

实际结果位于 `dependency_fix_v2/{COMPLETED.json,REAL_REFERENCE_GATES.json,NEUTRAL_PHYSICAL_PREFIXES.json}`；每行业每臂保存 `Stage.parquet / TRACE_RECEIPTS.json / IDENTITY.json`。完整源、输入和方法身份在两版 `SOURCE_FREEZE.json`。整合时由唯一full controller绑定该wrapper及其相邻freeze，不自动调用三行业验证controller。

本结果是接口与时钟一致性证据。尚未验证其余87行业、全1709中性ACT、实际3436填单决策许可或83/94固定赢家作用，也没有构造金融授权、资金重排或PnL/NAV。不能用Stage改变次数推断质量改善。完整导出和经济运行仍需另行授权。
