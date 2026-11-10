# 更正：CORE 已有上游 I 线间接止损

先前只沿 `joint_v3.py` 的 CORE 分支阅读是不完整的。该分支没有再次直接比较价格，**不代表 CORE 的 I 线没有对应止损动作**。真实 facts 生成链已在上游比较旧 I 线，并把结果传给全股退出。旧封版文件保留，本件与同名 JSON 为追加更正，优先于旧报告中任何“CORE参考线无对应价格止损”的解释。

完整原链如下，源码 SHA 与旧 freeze 比对结果见 `UPSTREAM_I_STOP_CORRECTION.json`，本次未调用 derive/project、模型、Account或回测：

1. `native-I-cache-interface-20261031/cache.py:27–32`：`project(e,base,g,'G1_I')` 的 `target/floor` 原样成为 `i_target/i_floor`。
2. `b5-g1-20261025/code/policies_g1.py:20–24`：active 时先判断 `not base.target` 或 **当日 adjusted CLOSE≤旧 floor**；命中则 active=False、exited=1。未命中才将 floor ratchet 到新的 base.floor。`34` 输出 target=0，并在退出当日保留旧退出线。
3. 同文件 `30` 的 `not exited` 禁止该次退出在同一观察立即重新入场；G1_I 的 `use_x=False`，不是另加 grade 冷状态退出。
4. 实际完整历史 cache 由 `universe-cp1-inputs-20261031/prepare.py:27` 调用同一个 N.derive；已复用 case 分支的来源见 `case-stock-cp1-warmup-20261031/generate.py:8,41`。`loader_2024.py:41–50` 装入该既有 facts；当前 `load_inputs.py:17` 复用该 loader，不重新生成信号。
5. `actual-risk-recovery-20261027/code/engine.py:24–30` 的 facts.row/floor 读取已存事实及 I floor。`joint_v3.py:225–229` 看见 `i_target=False` 时发出全部真实 live layers 的 `I_structure_exit`；次合法 OPEN 按原实际成交约束执行。

`joint_v3.py:231–234` 更新 `last_core_line` 后 continue，表示不在这里再复制上游判断。普通 active CLOSE 中，该字段按同一 facts.floor('I') 更新；下一 OPEN 使用最后决策已知值。不能额外对“当天 ratchet 后的新线”再做同一 CLOSE 比较，那会比原“旧线先检查、后上移”的合同更紧。间接止损依然不是成交保证，T+1、OPEN跳空、无窗口、容量和pending约束仍在。

对新统一状态卡的影响：保留这条原间接止损及其旧线/ratchet/同观察不重入时钟，不得以“填补 CORE 没有止损”为由重复加一条 I 线 stop。CORE/mobile 的其余差异仍可审查，例如 mobile 有独立旧 CP 线、首次 sizing 和资金授权不同；这次更正不自动证明二者所有退出相同。

## 盈新时钟的附带更正

原完整链已提供一个实际佐证，同时揭示“订单创建日”不能倒推每一层的最终触发日：

| CLOSE | adjusted CLOSE | I target | I floor / CORE last_core_line | 原实际状态 |
|---|---:|---:|---:|---|
| 2022-01-26 | 4.487331764019242 | 1 | 3.4053609072125717 | 无退出pending |
| 2022-01-27 | 4.043154254382819 | 1 | 3.4053609072125717 | 113/122先触发CP退出，68 CORE尚无exit reason |
| 2022-01-28 | 3.6445334124014144 | 1 | 3.4053609072125717 | CP退出仍pending，CORE仍未触发I退出 |
| 2022-02-07 | 3.280080071161273 | 0 | 退出日保留3.4053609072125717 | 跌破旧I线，68及其余层升级为I_structure_exit |
| 2022-02-08 OPEN | — | — | — | 原实际卖出 |

旧 `execution_code/READOUT.md` 的“其余为01-27 CLOSE触发I”应改读为：**01-27先有后两mobile层CP退出，02-07才有CORE/I全股退出，02-08实际卖出**。原trade中的 `order_created_at=01-27` 沿用同股已存在的exit order；`pilot.py:104–115` 会扩充该exit目标，`J:225–229` 会更新各层最终reason，不能把最终reason和首次order_created_at拼成每层的触发日期。

本更正不改变原现金流、损失、股数、银之杰实际先卖后买的证据，也不修改原报告/账/源。没有新增收益推断或反事实。
