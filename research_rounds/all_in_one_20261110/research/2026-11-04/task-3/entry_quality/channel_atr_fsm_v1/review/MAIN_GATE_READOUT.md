限定实现 gate：**PASS_STATIC_MAIN_AND_FIVE_REAL_SMOKE_WITH_LIMITS**。可据此使用已绑定的 engine/runner/freeze 运行既定纯市场信号批次；无账户、数量、费用、成交或经济有效性许可。

最终 source：engine `ad281eabf73045eba4f28456dc4e13025bc8f8dc37b971393379fcbdc9bab747`，runner `3df669581094f7dc3ed83312ff05cc3ece84c3bb779961c05b748063922dbc67`，freeze `aa108a5d27cfec43951911b5e225b9a8b6391f45522f0a4b9601eca6fb246331`。最终运行是 `smoke_v1`，不是旧 `smoke_main_v1`。旧版第五股为605111；最终固定第五股为300623，审查未混用。

静审发现并已修复两处接线：已知 C 的 frontier 不再被指标 ready 门遗忘，断暖期间跨格记录 SKIPPED/消费格子但不发券、不自动 mature；配对先以已知 C/I 检旧线，之后才因 H/L 未知删失。pre-fix engine、最初审查和旧 smoke 均保留。

审查没有导入/执行 engine，没有另跑指标、FSM 或账户。只读取最终已存结果及原源：五股25个 source SHA 核同；4333 展示行的 START/SEEN/ADVANCE 基本不变量核同；独算五个真实 generation 的 prior20 H、首个固定 ATR 整数格区间、冻结 A/S 和首次退出条件。

| 股票 | SEEN | 首推进 | 首个格 | 该 gen 首退出 |
|---|---|---|---:|---|
| 盈新000620 | 2022-01-07 | 2022-01-10 | 2 | 2022-01-18，旧线 |
| 海002583 | 2024-09-20 | 2024-09-23 | 3 | 2024-11-04，旧线 |
| 银300085 | 2024-09-19 | 2024-09-20 | 6 | 2024-10-10，新ATR proposal已触线 |
| 金海通603061 | 2025-12-22 | 2026-01-05 | 1 | 2026-02-24，旧线 |
| 捷捷微电300623 | 2026-01-05 | 2026-01-09 | 1 | 2026-02-02，旧线 |

银之杰8月启动在当前展示窗之前，不能因9月才展示就伪造9月新 START。盈新、海等这些退出均是市场 shadow 信号，不是候选实际成交，也不能拼原后续层计算收益。

291个原 raw CP 锚=290个 paired shadow+1个 entry quote unknown。全部580个 paired 分支核了共同初始 ATR 分母、20日前退出/不足20的后续风险为 NULL，以及零个 post20 观察时回撤不得填0。两保护影子共享初始P0与原I上下文；主 E0 generation 与配对上下文分开。ATR 只是此处标准化单位，不是实际风险预算或可成交亏损界。

限制：展示4333行没有 same-CLOSE exit+restart、unready START 或 SKIPPED_DATA_UNREADY 的实际发生行；这些分支只有静态审查，不能叫真实场景测试通过。600345 的未知 flag 旧单行证据已读，最终 gate 不据此宣称所有 UNKNOWN/缺行已验证。完整市场日历缺行检查仍 NOT_VERIFIED。未独立复算整个前缀状态、全部配对保护轨迹或未来强势十分位汇总；这些不在本 gate 范围。
