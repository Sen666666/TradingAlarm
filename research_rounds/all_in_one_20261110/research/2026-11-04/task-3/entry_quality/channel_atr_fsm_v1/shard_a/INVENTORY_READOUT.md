# 分片A：全母体库存

对原STOCK_MANIFEST按symbol排序，取零基偶数索引：855项，846 complete、9项原`not_applicable_no_local_observation_by_end`。没有按获资、原盈亏或原持仓筛股票。855项路径与必需schema均可盘点；9项无观察不算负样本。

| 展示期 | 有source/CP观察股 | 有原receipt股 | 原CP观察行 | 原raw CP收据 |
|---|---:|---:|---:|---:|
| 2022—2023 | 807 | 797 | 373285 | 17812 |
| 2024Sep—Dec | 819 | 813 | 65322 | 6339 |

fullprefix严格截到2026-06-30：source共2025166行，原CP2024994行。846 complete中845股source到2026-06-30，688072.SH到2026-06-26。原CP没有source中不存在的日期。

source比CP多出的172行在134股，已逐行核为synthetic=True、observed=False；price_eligible/source_invalid空值共344个，不得bool(NaN)。这不是已证明的172个交易日缺行情。2022—23仅000552.SZ 2022-04-11与300319.SZ 2023-06-20两条合成行，2024Sep—Dec无此差异。具体行见`SOURCE_DATES_WITHOUT_CP.json`。

当前库存只读日期、mask标记及原receipt/ready列，尚未验证每个OHLC数值/完整交易日历缺session；缺行不能推成停牌。历史ST、逐日合法limit、盘口、真实公告接收时点未保存。原manifest声明SHA已经带入逐股库存，当前文件bytes的完整校验留给统一runner，未将声明当已复核。

`SYMBOLS.json`可直接交共享runner；`INVENTORY.json/csv`含每股refs、schema、范围、缺口及原declared SHA；`INVENTORY_SUMMARY.json`是本次分母。库存阶段FSM/保护pair/账户/新q均为0，后续只接受封版共享engine/runner，不另造策略实现。
