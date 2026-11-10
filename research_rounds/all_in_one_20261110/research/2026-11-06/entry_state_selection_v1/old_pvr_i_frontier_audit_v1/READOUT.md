# 旧 PVR 连续消费者 I 内首 / 重复首仓核验

统一管理终点：2026-05-15。只读取旧账，不运行消费者、指标或新交易。冻结分组见 FROZEN_PROTOCOL.json。

## 全部完整回合结果（元）
- 2022_full：762 回合，已闭 762，未闭 0，胜率 21.00%，旧 proxy 净额 -341,584.41，跨年闭仓 70。
- 2024_full：553 回合，已闭 553，未闭 0，胜率 25.14%，旧 proxy 净额 -122,745.97，跨年闭仓 80。
- 2024_Sep_Dec：294 回合，已闭 294，未闭 0，胜率 29.25%，旧 proxy 净额 -25,120.11，跨年闭仓 75。

## 口径与边界
- 0→0 按实际成交股数重建，逐层买入净现金、卖出分配、拆股股数、红利应计与原 layer 对齐；不是把 mobile 退出当整只股票退出。
- I 从原始 facts 全前史同 source segment 的已观测 0→1 起算；market_i_buy_ordinal 和 market_cp_ordinal 统计市场事件，actual_round_ordinal_in_i 单独统计已成交股票完整回合。
- NON_I_BUY_DAY 与 NO_CP_RECEIPT_DAY 各自独立；add 的原 canonical receipt ID 已逐一对齐。只读原 CP receipts union，不重新生成 receipt。
- FIRST_ACTUAL_ROUND_IN_I 只说明 2022-01-01 账户成立后的首次实际回合，不宣称此前市场没有信号或其他账户没交易。
- 2022 全年和 2024 全年、2024-09 至 12 均用 2026-05-15 管理终点，2022 不再限定当年末已闭。
- round_pnl 是旧账买卖净现金 + 应计红利，不是已到账现金。241 项原红利应计事件的 paid_at 均未认证；原账含权益假设、分数股向下取整 proxy、非按比例定增 proxy。
- 原始持有日 facts 缺行/无效价另列，不冒充已证明逐日 raw-mark 可得，也不把未知补为 0。此次没有新 NET80 同等独立权益、停复牌、真实可成交性全审计，因此所有回合 financial_status 均为 OLD_PROXY_ONLY_NOT_NET80_CERTIFIED。
- 原账户是未来筛定 1709 标的固定池，非 PIT。所有胜率/净额仅是已消费历史描述，不是筛选后新账或因果收益。

## 文件
- ALL_PVR_ROUNDS.csv：完整回合、市场 I/CP 序号、实际回合序号、首层种类/真实原因、跨年和未知字段。
- GROUPED_OUTCOMES.csv：预先冻结的全部分层；未闭和未知独立。
- ROUND_TRADE_ALLOCATIONS.csv / LAYER_LEDGER_RECONCILIATION.csv：每一笔交易到 layer / 回合的账桥。
- CORPORATE_ACTION_ALLOCATIONS.csv / SPLIT_LAYER_ALLOCATIONS.csv：原权益应计与数量核对，非独立权益真实性认证。
- MARKET_I_SIGNAL_HISTORY.csv：涉及 I 的完整市场事件序列，包含窗口前史。
- CHRONOLOGICAL_SAMPLES.csv：每类按时间选首例，未按金额选例。
- SOURCE_SHA256.json / SUMMARY_QA.json：可复核源 hash 与 QA。
