# V5 主卡独立逻辑审查

已亲读 V5_EXECUTION_CONTRACT.md。核心合同一致：CORE 无 CP 入口保留；cap/approved Q/F 分开；同 up 一个 probe parent；真实 fill 才消耗；零 fill 终局对账后可续；partial 只追固定余量；历史合格持有链可跨 up；market mature 与执行 complete 分开。未运行候选、账户或订单路径，也未重算主卡案例数量。

首次读到的伪代码仍需以下执行闭合，已向主线程逐项报告：

1. `on_close` 显式挡 `context.pending_buy` 和尚未对账 replace，不只挡本系统能找到的 parent/cancel/exit；旧单或外来单不应因未登记 parent 被漏锁。
2. `on_terminal_ack/status_reconcile` 也要判断 complete，并在首次 F==Q、全部终局且累计成交对账时锁存 `complete_known_at`。仅在 on_fill 更新不够：最后 fill 先到、最后 ACK 后到时可能永远无完成钟；反复状态查询也不能把已知钟不断推迟。
3. 若 F 或 F+可能成交 leaves 超 Q，先持久记录真实执行、标超额/未知并阻止新风险，不截断 F、不靠 assert 让真实成交从账里消失。assert 可报警，不能代替状态处理。
4. `original_parent_still_valid` 明指当前 up/源可比/保护/purpose 权限：ADD 续单需当前 mature；probe 余量续单不需要新的 CP/I，且不被第一次 fill 后 held/core_epoch 拒掉。否则“可以续单”会被原新单 freshness 门重新锁死。

这些是接口完整性，未要求新增价格、收益、1R、资金或冷却门。其余关键防重放、单调 up.used、旧单回调归属、部分目标优先、完成后新 CP、legacy 微仓不得追认及实际 flat/存量 lineage 均已明确。

“probe 先保护退出、ADD仍健康时不自动继承”的代价已由主线程公开；当前逻辑不把它悄悄当作已解决。完整生产实现、真实 ACK 可用性、approved-target 的批准接口和经济有效性仍未验证。旧账 cap/成交只能作条件案，不能代替新 target/ACK 反馈。
