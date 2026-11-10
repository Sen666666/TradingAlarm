# TradingAlarm 已验证结果与反证

记录日期 2026-11-10。金额为人民币；初始资金为 1,200,000 元。全部为已观察历史的模拟研究，不是实盘业绩，不是样本外证明。不同终点、输入事实、引擎修正和执行假设的结果不得直接排名。

源根目录：`/Users/bytedance/Documents/Codex/2026-11-09/sector51_924_entry_review_v1/`。下文路径相对此根；小型原文快照在本交接的 `snapshots/20261109_sector51/`。

## 1 先把终点说清楚

- M7 原基准及修正 V11 的真实认证账户最长到 **2025-01-20，共 93 个交易日**。
- **没有完成到 2025-10-10 的证据**。原行情截止日期、计划目录名和实验 end 参数都不是已完成账户。
- M12 v1 只认证到 **2024-10-10，共 22 日**，不是 2025-10-10。
- M12 v2 恢复同一账户时因10/8 AVAILABILITY_EVENTS前缀不一致停止历史推进，usable_result=false，最后认证9/30。最新状态见 `RUNTIME_BLOCKER_UPDATE.md`；1/20目标未完成、未完成后审。
- 本次交接没有运行新回测，没有把任何未完成候选晋升为可用策略。

## 2 M1 到 M12 文件实数

以下均回查对应目录的 `RUN_STATUS.json`（`days`、`orders`、`last.day`、`last.NAV`），不是从目录名推断。未给出跨版本共同窗时只展示原账户事实。

| 目录 | 真实末日 | 日数 / 订单 | 末日 NAV 元 | 状态 |
|---|---|---:|---:|---|
| mainline_candidate_v1 | 2024-09-27 | 18 / 1472 | 1,320,196.3559986241500 | 9/30 的 002252 事件未准入，阻断 |
| mainline_candidate_v2_pending_quote_pause | 2024-09-30 | 19 / 1509 | 1,439,646.6815535028500 | 10/8 的 300870 事件未准入，阻断 |
| mainline_candidate_v3_core_reference | 2024-10-08 | 20 / 1351 | 1,543,879.5546299456500 | 本窗口完成 |
| mainline_candidate_v4_event_representatives | 2024-10-08 | 20 / 515 | 1,544,232.1578136950485 | 旧 UNKNOWN 供资分类有问题，保留旧结果 |
| mainline_candidate_v4_known_sector_fix_v2 | 2024-10-08 | 20 / 515 | 1,542,477.2881868895885 | 修正 M4，后续正确基准 |
| mainline_candidate_v5_expansion_competition | 2024-10-08 | 20 / 654 | 1,556,482.1562102814490 | 比修正 M4 多 14,004.87 元 |
| mainline_candidate_v6_mature_round_cap | 2024-10-08 | 20 / 652 | 1,562,897.4373657347085 | 比 M5 多 6,415.28 元 |
| mainline_candidate_v7_demand_capped | 2024-10-08 | 20 / 733 | 1,573,456.9155649536940 | 本窗收益 31.1214%，收盘最大回撤 1.0507% |
| mainline_candidate_v8_false_mainline_retirement_run_v1 | 2024-10-31 | 37 / 1499 | 1,381,908.9728156095195 | 本窗不支持替换 M7 |
| mainline_candidate_v9_persistent_stock_failure_run_v1 | 2024-11-06 | 41 / 1580 | 1,481,043.6413188901275 | 短窗增益小、回撤更差 |
| mainline_candidate_v10_positive_cp_initial_protection_run_v1 | 2024-11-06 | 41 / 1594 | 1,490,922.4000106376895 | 只支持短窗候选 |
| mainline_candidate_v11_structural_maturity_entry | 2024-10-08 | 20 / 581 | 1,545,444.6154552009400 | INVALID_IMPLEMENTATION，不用于假设评价 |
| mainline_candidate_v11_structural_maturity_entry_execution_fix_v2 | 2025-01-20 | 93 / 2906 | 1,297,829.9571357609705 | 已完成，独立审计通过 |
| mainline_candidate_v12_winner_funding_competition | 2024-10-10 | 22 / 664 | 1,469,827.6743768324175 | ATOMIC_BLOCK，仅启动段 |

M8、M9、M10各自从 M7 出发做独立消融，不是逐个叠加。M1—M7递进版本也不是相互独立的样本外证据。

## 3 长窗 M7 基准

来源：`mainline_m7_cash_batch_post_run_audit_v6/BLOCKER_READOUT.md`。

- 审计 13,723 项 PASS；93 日、3,596 单，终点 2025-01-20。
- NAV 1,275,326.0427500672225；现金 128,986.4827500672225；持仓市值 1,146,339.56；费用 28,881.8165199327775；130 只证券、75,265 股。
- 收益 6.2772%，最大收盘回撤 20.0919%。不是 10/8 短窗 31.1214% 的直接外推。
- 2025-01-21 因 `000728.SZ UNADMITTED_EQUITY_EVENT` 实际阻断。当前零持仓不等于终身未持有：此前有 4 单、3 个持仓日，不能走 Q0 从未持有豁免。
- 计划 2026-06-30 上限没有完成，后续 1—3 月公司行动没有因此自动准入。

## 4 明确不支持的方向

### M8 假主线退休

来源：`mainline_candidate_v8_false_mainline_retirement_run_v1/INDEPENDENT_READOUT.md`。

同窗至 10/31，收益 15.1591%，M7 为 20.8821%，少 68,676.67 元；最大收盘回撤 14.1172%，M7 为 13.1078%，更差 1.0094 个百分点。31 笔新退休释放 988,633.08 元，但现金增加没有带来经济改善。不得升级默认。

### M9 持续个股失败

来源：`mainline_candidate_v9_persistent_stock_failure_run_v1/INDEPENDENT_READOUT.md`。

10/31 比 M7 多 4,398.15 元，11/6 只余 1,488.33 元；最大回撤 13.3573% 对 13.1078%。不支持长期改善结论。

### M10 正 CP 初始仓保护

来源：`mainline_candidate_v10_positive_cp_initial_protection_run_v1/INDEPENDENT_READOUT.md`。

10/31 多 10,932.22 元、11/6 多 11,367.09 元；最大回撤 12.9289% 对 13.1078%，少 0.1789 个百分点。52 个 INITIAL lot 使用 90 次保护，真实提前退出 16 笔、10,300 股。增益主要由资金回收后常山获得更多 ADD，不是提前卖出常山。银之杰实际 OPEN 比锁存 CP 低 26.36%，所以保护线静态利润不等于可兑现利润。只作用 INITIAL，光伏集中问题未消失。

## 5 V11 实现修正与经济意义

来源：`mainline_v11_account_audit_v1/INDEPENDENT_READOUT.md`、`mainline_v11_account_audit_v2/INDEPENDENT_READOUT.md`。

旧版 NumPy 2.4.5 的 `numpy.bool` 被误判 UNKNOWN，CP 通道未运行：CREATED=0、UNKNOWN_GAP=5002、4992 条 CP_state 全为 −1。该结果标为 INVALID_IMPLEMENTATION，不能据此否定 F OR CP_state 假设。10/9 另受 605499 Q0 scope guard 阻断。

修正版至 1/20：

- 收益 8.1525% 对 M7 6.2772%，NAV 多 22,503.91 元。
- 最大收盘回撤 17.5259% 对 20.0919%；峰谷均为 10/8 至 1/13。
- 11/6 已领先 21,994.66 元；11/7—1/20 只少亏 509.26 元，不能称后半段修复。
- 后段费用少 3,224.07 元；加回费用后交易/估值损益反而差 2,714.81 元。
- 固定 62 个肥尾赢家捕获 57 个，实际合计少赚 25,378.46 元。
- 原 934 个负轮中参加 705 个，相同身份反而多亏 8,534.77 元。

支持的是少交易、少费用与少数赢家资金路径改善；不支持“入场更准确”或“假信号参与成本已降低”。

## 6 M12 启动段与当前现金修正版

来源：`mainline_v12_account_audit_v1/INDEPENDENT_READOUT.md`、`mainline_candidate_v12_winner_funding_competition/RUN_STATUS.json`。

同窗 22 日：

- NAV 1,469,827.67 对 M7 1,426,110.94，多 43,716.74 元；收益 22.49% 对 18.84%。
- 最大收盘回撤 8.70% 对 9.36%。
- 差额分解：已平净利多 6,949.88 元、未平标记多 36,766.85 元，不能统称已兑现。
- 9/24 原 MATURE 28/28 同日捕获；启动固定 222 轮捕获 151；固定 19 个强赢家捕获 17，仍漏今世缘/古井贡酒，其原同窗合计盈利 9,155.20 元。
- 水井坊 10/8—10/10 额外回吐 5,423.19 元。健康赢家资金保护不是未来盈利保证。
- 10/11 因 688200 现金事件未准入而原子阻断。两账户此前都未成交/持有该股，保留候选票仍使其处在事实预检范围内。
- 没有覆盖光伏 10/23—29、11/6 后、11/7 起的 954 轮和 12/5 机器人。这些不是零结果，而是尚未检验。

M12 v2 只补经过独立审阅、绑定哈希的 688200.SH / 2024-10-11 / LOCAL_DISTRIBUTION_007 事实，并增加无损 gzip 导出及同 manifest 检查点恢复。经济方法保持不变。`mainline_v12_account_audit_v2` 的 PREPARED_SYNTHETIC_ONLY 和 28 项合成断言，不是新真实账户后审 PASS。见运行快照和研究负责人贡献。

## 7 历史成果仍保留但不应冒充当前主线

主工程 `docs/ALGORITHM_*.md`、`docs/ALGORITHM_*.txt` 保存 E0/R/R1、B4、B5、B5-G1、RC1、E0-NR1、ACT20_BREAK、SFW3_RS_1、S-AMT1 等定义。`research_rounds/` 保存每轮冻结、代码、数据引用、结果、图和失败。

例如 10/28 CP1、S/F/W、PH1、创新药本池恢复与科技策略均有真实有限对照，但范围多为 407 科技股/48 创新药，而非当前 51 行业主线。不可只摘其中 378% 或 657% 的单路径收益宣称项目完成。完整各轮目录与入口见 `RESEARCH_DIRECTORY_INDEX.csv`，最新主线以本交接及 11/09 原文件为准。

## 8 共同限制

当前存续池、当前行业/市值筛选与后修订行情存在选样及信息偏差。OPEN±5bp 是条件执行/成本代理，不是逐笔盘口或涨跌停排队认证。NET80 是研究股息约定。费用与滑点已经进入账户，不重复扣减。普通交易、尾部、未结估值、现金暴露必须一起读；修好会计和通过前缀不能证明预测或经济优势。
