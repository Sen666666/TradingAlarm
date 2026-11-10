真实OHLC及调整因子准备完成，尚未计算channel/ATR或运行新策略、账户、数量、收益。

两股沿No60原STOCK_MANIFEST绑定的`prepared-v2/.../signal.parquet`，不是CP_input的C/amount代理。Sea为000389，银为000516；均从2013-01-04完整前缀保存至2024-11-29。Sea2853行中真实合格HLC2852行，银2682中2680；明确保留原合成/无效行及源旗标，不静默填价。两股9—11月各58个观察均真实HLC合格。

| 股/日 | raw O | raw H | raw L | raw C |
|---|---:|---:|---:|---:|
| Sea 9/24 | 5.24 | 5.24 | 5.24 | 5.24 |
| Sea 9/30 | 6.06 | 6.67 | 6.06 | 6.67 |
| Sea 10/10 | 8.60 | 8.85 | 7.26 | 7.58 |
| Sea 11/1 | 31.00 | 31.02 | 25.38 | 25.38 |
| Sea 11/4 | 22.84 | 26.15 | 22.84 | 22.84 |
| 银 9/30 | 32.81 | 32.81 | 32.81 | 32.81 |
| 银 10/8 | 39.37 | 39.37 | 39.37 | 39.37 |
| 银 10/9 | 47.24 | 47.24 | 45.80 | 47.20 |
| 银 10/10 | 49.85 | 49.94 | 37.76 | 37.76 |
| 银 10/11 | 30.21 | 37.75 | 30.21 | 32.00 |

9—11月调整因子分别恒为Sea5.619931234399201、银5.277878318832183。四个调整OHLC字段逐项等于对应raw字段×factor，差异仅约1e−14浮点量级；source元数据`price_adjustment='raw'`描述原来源，不能只凭这个字符串把容器内已调整OHLC误当raw。前20/55历史H与TR必须使用同一可比坐标、保source段，不能混raw H与调整C。

channel高点不含今日，Wilder TR/RMA14和ATR(t−1)所需真实H/L/C历史均足够。计算仍等待唯一冻结口径：首TR在无前C时的定义、首14TR seed、无效/合成/缺bar及source变化的重暖规则。当前表中的前20/55高与ATR列明确为尚未计算，未自行选择公式seed或用C替代H/L。N=2/3/4不在本阶段运行或选择。

源schema没有直接halt、suspend、ST、price-limit、真实receive字段。原实际消费的`execution-rules-v2.json`同样没有已核真实逐日涨跌停界或tick字段，availability是研究proxy。缺行、非observed、零量不等于停牌；原`H=L`只能当完成日线的flat-bar事实，不能直接认定真实封板、排队成功或可卖。Sea11/4尤其H26.15>L22.84，并非flat。

银10/10次日开盘与当日剧烈下跌、Sea持续上涨，都不能用当日整日H/L/volume事后证明OPEN时已能成交。后续纸面旧线先判/新线次日生效只定义信号时钟；当前日线没有盘口、委托到达、partial fill/cancel ACK，仍只能报告价格代理，不能给实际净收益。

文件：[关键原bar CSV](KEY_ORIGINAL_OHLC_BARS.csv)、[字段/有效性](SOURCE_SCHEMA_AND_READINESS.json)、[规则字段盘点](EXECUTION_FLAG_AVAILABILITY.json)、[准备收据与源SHA](PREPARATION_RECEIPT.json)。两份`*_ORIGINAL_PREFIX_OHLC.parquet`保完整历史与全部原字段，新增的`prepared_observed_HLC_source_eligible`仅为源有效性旁注，不是交易信号。
