# V12 真实 M7 接口独立复验

结论：PASS_FOR_ONE_FROZEN_OFFLINE_EXPERIMENT。允许父级按以下静止源码封存一次离线实验；这不是经济效果、PIT、真实撮合或实盘许可。无剩余阻断。

冻结：
- engine.py：2e37d2a20e33760ffdb1b1b9ba84f8edce7492a3162880ba800759d8773cdd72
- synthetic_tests.py：808f541527f67fdbe1090269a2dd61d6959e41fff044d0a9a9e341a3a9764b53
- SOURCE_HASHES.json：7e78f1851781f89c168123585d0d807d9f00527f7f1885a7e158fb95d3b50554
- 原基线仍是 mainline_m7_cash_batch_design_v6；最终合同为 EXECUTION_FREEZE_ADDENDUM.md SHA256 3ffa6bd951e2377e65a83f9ee13bd3a2ed320970ed0f03fd277398e1b9856bd1。

## 已独立执行

1. 101 条冻结测试断言，包含原 19 条合同选择器和真实 M7 原方法集成合成。
2. 8 条审查者独立追加断言：CLOSE 对次日全部 quote/factor/I/CP/M/stock 扰动不变；OPEN H/数量/选枝对当日后验 bar 资格、H/L/C/volume 与信号扰动不变；退让 fresh SEED 的原 attempt budget 失败不保活；OPEN 不改冻结 book；每枝哈希可重建。
3. 3 份既有事实/CP parquet 的原始标量类型检查：I 沿原 truth/false 接受整数与布尔，CP receipt 仅 bool/np.bool_。未构建真实 Data。
4. 候选源清单 31 个文件全部复验，测试前后未漂移；旧原策略、原设计封存未改。

运行解释器使用候选 QA 记录的既有 uv 环境：
/Users/bytedance/.cache/uv/environments-v2/b2d53c07a5e2321f/49580a0fa3b048c7/bin/python
默认系统 python3 缺 parquet 引擎，首次仅类型文件读取因 ImportError 中断；改用上述既有环境完整复验通过，没有安装软件。所有官方测试的结果写入只重定向到本审查目录，测试条件和候选文件没有修改。

复验命令：
上述 python -B mainline_winner_funding_review_v1/verify_v12_interface.py

## 关键接口确认

- 原真实 close/exit/alloc/transfer/noncash/demand/requests/reference/order/preflight/info/net/CP/no_fill/accrue/pay/refresh 方法对象保持继承。唯一新增许可为按固定新 MATURE SEED 后缀选择完整自然计划。
- CLOSE sync/prepare 一次；每枝重算原 D/K/U/X/T 和 floor/receiver/donor 排斥。没有截 donor、调序、联合优化或新目标。
- QuoteView 在 CLOSE 投影把 next session OPEN 报价映射为本晚 CLOSE，同时保留 next session dated fees/quantity/T+1。不消费次日真实 factor/行情/信号。
- OPEN 共同预测 prefix 使用 ConditionalEngine，所有 no_fill 强制 False；原真实强制退出、donor/buy no_fill 仅在选枝后执行。原实际 prefix 的现金/库存/H 只作为后验诊断，不重新选枝。
- H 来自共同阶段快照；OPEN 新完成的信息确认纳入，后验 bar 资格不参与。确认 proof 可追溯；M/stock/sector 为已冻 known，不要求 M=1。
- 每枝原 receiver 上限与 q_hat 分开。已真实测试 shadow CLOSE q_hat=0/bar_q=100，而 OPEN 可提交100时拒绝缺同量的 full，不借 shadow 字段临时补买。
- 已真实测试无H供给约束时，加入种子使 ADD 从 shadow300股降到full200股，正确因 ADD 下限退让。RESIDUAL不保量。
- 全部原 pending 保留供 preflight。资金退让明确 WAIT，原 identity/nav0/budget/phase 快照不改；原 attempt/stock/结构失败不伪装 WAIT，Q0 unknown 暂停及后续False取消保留。
- 真EVENT尝试即消费priority（即使nofill）、CP仅真实ADD消费；scratch不改账户状态。active/archive alias与全部状态回滚已测。
- 无绑定/无N原接口合成逐字段一致。真实执行无新quantity cap；原整数剩款保留。
- 分支完整安装，branch/book hash可独立重建。预测与最终实际数量差异单独记录及标注原nofill原因。

## 限制

本次没有运行任何真实历史账户，没有构建 Data，没有外网访问；CNINFO 403 步骤未接触。30N/31枝合成仅约1.89MB book的局部规模测试，不是93日实际内存/时间保证。父级 runner 应封死原源hash、显式限制93日至2025-01-20，原异常原子回滚后停止，不能自动更改参数/重跑。

实际账户账务、收益、11/6锚定损益、winner回吐、漏掉真实新主线、所有保存分支不挤出及撮合偏离，仍由实验后的独立审计负责。
