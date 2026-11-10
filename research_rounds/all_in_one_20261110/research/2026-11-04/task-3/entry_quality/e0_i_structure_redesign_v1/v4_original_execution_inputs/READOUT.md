旧V4授权已因用户否决封为SUPERSEDED：不再沿用“无CP取消CORE”或“发permission即烧probe”。已完成CP*市场事实保留，新授权未实现、未运行。这里只摘原No60模拟账。

| 原层 | 原信号→代理fill | 原股数 | 原fill价(raw OPEN) | 原调整保护线 | 同信号日CP |
|---|---|---:|---:|---:|---|
| 盈新CORE68 | 2022-01-10→1/11 | 100 | 3.011505 (3.01) | 2.255055048923375 | 有；CORE本身CP1_id为空 |
| 海CORE1994 | 2024-10-14→10/15 | 100 | 8.90445 (8.90) | 42.59907875674594 | 旧CP与CP*均无 |

原始索引：CORE68=`B.json.gz trades[71] / decisions[4].intents[38]`；CORE1994=`trades[3544] / decisions[669].intents[20]`。可读表见[ORIGINAL_CORE_TWO_RECORDS.csv](ORIGINAL_CORE_TWO_RECORDS.csv)，JSON保完整源路径。

指定8个信号日已保存：

- 盈新1/10原CORE与MOBILE双intent，只有CORE在1/11实际fill100股，不能把未发出的另一角色称为成交。
- 盈新1/20原MOBILE，1/21资金结果`cash_or_original_reserve,sector_capital`，无对应实际buyfill；1/24原MOBILE在1/25实际fill层122，4700股@4.00200。
- 海9/20有CP但原decision无该股intent、无该信号buyfill，9/23也无该股funding记录；不能从CP存在推有挂单。
- 海10/14原CORE在10/15实际fill层1994；10/18原MOBILE在10/21实际fill层2017，1100股@12.00600；10/21信号在10/22实际fill层2039，1000股@14.00700。
- 海11/20原MOBILE，11/21资金结果`cash_or_original_reserve,probe_risk`，无对应实际buyfill。

原`reserve`审计有target_shares、order_id、decision_at；`real_buy_fill`有layer、shares、signal_at、CP1_id；另有`release_buy`记录。这些是原模拟账事件。`release_buy`只证明账本释放预留，不能当交易所/券商撤单ACK。原最终`orders`为空，budget.orders可读但只是期末dump状态，不能回填为申请时pending/partial/remaining快照。本稿没有真实exchange submit/cancel/fill ACK、订单网络时延或撮合队列；新“0fill且全部cancel ACK才重申”必须由明确外部反馈合同驱动，不能从这里补造ACK。

[EIGHT_FIXED_ORIGINAL_SIGNAL_EXECUTION_RECORDS.json](EIGHT_FIXED_ORIGINAL_SIGNAL_EXECUTION_RECORDS.json)保原intent、对应实际buyfill、同日/次日journal及audit、次OPEN资金结果、原CLOSE持层ID/pending列表和期末order警示。`same_day_or_next_OPEN_journal`是日期范围旁注，可能包含此前信号的成交；归属信号以`original_actual_buys_tied_to_signal`为准。只保原股数/价格/线，未求任何新q、资金、持仓路径或收益。
