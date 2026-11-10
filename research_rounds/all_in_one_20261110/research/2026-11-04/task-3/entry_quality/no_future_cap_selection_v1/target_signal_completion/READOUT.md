# 六股×七日原信号补全

已完成固定42请求，6worker计算墙钟33.21秒：38条 `EXACT_TARGET_STOCK_SIGNAL`，4条 `MISSING_TARGET_BAR`。未启动账户、全池计算、参数搜索或外部数据访问；没有修改已封存的signal_review。

主输出 `TARGET42.parquet/.csv` 可按 `sid,day`合并。包含 `target_source_row_present`、`prefix_end_day`、前缀行数/实际最晚日期，原 `e0_* / i_* / g_* / numeric_event / numeric_leg_direction / close`，以及当日同源OHLCV、成交额和复权字段 `source_*`。JSON保留嵌套原始行。MISSING的信号字段为空，不能当False。

| 日期 | exact行 | E0 ready | E0 target | I target | i_buy |
|---|---:|---:|---:|---:|---:|
| 2022-01-10 | 4 | 4 | 4 | 4 | 1 |
| 2022-01-24 | 4 | 4 | 4 | 4 | 2 |
| 2024-09-24 | 6 | 5 | 3 | 3 | 2 |
| 2024-10-08 | 6 | 5 | 5 | 5 | 5 |
| 2026-01-15 | 6 | 6 | 6 | 6 | 3 |
| 2026-01-20 | 6 | 6 | 5 | 5 | 3 |
| 2026-05-15 | 6 | 6 | 6 | 6 | 2 |

四条MISSING是金海通603061、珂玛301611的两个2022日期：源没有当日行，未推断上市、退市或停牌。珂玛在两个2024日期有exact源行，但原ready=0、I=0；这是已算出的未准备状态，区别于MISSING。江丰与金海通9/24 I=0，10/8 I=1且i_buy=True；海能达2026-01-20 I=0。原算法结果不代表未来盈亏。

每股每日期均独立执行源过滤 `symbol==sid AND trade_date<=t`，仅把该请求的截断前缀传给原封存 `stock_signal.calculate`；未从未来frame计算后回填。只有38条有当日bar的请求调用模型。FREEZE先绑定六ID、七日期、原代码、driver和实际canonical输入SHA256：

`11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b`

运行后源码哈希与源大小/mtime均未变。银之杰9/24与fixed35、盈新/海能达9/24与pilot的**全部原信号字段精确相同**；这次两条pilot重算结果也已获得实际输入SHA绑定，旧pilot文件原有证据限制仍原样保留。

`i_buy`是原G1_I当日事件字段，不等于`i_entered`，也不表示新独立结构、订单或最终交易资格。此处不计算CP、行业/市场资格、持仓资金、ACT或历史cap；`full_S0_eligibility_q`全部未评估。canonical qfq参考日可能晚于目标日，历史复权因子及available_at未由本次认证；“无未来价格行”不扩展为完整历史PIT数据声明。

`FREEZE.json`保存输入/代码身份，`COMPLETION.json`保存38/4状态、耗时及三条复核，`SEAL.json`绑定全部交付文件。无剩余运行。
