# 个股 prior63 价格新高：源码语义与旧研究排重

本轮只读源码和旧研究，不计算新条件命中、指标或收益。结论是：原 I/G1 的 S21/S63/fresh_up 不等于滚动63价格新高；但 fresh CP1 已有严格的新 frontier 约束。在持续未重置的 frontier-run 中，新增63新高条件可能逻辑冗余，真正新增的信息主要来自重置前旧高仍留在63观察窗口的情形。尚未证明这部分有足够规模或能改善账户。

这里把“price high”精确区分为**此前63个同一可比信号价域 close 的最大值**，排除当日；这正是旧 three-layer 的 `high63` 字段。此前63根 OHLC `high` 的最高值是另一条件，旧55突破研究使用后者。均不是63收益正号、均线、净推进R或macro恢复新高。本报告没有替候选实施或选定窗口/价域。

| 原有语义 | 实际定义与源码 | 与 prior63 close 高关系 |
|---|---|---|
| S21/S63 | B4事件结构状态；h进入√h波动位移阈值。方向确认后将该结构running high/low重锚当前close，`model.py:195–256` | 不是过去21/63观察rolling max，状态正向可在更早高点以下 |
| G1 fresh_up | 新原E0上event，或新S21/S63上确认，或S21已确认上结构的running extreme再创新高，三者OR，`grade.py:23–29` | 其中“新高”也是当前结构极值，不是固定63窗；另外两支更非63新高 |
| I新建/恢复 | shadow有效、grade≥2，且原entered或fresh；I有效后的维持沿原结构/floor，`policies_g1.py:16–34` | 不要求每次当前C创63高，也不要求当前grade持续暖 |
| 新mobile | 当日原fresh股票CP1 + continuing Q，再核ACT和资金；continuing不重要求fresh I，`joint_v3.py:243–255` | 有新的价格/量信用证据，并非无方向；仍不等于跨重置的63新高 |
| 原CP1 | `fresh = logC − frontier > 0`，同时displacement与credit≥√5×冻结z；量以相对前21 amount背景的软信用权重进入，`CP1/model.py:20–24,35–49` | 新的当前frontier进展，不是硬q≥2或固定63高；63在此用于此前收益尺度 |

CP1 的关键比较范围：源码只在source变化、unprepared、输入valid失效、phaseNone/start、原down事件或SEEK lower_anchor等分支清空/降低frontier。股票CP1_input的 `e0_valid` 在此管线实际绑定股票 I target，不能把字段名泛称为原始E0 target。普通UP回调不降低frontier；receipt_consumed虽然清anchor/credit并移至当前C，但它刚创出的frontier也等于当前C，并未降低。

因此可作**有条件逻辑蕴含**：若此前63个原始价格观察全部位于最近一次会清空/降低frontier的reset之后，且采用同源、同观察集合与原比较精度，则当日fresh CP1意味着当前C超过该run此前所有close，自然也超过prior63 close max。不能只凭“同source segment”“同E0/I episode”或“距离最近receipt超过63”声称该前提成立；SEEK lower_anchor等能在这些大标签内部重置，receipt本身又不降低frontier。

非冗余区域主要是重置后局部推进：63窗还含旧run的高点，而新的local CP1已经满足。因此这项备选针对的是“新局部进展与重置前背景高点的关系”，不是为持续同一run补上本来没有的新高证据。反向不成立：创prior63高并不自动满足原CP1的ready/valid、位移和信用门。只靠旧高滚出窗口也不能制造fresh CP1；保留其合取很重要。这里没有统计这些情形的现实占比。

“保留小probe、成熟confirmed才接受原fresh CP1且股票63高”还需区分**新订单**与**既有批次迁池**。原mobile新请求已必须fresh股票CP1，但行业确认可调用sector-wide migrate，将该行业同attempt的既有probe lots迁入confirmed；迁池并不逐股票检查新CP1或stock63高。若未来定义覆盖全部成熟资本，仅改新订单条件会漏过迁池。这里只指出现有接口语义，没有设计新合同或改路由。

旧研究排重已找到三类近邻：

1. **明确63 close 高扩张家族已存在。** `three-layer-prototype-20261024/model.py:21,95` 和 `temperature-regime-comparison-20261025/code/three_layer_v1.py:21,95` 使用 `close.shift().rolling(63).max()`；扩张还合取hot、daily_z≥2及可选q≥2。它不是原CP1，也不是当前PVR mature-confirmed合同。其真实资产/年代/执行范围由pool分工审阅，不能称“63高从未研究过”。
2. **明确55 OHLC high +量确认已实际研究。** `stock_signal_data.py:39` 取前55根high最大值；`a_stock_campaign_signals.py:33,48–51,59–71` 的volume分支是信号日真实股数成交量大于此前20个正量观察均值，次合格open执行、无加仓，保留4ATR/MA200退出；其MA分支与量分支不能混。该研究有独立campaign结果，但不是当前1709股native三年同资金账户，更不是只成熟confirmed加门。不能把55改63当成原理从未检验，也不能把独立campaign R均值当账户回报。广泛旧引擎/已运行范围由pool单独收口。
3. **股票proof +共用小probe/成熟迁池设计已存在。** 旧 `temporal-frontier-design-only/DESIGN_REVIEW.txt` 的T1-L用原attempt新frontier增量的分散度/latch，再需当前fresh CP1，初试共用probe、证明后股票级迁池；该文件明确只有设计/源码审，未计算候选或回测。它是attempt-frontier proof，不是rolling63价格高。其“重置后可在旧高以下重新证明”的成本已公开，恰是本次63背景可能新增的区别。

在本次检索的两旧研究根及读取的当前native链中，**未找到已执行的完全同义组合**：原小probe机制保留，成熟confirmed新资金及迁池逐股票要求原fresh CP1且current C>prior63 close max，完整2022–24与strong共用原账比较。这是有界检索结论，不是全仓库不存在的证明，也不是新候选已获授权。

当前只确认语义不同及条件冗余关系。是否主要损耗发生在该跨reset旧高区域、是否会伤新趋势与强窗固定赢家、是否能在不挤死probe的条件下兑现成熟资金，均未计算、未验证。下一机制须与loss的单一核心建议一起主审；不叠均线、不预设该备选有用，未运行新gate或绩效。

独立源码审确认了上述frontier-run蕴含及其reset前提；实际价格高条件的命中、反事实账户和信号表现不在本轮。来源文件及SHA见 `stock_prior63_high_source_review_v1/SOURCE_MANIFEST.json`。
