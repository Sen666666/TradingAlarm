# 1681交集：新旧输入的PVR / FAST / CONT同池对照

一次廉价纯特征批次已完成，33.37秒。没有恢复已停止的E0/I长跑；没有导入/调用stock_signal、E0、G1、账户、订单、收益或未来label。仅新增本目录，原`adjustment_review`与既有封存数据未修改。

母体是当前canonical 5,517股与原固定1,709股的精确symbol交集**1,681股**。旧source fullwarmup重算原e一次，再复用该e算原21项.9权重PVR、近5项.8权重FAST及lag5..62的58项slow。正有限close/amount、原optional masks与segment/invalid重启均沿原PVR；无缺bar填补、无稀疏pending-cache移位。原full signal已存在，因此旧dual缓存稀疏不妨碍此交集的廉价重算；这里没有据此宣称旧口径全5,517股已可得。

旧特征保留全部1,681×7=11,767键及独立readiness/窗口日期，输出`OLD_SOURCE_FIXED_FEATURES.parquet`；新侧直接复用已封canonical特征，双方11767键全保留在`ALL_1681_COORDINATE_FEATURES.parquet`。重算旧侧8列r/scale/amount_ref/u/b/e/E/score在全部1,681×968=1,627,208个原feature-grid日期点上已知性及bits一致；其中e finite 1,525,766点、E/score finite 1,521,151点，原四项clock字段也一致。000620至2022-01-24、002583至2024-09-24的真实截断prefix所有共同列exact。

每个日期、每个queue先固定**双方该queue完整的同一股票池**：PVR双方score有限；FAST双方fast独立已知，不要求slow；CONT双方fast和slow都已知。两侧分别在这个CONT共同池计算0..1 average-rank百分位，再固定0.3*p_fast+0.7*p_slow。没有正值过滤、绝对值改号或参数扫描。CONT用数学等价整数半秩分子`3A+7B`精确比较，同分symbol升序；PVR/FAST保留未round原值、同分symbol升序。

| 日期 | PVR共同N | FAST共同N | CONT共同N | 三queue各自top20交集 | 最大位移 PVR/FAST/CONT |
|---|---:|---:|---:|---|---|
| 2022-01-10 | 1426 | 1432 | 1405 | 均20/20 | 4 / 0 / 14 |
| 2022-01-24 | 1429 | 1433 | 1408 | 均20/20 | 1 / 1 / 3 |
| 2024-09-24 | 1618 | 1620 | 1615 | 均20/20 | 15 / 26 / 25 |
| 2024-10-08 | 1612 | 1614 | 1609 | 均20/20 | 38 / 46 / 41 |
| 2026-01-15 | 1640 | 1642 | 1637 | 均20/20 | 13 / 11 / 120 |
| 2026-01-20 | 1641 | 1643 | 1639 | 均20/20 | 10 / 3 / 188 |
| 2026-05-15 | 1665 | 1665 | 1653 | 均20/20 | 39 / 29 / 6 |

七日×三queue共21组前20**集合**相同，不表示前20内部次序或全池名次均相同。既有PVR同池全部11,031个key的old/new名次与`adjustment_review/ALL_COMMON_FINITE_PVR_RANKS.csv`逐键完全一致。新扩展的FAST/CONT排名不混用原pending/H1/账户次序。

11个固定目标×7日×3queue的231行全部保留在`TARGET_231_SAME_POOL_RANKS.csv`。每queue各66共同已知、11双方UNKNOWN；UNKNOWN不赋名次。名次变化行分别PVR3、FAST2、CONT16；其中最大为688012在2024-09-24的CONT 1111→1107，仅4名。目标没有跨入/跨出top20。某目标自身分数不变仍可因其他股票变化而换名次，不能把该目标的名次变化全归为自身公司行为。

交付字段提示：`ALL_COMMON_QUEUE_RANKS.parquet`保留全部33,046条共同排名及rank delta；`TOP20_BOTH_SIDES.csv`有840条双方各自top20记录。CONT的`queue_value_old/new`是**整数排序分子**，不是0..1分数；归一分数`CONT_old/new`、`p_fast_old/new`、`p_slow_old/new`在排名parquet和top20 CSV，等于分子除以20(N−1)。PVR/FAST的queue_value就是各自原值。

这是新旧输入坐标的对照，不是全表纯CA干预：价格历史、复权/动作处理、观察集合、mask/segment、源单位或浮点编码均可能不同，本次未逐股因果归因，也未认定哪一方供应商正确。固定同股reference常数及同源amount单位倍率在相应比率中代数抵消，但不能由此认证历史factor vintage/PIT；历史ST/停牌、公布/接收时刻和交易资格均未由此补齐。此结论只覆盖七个已消费日期、1681交集的score共同可评池，不是全5517、合法候选、真实样本外或收益改进。

源SHA、全部1681原signal路径/SHA、grid复核、两prefix、输出SHA见`COMPLETION.json`与`SEAL.json`。无新账户、无E0/I/G1调用、无参数改变、无forward、无联网/下载/刷新，全部进程已结束。
