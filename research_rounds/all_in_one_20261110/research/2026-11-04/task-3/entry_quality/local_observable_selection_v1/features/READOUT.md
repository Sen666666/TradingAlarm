# 本地5,517股、7固定日纯特征

`LOCAL_FIXED_DATE_FEATURES.parquet`已完成并封定，SHA256：`e257fdf858504be681fe1bdad5a11a1516aaf19ec44f19a85ecd2a7ae8439b50`。母体严格来自canonical adjusted_daily_bars已有5,517个symbol，保留38,619=5,517×7行，键`sid/day`唯一；不依赖旧账户或旧候选表。

| 固定日 | 全母体 | 当日确有源行 | 缺当日行 | 原PVR已知 | fast已知 | slow已知 | fast-only |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2022-01-10 | 5,517 | 4,503 | 1,014 | 4,336 | 4,368 | 4,243 | 125 |
| 2022-01-24 | 5,517 | 4,518 | 999 | 4,356 | 4,382 | 4,263 | 119 |
| 2024-09-24 | 5,517 | 5,309 | 208 | 5,281 | 5,285 | 5,270 | 15 |
| 2024-10-08 | 5,517 | 5,306 | 211 | 5,275 | 5,279 | 5,264 | 15 |
| 2026-01-15 | 5,517 | 5,451 | 66 | 5,402 | 5,411 | 5,387 | 24 |
| 2026-01-20 | 5,517 | 5,461 | 56 | 5,412 | 5,421 | 5,397 | 24 |
| 2026-05-15 | 5,517 | 5,495 | 22 | 5,441 | 5,446 | 5,413 | 33 |

输入直接读取`/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet`全可得历史（15,739,264行），逐股计算后才选7个exact日期；没有只读7行造暖期。每股source实际为单一tushare段，显式segment_id=0；正有限close/amount和原invalid-reset规则来自原`pvr_information_v1/feature_design/features.py`。没有补缺bar、延长日期、填停牌False，或把缺首日解释为未来上市。`target_status=MISSING_TARGET_BAR`仅说此文件当日无源行。该母体是当前本地股票集合，不冒称已还原历史PIT上市/退市/ST母体。

`derive.calculate`直接调用原`original_pvr`一次，保留`r/scale/amount_ref/u/b/e/E/score`；其中`score`就是原PVR。scale为严格此前63个|logreturn|中位数×1.4826，已知值下限1e−8；amount_ref为严格此前21个amount中位数；原E为21项.9权重。快慢段复用该次原e，不再另算e：fast为lag0..4的.8指数权重，独立5个有限e即可；slow为lag5..62的58项均值，独立readiness，不能用slow状态门控fast-only。

保留每目标的`past_source_observation_count/source_observation_count_through_t`、当前block观察数、block起点、scale所用此前return和其价格基点日期、amount/E/fast/slow窗口起止、独立`pvr/e/fast/slow_status`与knowncount、物理源起止日期。时钟是文件实际观察，不是补齐的市场session或已确认可交易日。

逐目标读取原未复权`daily_bars_history`对照：`raw_close/raw_volume/raw_amount`与qfq `current_close_qfq/current_amount_passthrough/qfq_adjustment_factor/raw_adjustment_factor/reference_adjustment_factor/reference_trade_date`均保存。所有真实目标行的raw×归一factor价格、raw/reference factor比及amount pass-through均bitexact；missing行保持NaN。qfq是当前文件的末端归一坐标，不是历史raw成交价；reference元数据保留并标出晚于目标日。固定同股reference常数在PVR的价格比及原e中抵消，不能因此宣称信号有未来收益泄漏；rawfactor的历史修订/known时刻、真实ST/停牌和公司行为账户处理仍不由本特征导出解决。amount单位倍率若同源一致，在amount/历史median(amount)中抵消，绝对交易容量单位合同不由此建立。

4股（000620、002583、300085、300666）全可得历史另用不含pandas rolling的定参数组/逐项reference复核，10列`r/scale/amount_ref/u/b/e/E/score/E_fast/E_slow`全部共同单元已知性及bits一致；见`INDEPENDENT_REFERENCE_CHECKS.json`。3个真实截断prefix：000620至2022-01-10（4,729/5,775行），002583至2024-09-24（3,187/3,580行），300666至2026-01-15（2,072/2,143行），全部共同列exact；见`PREFIX_CHECKS.json`。这些检查针对既有qfq坐标下的计算因果性，不将当前reference元数据冒充历史当时接收证据。

一次3进程固定批次约35.03秒，未改任何参数/原source；0账户、0订单、0排名、0未来收益标签、0下载/联网/刷新。代码及两个canonical源文件SHA见`RUN_STARTED.json`、`RUN_RECEIPT.json`。`SHARD_0/1/2.parquet`为同一次导出的中间分片，主消费文件为上述合并parquet。
