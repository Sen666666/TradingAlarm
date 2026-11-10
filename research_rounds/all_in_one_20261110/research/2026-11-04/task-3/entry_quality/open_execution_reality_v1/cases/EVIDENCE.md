# 原执行时钟：盈新6笔、海能达3笔

这九笔是已保存研究账的原成交，不是新风险纸算数量或实盘成交。代码先在前一CLOSE保存信号/intent；次OPEN读取已知raw OPEN，再preview定量、route、reserve；随后成交代理按raw OPEN加5bp写fill。九笔均逐Decimal核同该价格公式。

|股票/层|signal CLOSE|前CLOSE raw价|nextOPEN rawO|原route/reserve时钟|原target/filled|fill时钟/price|
|---|---|---:|---:|---|---:|---|
|000620.SZ/68|2022-01-10 15:10:00+08:00|2.74|3.01|2022-01-11 09:30:00+08:00|100/100|2022-01-11 09:30:00+08:00 / 3.011505|
|000620.SZ/69|2022-01-11 15:10:00+08:00|3.01|3.08|2022-01-12 09:30:00+08:00|6300/6300|2022-01-12 09:30:00+08:00 / 3.081540|
|000620.SZ/75|2022-01-12 15:10:00+08:00|3.31|3.39|2022-01-13 09:30:00+08:00|5700/5700|2022-01-13 09:30:00+08:00 / 3.391695|
|000620.SZ/78|2022-01-13 15:10:00+08:00|3.64|3.82|2022-01-14 09:30:00+08:00|4200/4200|2022-01-14 09:30:00+08:00 / 3.821910|
|000620.SZ/113|2022-01-21 15:10:00+08:00|3.62|3.72|2022-01-24 09:30:00+08:00|5100/5100|2022-01-24 09:30:00+08:00 / 3.721860|
|000620.SZ/122|2022-01-24 15:10:00+08:00|3.98|4.0|2022-01-25 09:30:00+08:00|4700/4700|2022-01-25 09:30:00+08:00 / 4.00200|
|002583.SZ/1994|2024-10-14 15:10:00+08:00|8.76|8.9|2024-10-15 09:30:00+08:00|100/100|2024-10-15 09:30:00+08:00 / 8.90445|
|002583.SZ/2017|2024-10-18 15:10:00+08:00|11.95|12.0|2024-10-21 09:30:00+08:00|1100/1100|2024-10-21 09:30:00+08:00 / 12.00600|
|002583.SZ/2039|2024-10-21 15:10:00+08:00|13.15|14.0|2024-10-22 09:30:00+08:00|1000/1000|2024-10-22 09:30:00+08:00 / 14.00700|

## 先看OPEN后仍可拒绝：盈新1/20→1/21

1/20 15:10原mobile intent：cap5900、gross budget19567.320460227788090、调整线3.4053609072125717。1/21原raw OPEN3.28，源码preview对应买价3.281640；随后09:30 funding原记录为cash_or_original_reserve,sector_capital，没有reserve/fill。3.281640是源码公式对应预览价，不是假造实际成交价，尝试过的逐个股数没有保存。1/21下午另一个新信号到1/24才成交，两个时钟不可混。

## 看14元OPEN后定量：海能达10/21→10/22

10/21原收盘raw13.15、原intent cap1100、gross budget14575.426586994384950；10/22 raw OPEN14。原reserve实际target1000，原fill1000，价格14.00700。reserve.at与fill.at均为程序09:30，reserve.decision_at仍是10/21 15:10；known_open_funding=True。这里的1000是原交易，未加入任何新风险候选数量。

## decision_at、quote cutoff与真实报单时间不能混用

- [Runner.opening](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:302)：读取`raw.loc[day].open`后调用LR.preview，再`route`，成功才`reserve_quantity`；全部funding后才查询执行window并fill。raw OPEN读取和route调用没有单独的更细时间戳，代码逻辑顺序可查，实际耗时未记录。
- [LR.reserve_quantity](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:94)：先`quote.read_price(clock.decision_at)`验证原CLOSE quote，再`self._time(at)`；实际在OPEN构造BuyOrder，但其`created_at`参数沿旧signal decision_at，`earliest_at`为nextOPEN。audit另存真实程序reserve.at、原decision_at与known_open_funding=True。created_at/decision_at不证明前晚已向交易所报单。
- [DecisionQuote.read_price](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:175)：验证quote.known_at不晚于传入cutoff以及source/FX；此处传的是前CLOSE signal cutoff。实际OPEN价格另从raw条读取，不是用这一CLOSE quote读取未来OPEN。九行quote_source是原raw数据文件hash；源声明close_available_time=15:05，不是交易所逐笔送达记录。具体quote对象known_at未另存在这些audit行中，明确缺失。
- [FastMarket.window](/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py:45)：成交代理除了raw OPEN与5bp，还读当日H/L是否flat及当日完整volume，并以past20正量均值1%与当日volume取min做容量。J.opening将该检查放在funding之后；不能把这个后验执行代理称为开盘时已经知道全天H/L/V。

原日志缺失：没有交易所报单发送时间、券商/交易所ACK、交易所订单号/成交号、逐笔成交时间/队列、竞价分配或开盘价公布延迟。`buy:...`和`fill:...`是程序内部ID，09:30是研究时钟。现存代码能证明“按已知OPEN定量后，以同OPEN加滑点的日线代理成交”的模型规则，不能证明现实中能先见最终开盘价、再以该价拿到同样数量。

源文件：NINE_ORIGINAL_EXECUTION_CLOCKS.json/csv逐笔保reserve、fill、funding、原intent和audit逻辑序号；ORIGINAL_KNOWN_OPEN_REJECTION_JAN20_21.json保失败例。没有运行新策略/账户、没有求新数量，也没有将新纸算数量写入原成交。
