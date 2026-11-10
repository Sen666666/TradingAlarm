# A：原 MOBILE 峰值回撤／有效 CP 冻结尺度扫描

**海能达仅 k=2 在11-01早于原CP请求；k=3/4均11-04同原请求。太保、人保部分早层9月就有警报，不能把这些警报等同于只避开10月回吐。** 固定六股14个原MOBILE层，209层日；无新账户、反事实成交、收益或资金路径，未改策略。

## 口径与真实尺度

主条件严格 `log(H_(layer,t−1)/C_t)>k·s_activeCP`，只看 k=2/3/4。H只用该层**实际首次fill后、截至前一有效CLOSE**见到的最高调整收盘；不含当日、不含买入前、不用日内high。首持日没有先前已持收盘，标 NOT READY，不触发。全程在原连续可比调整价域，raw H用当日factor转为当前交易单位展示。

原CP源 `continuous-protection-lines-20261028/code/model.py:44–50`：先以旧冻结scale计算 `candidate=C·exp(−sqrt(21)·scale)`，保存为 `q.scale=used_scale`，随后才将当日 `q.z` 写到 next_scale。`cp1-evidence-trace-20261031/trace.py:55` 的 canonical `original_scale=float(q.scale)`。扫描已逐控制收据核 `q.scale==receipt.original_scale` 和 candidate完全相等，**没用 next_scale、当前s63 或当天后来新CP替代**。

入口 `max(I,CP)` I先；持有更新 `max(old,I)` 再 `max(old,CP)`。原Python max等值保首项：相同线值维持旧来源，不让后来同值I/CP冲掉它。扫描以已保存原层old/post-CLOSE floor注释实际抬线来源，未重演新保护状态机；当前条件只用旧线来源，当天抬线只影响下一次旧线。I主导且没有唯一CP冻结尺度时保留 UNKNOWN，不能借当前波动率补齐。

209层日中174可判；14个首持日无prior峰；另21日已有prior峰但I主导。按原因计，I主导共24日，其中3日与首持日重叠。这里的UNKNOWN不是“未触发”的证据。原请求当日及pending至真实fill前均在原持有范围；同CLOSE命中记tie，不算提前。

## 每层首次命中日

| 股票／原MOBILE层 | k=2 | k=3 | k=4 | 原CP请求CLOSE |
|---|---|---|---|---|
| 太保601601／1904 | **09-09** | **09-10** | **09-12** | 10-09 |
| 太保／1914、1931 | 10-09 | 10-09 | 10-09 | 10-09 |
| 中信建投601066／1916、1958 | 10-10 | 10-10 | 10-10 | 10-10 |
| 中金601995／1915 | 10-09 | 10-09 | 10-09 | 10-09 |
| 人保601319／1897 | **09-04** | **09-11** | 10-09 | 10-09 |
| 人保／1911 | **09-11** | **09-12** | 10-09 | 10-09 |
| 人保／1952 | 10-09 | 10-09 | 10-09 | 10-09 |
| 人寿601628／1893、1907、1930 | 10-09 | 10-09 | 10-09 | 10-09 |
| 海能达002583／2017、2039 | **11-01** | 11-04 | 11-04 | 11-04 |

日期均2024年。粗体只是严格早于原请求，**不是收益改善标签**。每层峰、线和尺度分别计算，不能把早层警报当成当时尚未拥有／尚无prior峰的新层也应退出。人保1884是CORE，未纳入此MOBILE候选。

## 海能达全部警报日

两个原MOBILE层2017/2039在下列日期的值相同，原持有期10月没有更早命中；没有遗漏只因“看起来会伤赢家”的警报。

| 日期 | raw C | Hprior raw | oldfloor raw | 控制尺度 s | log(H/C) | 命中 |
|---|---:|---:|---:|---:|---:|---|
| 11-01 | 25.38 | 28.20 | 23.6376606784 | 0.0385112561415 | 0.105360515658 | 仅k2；早于原请求 |
| 11-04 | 22.84 | 28.20 | 23.6376606784 | 0.0385112561415 | 0.210808593156 | k2/3/4；同原请求 |

旧线adjusted132.84202755479672来自10-31 receipt `4b4720f2dac26ab8f8693a4de18086b8f524a780c55df860c560e744285143d2`；原尺度冻结在10-29。不是11-01新取的滚动尺度。原CP请求是11-04 CLOSE，11-05原代理售出；本扫描只说k2可于11-01 CLOSE新增请求，下一市场OPEN只是最早调度，不是假定成交。这里提供全部警报，不依据未来收益判“误触/正确”。

## 太保早期警报的原数

1904层9月三个首触均由9-06 receipt `56258cf3d0de80173b817ab05fcb4624448a8c034c8677c3e0ed1e4b2473e983` 控制旧线：s=0.011766728430638815，冻结8-30，oldfloor raw29.3632134616。Hprior是9-06已见raw30.99。

| k首触 | C raw | log(H/C) | 回撤／当时active CP尺度 |
|---|---:|---:|---:|
| 2：09-09 | 30.06 | 0.030469187475 | 2.589435768 |
| 3：09-10 | 29.88 | 0.036475211535 | 3.099860063 |
| 4：09-12 | 29.42 | 0.051989856626 | 4.418378221 |

到10-09控制旧线已换为10-08 receipt `f0446fe6f6ef01f58d7b5720b68290f150d3b7093bc0e67a26fbfa22deda314e`，s=0.015834255171283874、冻结9-30，oldfloor adjusted55.14261903078265。不能拿这个更晚尺度回填9月条件。10-09 Hprior40.76/C36.68的当日三k命中成立，却不是1904层的首次警报。

## 可核交付与边界

- [DAILY_LAYER_SCAN.csv](DAILY_LAYER_SCAN.csv)／[JSON](DAILY_LAYER_SCAN.json)：全部209层日、C/H/峰日期、旧线、active收据及尺度、原pending、各k状态和请求先后。
- [FLOOR_PROVENANCE.json](FLOOR_PROVENANCE.json)：每层原旧线／实际更新线与来源，含canonical完整收据、scale_frozen_at及明确未使用的next_scale/current_s63。
- [FIRST_HITS_BY_LAYER_K.json](FIRST_HITS_BY_LAYER_K.json)、[SIX_STOCK_FIRST_HITS.json](SIX_STOCK_FIRST_HITS.json)、[HAINENGDA_ALL_TRIGGER_DAYS.json](HAINENGDA_ALL_TRIGGER_DAYS.json)：首次与全部海警报。
- PROTOCOL、SOURCE_AND_VALIDATION、SOURCE_EXCERPTS、DELIVERABLE_SHA256保存定义、源绑定与封口。

canonical收据读真实2024年度 `ar6_native_feasibility/NEW_CYCLE_READINESS/2024_full/inputs/stock-receipts`；不能误读universe refs里主要为strong窗口的收据文件。原持仓／floor／请求来自已完成No60原book和daily快照，复用上轮只读时间线；没有新账户或模型调用。

本扫描只定位固定原路径上的因果可知条件。任何更早退出都会改变后续持仓/CP消费/资金，故不能继续把后续原层当成候选仍会同量参与，也不能计算“少亏／多赚”。I主导UNKNOWN使覆盖不完整；多个k警报不提供参数最优性或经济支持，原执行代理/源快照/已见开发历史限制延续。
