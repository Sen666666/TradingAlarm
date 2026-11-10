# 2024-09-24 资格数据可用性收口

只读取既有名单、当前 THS 分类、市值快照和 90 条原行业系列，没有运行新模型、资格函数或账户，没有使用申万替换 THS。

**关键结论：行业数据不只覆盖旧 1,709 池，但保留原 S0 的当前市值硬门时，原池外没有已知新增通过者。** canonical 5,517 中有 5,499 只能精确连接当前 THS 行业及已有行业历史源；它们的同价域个股 E0/I/G1 仍须由统一 qfq stocksignals 产物给出，不能移植旧价格坐标的状态。

## 真实文件规模与行业母体

| 来源 | 实数与含义 |
|---|---|
| `inputs-v2/metadata.json` | 1,711 股票键；每行 7 字段：name、industry、sector_id、code、par_value、par_value_basis、native |
| `inputs-v2/selection.json` | 1,711 lines，即 1,709 已知当前市值合格 + 2 市值未知 |
| `prepared-v2/manifest.json` | 1,801 series = 1,711 个股 + 90 THS 行业，非全 5,576 个股状态库 |
| `inputs-v2/roster-dispositions.json` | 5,576 原始当前股票，1,709 selected、3,865 当前市值未超过门槛、2 unknown_cap_retained |
| `current-stock-master.industry-resolved.csv` | 全 5,576 当前股票；5,575 有唯一 THS 行业，90 行业；000016.SZ 无行业 |

metadata 是筛后表，不能因它只有 1,711 行就误说池外没有 THS map。完整分类源码路径为 `a-share-selection-e0-20261024/code/build_inputs.py:12` 的 OLD=`../current-pool-20261022`；`repair_classification.py:13` 读 OLD/audit-snapshot/current-stock-master.industry-resolved.csv，`14—29` 用 BlockUpdate/StockLink 和非空 tree 边复核，`34/40/44` 写 selection、全 roster 与 metadata。该分类是 2026-10-22 快照，非 2024 历史成员。

canonical 5,517 exact ID join：

- 5,500 在当前 5,576 名单，17 不在。
- 5,499 有当前 THS map，并且所属行业都有已有 prepared 历史源；另缺 17 个不在当前名单者与 000016。
- 1,683 在筛后 metadata 1,711；这是含两个当前市值未知证券的覆盖，不等于 1,683 个合法买入者。
- 原 1,709 池外共有 3,836；其中 **3,818 有当前 THS map 与行业历史源**。这是数据比较范围上界，非资格通过数。

本次源中实际核出的是 1,709/1,711；其它“1,739”旧子池若被提及，也不能视为全部原始证券。原 raw 当前名单是 5,576，指定 canonical 是 5,517，三者须分开。

## 当前市值硬门不能悄悄撤销

原 active 路径的静态调用链：No60 `adapter.py` 只替预算 `Contract.request`；BASELINE planning 仍调用 `BP.A.eligibility(...,'S0')`。LR adapter 的 eligibility 是 memo 包装，保存 `_elig`。BP 经 `pilot.py → pvr-act experiment → tech-finite-compound/common.py` 导入 `rs-h1-execution-20261025/code/sector_stock_admission.py`。该文件 `203` 仍为：

```python
'cap_above_10bn': None if cap is None else cap > 10_000_000_000
```

同时 `207` 检查 stock rank ready/fresh，`211/213` 检查当日 sector observation 与 sector rank ready/fresh，`214—215` 检查 sector_up。不能以较早同名 a-share-selection 文件代替这版 active freshness 规则。上述是源码静态核查，未创建运行器或账户。

| canonical 范围 | 当前 cap>100亿元 | 当前已知≤门 | 当前 cap 未知 | 不在当前名单 |
|---|---:|---:|---:|---:|
| 全 5,517 | 1,681 | 3,817 | 2 | 17 |
| 原 1,709 池外 3,836 | **0** | 3,817 | 2 | 17 |

两个未知为 000016.SZ、002731.SZ；前者行业也未知，后者当前 THS 行业已知。因此池外 3,818 个有行业数据者包含 3,817 个 cap 已知失败和 1 个 cap 未知。

市值实际 observed_at 为 2026-10-24，selection observed_at=2026-10-24T21:56:29+08:00，roster_asof=2026-10-22。没有据此取得 2024-09-24 历史 cap。若以后研究全池不带该门的信号比较，应明确是不同资格设定，不能把排名池扩张称原 S0 新增可买。

## 90 个 THS 行业现存状态与时钟

已逐行业读取旧 manifest 指定的 signal/events/states 及原 native E0 sector facts，90/90 文件 SHA 与旧 manifest 一致；固定日四种表均 90/90 精确有行。

- native E0 `e0_ready`：90 已知就绪；`e0_target`：87 为 1、3 为 0。
- prepared state 的个体 `rs`：90 非空。固定日 participation target 与 native E0 target 数值相同，但它们仍是不同状态定义，不能只凭同名 target 合并。
- 示例半导体 URFI881121 原信号 close=5167.125，来源 `ths-index-history-9603-20261018/canonical/URFI881121.csv`；native E0 ready=1、target=1、floor=4955.848。它不是申万指数。

原行业 native 事实字段：close、segment_id、e0_ready、e0_target、e0_floor、factor、raw_close。原个股 facts 另外有 i_target、i_floor、i_buy、g_grade、g_fresh_up、g_acute_down、g_ready。旧原个股 facts 的身份范围是 1,709，价格来自旧企业行为 bridge；prepared 1,711 个股还存 participation/个体 RS，不等于全 5,517 同价域 G1/I 库。

### 当前 `facts.packet(at,'I')` 实际接线

已补充静态接口核查，未调用 packet 或建立模型。`actual-risk-recovery-20261027/code/engine.py:31—47` 的 I packet **只替个股**：个股 trend_up 置为 `r.i_target`；初始 buy_allowed 再与精确当日 `i_buy` 相与。最后直接返回 `inputs.sectors`，没有把行业改为 I_target。

行业来自 `mainline-I-quarter…/adapter.py:62—63` 注入 bundle 的 `e0_ready/e0_target`；active `rs-h1-execution…/current_pool_bridge.py:342—354` 将其构造为 Sector.trend_up。因此原 sector_up 在这条 active 线上是 **native 行业 E0_target**，并非行业 G1/I_target。但上面的 87 只是单个字段计数，不能叫 87 行业 S0 pass：还要满足行业 observation 当日、rank ready/fresh 等条件。

共同 ready 是同桥 `357—363` 的股票 E0 ready AND 行业 E0 ready，未知保留；个股持有许可看 I_target，不把 G1 grade 单独当 hold。`joint_v3.py:218` 的 continuing MOBILE 路径将 buy_allowed 换回 market_buyable，从而撤去当日 i_buy 的要求；I_target、sector/common/cap/rank 其它检查仍保留。这与首次入口不可混用。

原 rank 从 `_h1_cache` 的精确 session_date/series_id 取得，`Rank(score, clock.decision_at, clock.decision_at)`；不是 prepared.states.rs。行业 trend 的观察时钟另外由 `_last()` 给出，runtime manifest 中 90 行业 close_available_time 全为 15:05，原决策阶段为 15:10（中国时间）。数据存在、某字段向上和整套资格通过是三件事。

## 原资格依赖字段的可得/缺失

| 所需数据 | 现存证据 | 当前不能声称 |
|---|---|---|
| 当前 THS sector ID | full resolved roster，canonical 5,499 exact join | 历史 PIT 行业归属或当年成员 |
| sector_up 与行业 ready | 90 条原 THS native E0 facts，固定日均有行 | 缺字段可用申万/别的行业替代 |
| 个股 hold/I target、i_buy、G1 | 旧 1,709 facts 有字段；新 canonical qfq 同价域结果由结构线另行输出 | 把旧 I/G1 原样移到不同复权价格，或声称池外已具新资格 |
| stock/sector rank ready、fresh | 原个体 RS 及数据 observation clock 已保存；active Rank.read 要求当日 | 旧 H1 是全 5,517 的同池排名。H1 依赖股票母体，旧缓存不能不变挪用 |
| common_ready、观测/源有效性 | 原 mask、segment 与现有状态字段；本线未算新共同 gate | 只看非空价格就等于模型 ready |
| market buy_allowed | 旧 market-rules 有代理版本；`build_market.py:45` 来源名就是 `A_availability_no_historical_ST_delisting_tag` | 完整历史 ST、停牌、退市、盘口或可成交认证 |
| 公司 cap>100亿元 | 2026-10-24 当前快照、严格 known/unknown 分开 | 2024 历史市值或自动取消原硬门 |

对上一版桥接描述作精确更正：较早 a-share-selection 的 bridge 使用个体 RS/原 observation time；**active rs-h1 bridge** 的 `_last():301—321` 保留真实 trend observation time，但 `331—347` 的 rank 使用当日 H1 矩阵，并盖当日 decision clock。不能把早版的 raw-RS/last-at 说明当 active rank 数据流；sector observation freshness 是独立检查。`state_frame:224—236` 的旧个体 RS 不是 H1 最终跨池分位。

market_buyable 继承 `rs-h1-execution…/history_runner.py:164—179`：只读 source availability、venue identity 与 availability_versions，未知保留；没有从当日 H/L/V 推成真实可买状态。`FastMarket.quote:41—44` 委托 `FrozenMarket.quotes:224—242` 使用最新已知 raw mark、quantity、fees。后续真实执行代理是另一阶段，不能把该 decision quote 当成交证明。

结论范围：在不改变数据集/分类假设时，可为最多 5,499 只准备当前 THS map + 原行业源下的统一价格资格**数据比较**，池外最多 3,818 有这两类资料；真实同价域个股状态和共同 gate 未在本审计中生成。严格保原当前 cap 门，池外已知新增通过数为 0。当前快照、历史 ST/停牌与股票价格域差异必须继续披露。

文件入口：`AUDIT_RECEIPT.json`、`CANONICAL5517_MAP_CAP_DATA_AVAILABILITY.csv/json`、`ALL90_THS_SECTOR_FIXED_DAY_SOURCE_ROWS.json`、`FIXED_DAY_SECTOR_STATE_SEMANTICS.json`、`CURRENT_PACKET_I_INTERFACE_TRACE.json`。接口补充前的报告与 seal 保存在 `prior_before_packet_trace/`。全部为只读资料审计；0 新模型、0 资格函数调用、0 账户、0 网络。
