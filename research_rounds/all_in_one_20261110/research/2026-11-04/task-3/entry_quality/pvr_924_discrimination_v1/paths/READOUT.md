# 冻结2313股的收盘观察路径

已完成，纯执行5.52秒。`HORIZON_PATHS.parquet`为2313个完整sid行；`LONG_PATHS.parquet`为46260行，即每股未来第1至20个有效观察。未运行信号、账户、OPEN读取、成本或成交模型。

先冻结原 `i_buy_research=True` 的2313股、`rank_ALL_LOCAL_I_BUY`及9/24基准qfq收盘，随后才读未来价格。冻结源实际SHA为`11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b`。另核父线程`FROZEN2313_PRIOR_RANKS.parquet`的2313身份、日期、原rank、基价完全一致，score与冻结原候选逐bit相同；没有按未来结果选择股票。

每个观察要求close、amount均正且有限，来源已知且保持锚点来源；若有原显式有效/无效mask也应用。首个invalid/未知或改变来源会终止锚点block，不跳过重开。缺日不补；日期并集只作源缺行代理。本源schema无额外显式mask，实际读取列只有symbol/date/close/amount/source。

计算值为canonical qfq收盘比率：`return=C_n/C0−1`；`max_up=max(0,max(C_1..C_n/C0−1))`；`max_adverse=min(0,min(C_1..C_n/C0−1))`。只有满h观察才给full-h结果；不足时full-h为空，partial extrema另列。本母体5和20观察均完整，horizon删失0，不能将其推广为其他母体也完整。

| 指标 | 完整股数 | 主要nth观察日期 | 其他日期 | 自然日跨度 |
|---|---:|---|---|---|
| 第5观察 | 2313 | 10/8：2307股 | 10/9：1，10/15：2，10/22：3 | 14–28天 |
| 第20观察 | 2313 | 10/29：2302股 | 10/30：1，11/4：1，11/5：4，11/11：1，11/12：4 | 35–49天 |

5观察内6股、20观察内11股出现全source日期并集中的缺行代理。该并集为394个实际存储日期，9/24至2026-05-15，不是官方交易日历；不能将缺行判为停牌或把h=20称为20个市场交易日。

2313个锚点block在现存源内未遇invalid/source变更，最终均右截于源尾。**这是整个后续源block的尾部截断，不是已完整5/20观察的删失。** 2307股源尾为2026-05-15，其余6股源尾在2026-04-13至05-14之间；文件为何截止、历史退市/停牌状态均UNKNOWN，不由尾日期推断。源尾日期、block终止原因及horizon删失字段分别保存。

HORIZON表保留每个horizon的实际nth日期、自然日跨度、观察数、完整标志、收益/极值、partial字段及缺行代理数；LONG表保留真实观察日期、累计序号、收盘价/原生成交额、来源及相邻观察间跨度。`COVERAGE_METADATA.json`为完整覆盖收据，`MOTHER_CROSSCHECK.json`为父母体核同。

价格仍沿用冻结canonical qfq域；历史复权因子/available_at、证券范围PIT及真实可成交未由本次认证。这些只是固定信号母体的事后收盘路径，不能称为新策略收益或因果效果。
