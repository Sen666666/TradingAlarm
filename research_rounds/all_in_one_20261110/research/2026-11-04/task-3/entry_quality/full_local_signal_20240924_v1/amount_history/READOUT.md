# 2024-09-24成交额自身历史分位

主合并文件：`AMOUNT252_2024_09_24.parquet`，5517唯一`sid/day`，SHA256：`9df498a842a541e5fcb64d038896d78df9cd39f98bfbce9773c5466e24141084`。主列`amount_history252_percentile`与原`amount_hist252_percentile`逐值相同。

冻结定义：当日A在**此前**252个同有效/source block个股观察中的经验中秩分位：`(#prior<A + 0.5*#prior=A)/252`。不含当日，全部252个历史量额须有限正数；不足不缩窗或改分母。当前缺bar/价格量额无效/source未知均不给分位。不是跨股票排名、不是过去252共同市场session或自然年，不设阈值或新增排序。

| 状态 | 数量 |
|---|---:|
| 完整252历史，分位已知 | 5179 |
| MISSING_TARGET_BAR | 208 |
| 同block此前观察不足252 | 130 |
| 全部请求 | 5517 |

只读取canonical必要列symbol/trade_date/close/amount/source，先截到2024-09-24，实际读取13618181条历史观察。source SHA已精确匹配`11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b`。amount保留vendor原单位，不乘qfq因子、不换现金/参与率单位。

复用已封5517单日PVR和prior20数据，未重算PVR/E0/I/G1；current amount与保存PVR输入逐bit相同，重新核窗口的prior20 median与已存`LIQUIDITY20`逐bit相同。分位单独准备，不借PVR、FAST或SLOW ready当252窗口ready。

## 原未复权数据独立计数

四例另外从`daily_bars_history/daily_bars.parquet`读取截至当日的原raw amount，使用Python逐项比较和精确有理数分母，不调用批量分位函数。四例各自此前252+当前的253个日期/amount与standardized完全一致；prior20再用Python statistics.median独立核对。

| sid | 当日amount原单位 | 此前252中小于当日 | 等于当日 | 中秩分位 | prior20 median原单位 |
|---|---:|---:|---:|---:|---:|
| 000620.SZ | 92640.411 | 220 | 0 | 55/63 = 0.8730158730 | 29490.0885 |
| 002583.SZ | 61865.117 | 4 | 0 | 1/63 = 0.0158730159 | 91030.488 |
| 300666.SZ | 271836.757 | 178 | 0 | 89/126 = 0.7063492063 | 112270.116 |
| 300085.SZ | 2193119.027 | 252 | 0 | 1 | 71652.5405 |

前三例非百分数显示，乘100才是百分位%。000620历史窗口起于2023-09-05，其余三例起于2023-09-07，均结束于2024-09-23；日期跨度不据此解释为已知停牌/上市状态。原252个日期和金额证据在`FOUR_RAW_252_WINDOWS.json`，计数在`FOUR_RAW_HAND_CHECKS.csv`。

输出保留currentamount、原prior20 median/knownN/端点、252窗口knownN/less/equal/端点与状态。未知分位为NaN而非0，0/1是允许的真实经验分位端点。原`AMOUNT_HISTORY_2024_09_24.parquet`是增加主合并别名之前的同值计算原件；`SCHEMA_ALIAS_RECEIPT.json`绑定原件到最终文件，无指标重算。

全部历史listing identity/ST/halt/limit/executable eligibility字段继续`UNKNOWN_NOT_CERTIFIED`，未读取任何当前cap、ST或行业资料。固定本地5517集合不冒称历史全A/PIT母体；名义close索引不证明供应商实际接收时刻。分位不认证质量、趋势、可交易性或收益。

唯一计算约3.37秒，0信号模型/账户/订单/阈值/排名/未来label/下载。源SHA、原值与状态计数在`COMPLETION.json`，最终别名与文件身份在`SCHEMA_ALIAS_RECEIPT.json`和`SEAL.json`。全部计算已结束，数据封存。
