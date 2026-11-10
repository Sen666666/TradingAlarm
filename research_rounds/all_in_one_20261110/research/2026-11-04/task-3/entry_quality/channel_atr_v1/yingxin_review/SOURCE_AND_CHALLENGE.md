# 盈新OHLC已核；通道/ATR规则尚未计算

仅原source准备与纸面审查，0账户/新q/收益，未计算20/55通道或ATR。待主freeze确定窗口、ATR种子/shift、里程碑和退出状态后再算，不按历史盈利选择N。

## 同源价格及执行字段

信号源：`/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/prepared-v2/000072/signal.parquet`，含同一条记录的adjusted OHLC、raw OHLC、adjustment_factor、segment与observed/eligible/synthetic标记。它的C和factor与No60原facts逐个指定日exact一致。

真实原native执行raw源：`/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/runtime/market/update-20261030-153010-c551af/prepared/bars/000620.SZ.parquet`。10个指定日的O/H/L/C与signal内raw字段全部exact。完整2179行prefix（2013-01-04至2022-02-07）与指定日已保存，没有用当前QFQ覆盖历史OHLC。

原`current_pool_bridge.py:145–150,179–217`声明prefix-causal信号坐标：起点factor=1，只有当时生效的action改变factor；theoretical_ex_price用previous raw close计算理论除权价后累乘，随后OHLC同乘当前factor。2021Oct—2022Feb7本股factor恒为`1.138916691375442`，期间无该source action，因此所选通道/ATR输入不含跨除权日跳点。此处验证的是既有研究source的计算时钟，不宣称action档案本身保存了真实公告接收时点；action文件仍标declared_research_proxy。

| 日 | raw O | raw H | raw L | raw C | 前一source raw C |
|---|---:|---:|---:|---:|---:|
| Jan6 | 2.04 | 2.26 | 2.04 | 2.26 | 2.05 |
| Jan7 | 2.30 | 2.49 | 2.15 | 2.49 | 2.26 |
| Jan14 | 3.82 | 4.00 | 3.62 | 3.78 | 3.64 |
| Jan17 | 3.66 | 3.92 | 3.40 | 3.59 | 3.78 |
| Jan20 | 2.95 | 3.29 | 2.91 | 3.29 | 2.99 |
| Jan21 | 3.28 | 3.62 | 3.20 | 3.62 | 3.29 |
| Jan24 | 3.72 | 3.98 | 3.26 | 3.98 | 3.62 |
| Jan25 | 4.00 | 4.38 | 3.70 | 4.38 | 3.98 |
| Jan26 | 4.56 | 4.61 | 3.94 | 3.94 | 4.38 |
| Feb7 | 2.88 | 2.88 | 2.88 | 2.88 | 3.20 |

所有数值同时有原adjusted字段与source flags，见`KEY_OHLC_INPUTS.json/csv`。前一source close只是备料，最终ATR必须使用freeze规定的同源有效观察钟，不能因这里已列就默认为最终ATR算法。春节自然日不补虚拟观察。

原raw表没有历史ST、逐日合法涨跌幅bound、tick、停牌状态、盘口，也没有真实publication/received_at；指定行observed_at为空。不能凭约10%变化或Feb7 H=L=C推断真实涨跌停、可成交或次日必成交。原FastMarket.window:59–60恰是flat-day拒绝/当日H/L/V容量proxy，不能当先验合法限制或实盘fill证明。

## 纸面必须闭合的五处

1. 通道必须不含当前H：如`max(H[t-L:t])`再比当日C，否则若把H_t包含在通道，C_t>channel通常不可能。20/55如何并列是不同候选或两路许可，须事前写明，不能看盈新或赢家后选择。
2. E0只启动、breakout latch延续与失效是三件事。若每个E0 down/CP reset重置里程碑锚，旧反弹仍能反复领取“新净推进”；若latch永不失效且不看原保护，又复活旧entry-only粘滞。必须定义保护破坏后的新代，旧退出不能被当日新突破撤销。
3. ATR单位里程碑若每日以新ATR作同一分母，价格没有推进、ATR下降也可能凭比值跨级。可将每次未消费里程碑的ATR坐标冻结，或至少要求严格新价格frontier并明确阈值随ATR改变也是政策变化。不能把旧价/新分母冒称新市场推进。
4. `trail=max(oldtrail, known_peak−N*ATR)`确实不放宽，但ATR缩小时无新peak也会提高line；这可能是合理波动退出，也可能提早切掉正常整理，不能称新趋势确认。peak取H或C、包含本日还是此前、ATR使用t或t−1都需统一：旧line先判、本日收盘后才提高下一次可用line，次交易日行动。
5. gap/flat/T+1仍可穿越ATR退出参考线；ATR14×N不是最大损失或固定概率区间。新模型的退出request不能从原账推成候选fill。

## 未过通道但加速：必须承认取舍

单纯“加速”同样来自这条价格路径，不是独立真实性证据。盈新Jan20/21急涨仍低于Jan14已见H4；Jan24 C3.98也低于该H，Jan25 C4.38才越过。不能为保快速赢家增加一条同价加速豁免，却把它宣称自动排除盈新。

最小、无新门的解释是：E0允许START/原小试探参与加速；未过通道暂不取得通道扩张许可，允许代价是启动期规模较小。若用户要求通道未过也能连续扩张，就必须明确另一路“以启动/上一里程碑为不降锚的ATR单位净推进”可独立授权；它是放宽成熟定义的OR路，须原样保留失败反弹反例，不能再用EMA阈值把矛盾藏起来。这里不替主freeze选路线、步长或N，也不生成任何新数量。

该源可做一日手算和固定因果对照，尚无经济有效性结论。
