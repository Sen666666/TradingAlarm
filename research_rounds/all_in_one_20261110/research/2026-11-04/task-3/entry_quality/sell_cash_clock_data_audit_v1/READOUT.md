# 卖款回用时钟与本地执行数据：只读审计结论

本轮不联网、不补数、不修改策略、不运行模型、账户或新回测。结论只对应当前 No60 调用链、已有原账和列明的本地数据根；不是全机数据普查或实盘认证。

## 1. 已证实的因果路径

**当前代码先用执行日最终 H/L/V 产生模拟卖出 fill，再于同一个 OPEN 事件把净款结算进 available，随后确定新买数量并预留资金。** 不是把未成交退出意图直接加到现金；问题是执行代理的输入时钟早于其真实可知时刻。

严格顺序见 [完整源码摘录](code/EVIDENCE.md)：

1. `joint_v3.py:304–306` 按 `sorted(a.exits)` 依次执行 `market.window(...,'sell',1)`、`fill_exit`。
2. `fast_market.py:53,59–63` 查当天完整 volume 有效性；用当天 `high<=low` 禁止交易；容量为 `min(过去20个正成交量日均量×1%, 当天完整volume)`；卖价为当天 OPEN×0.9995。该过程先于买单资金决定。
3. `sector_account.py:746–797` 按可卖库存、数量格点、容量生成模拟成交和净款 Settlement；正净款此时还不是 available。`J.fill_exit` 的第一次 sync 只把应收同步。
4. A 协议 `settlement_lag_sessions=0`；`FastMarket.lag(...,0)` 返回原 at。`J.opening:307` 执行 `settle_due(at)`，由 `sector_account.py:804–805` 把到期净款加进 available；随后 sync。
5. `J.sync:58–59` 令 `Budget.cash=available+order_reserved`，其余应收单列。实际 No60 route 来自 `native_adapter.py:17` 的 `P.ROUTES[True]`，仍检查现金：

```python
if cap+fee>min(float(a.available-a.current_nav*D('.1')),b.cash-reserve)+1e-9:
    fails.append('cash_or_original_reserve')
```

6. `J.opening:308–318` 按 rank、同 rank CORE 优先确定数量并 reserve；`study.py:100` 扣 `available-=gross+fee`。
7. `J.opening:319–322` 全部买资金预留后，才查询买端 window 并模拟 fill；末尾再 settle/sync/check。买端后查 H/L/V，**不消除卖端在前的资金反馈**。

最关键的原文为：

```python
for sid in sorted(a.exits):
    win=self.market.window(sid,at,'sell',1)
    if win:a.fill_exit(sid,win)
a.settle_due(at);a.sync(at);funded=[];done=set()
```

`source_available` 实际只查不可用日期和源数据段断裂，不验证 H/L/V 的逐字段发布时间或接收时间。整条调用共享同一 OPEN at，没有行情接收、订单发送、交易所接受、成交回报、余额可用的外部时序。

## 2. 原账直接数值：海能达 2024-10-22

原 No60 BASELINE/2022_2024，全部以下事件标记 09:30；审计索引与原 source SHA 见 [原事件](code/EXISTING_ORIGINAL_EVENTS.json)。

| 原事件 | 数值 |
|---|---:|
| 前 CLOSE 可用现金 | 99,854.4201497192475 元 |
| audit17617–17619：000656.SZ 卖出后结算 | +333.6393657149500 元 |
| audit17618–17620：601107.SH 卖 8800 股，5.507245 元/股，扣费后结算 | +48,426.7248440404000 元 |
| audit17621 前 available | 148,614.7843594745975 元 |
| audit17621：海能达预留 1000 股 | 14,007 元货款＋5.8978487 元买费 |

601107 原 bar 为 OPEN 5.51、HIGH 5.74、LOW 5.40、volume 75,611,279 股。该日源行 `observed_at=""`，只有日日期；manifest 的 `close_available_time=15:05` 不是 09:30 前收到最终 H/L/V 的证据。原始记录见 [对应日线](code/RAW_601107_20241022.json)。

这证明卖款进入买单读到的资金前缀。**未做“删去卖款”反事实，不能推断该买单必然失败、数量必然改变，或该问题带来多少收益偏差。** 模拟 receipt、journal 中的 `real_sell_fill` 名称也不是券商真实回报。

## 3. 本地实际覆盖与缺口

| 类别 | 找到的证据 | 能支持与不能支持 |
|---|---|---|
| my-quant 日线 | 15,739,264 行，全局极值 1995-04-06—2026-05-15；raw 5517 文件 | 可核日级输入。831 个 artifact 恰 6000 行，早史截断尚未排除；日期极值不代表每股连续覆盖。未重扫全表重复键/历史母体。 |
| my-quant 分钟、tick、盘口 | 四数据根及已审 schema 内未识别 | 无已核执行覆盖；不代表全电脑绝无文件。 |
| TradingAlarm 分时和 quote | 2026-10-16 单日17标的、3205分钟价点；1143标的单时点 raw numeric quote | 分时确实存在，但局部日、不完整、部分量额缺失。quote bid/ask/depth 字段映射未核；不是已证双边历史盘口，不能覆盖盈新2022/海能达2024链。 |
| TradingAlarm 最新 market | 1709股票＋90行业，共1799日线 series；1797末日2026-11-04、2个末日10-30；facts/signals各418文件 | 日线长历史样本存在，未对全池逐行重验。raw数量不等于当日可用facts数量；不是历史PIT池。 |
| paper-quotes | 8批、9标的，42个整包history响应；内容为 daily OHLCV，日期2026-10-12—11-05 | 有真实本机 `received_at`，在收包并保存后记录。不是各历史bar第一次发布时间，不是逐笔流；早盘当天bar仍可能形成中。 |
| 停复牌、涨跌停、ST | my-quant limit仅2026-05-15的7599行；suspend仅2020-03-12的22条事件；证券表list/delist全空 | 无已核2022—26连续可交易状态/ST路径。limit有2082标的不在当前证券表、pre_close空2104；单日事件缺行不代表可交易。 |
| 企业行为 | my-quant factors 16,214,935行；TA actions 16720个事件，2013-03-04—2026-11-04；另688008八条公告日期样本 | factor不是权息执行。TA池均标research proxy，paid_at/新股可卖时刻已知数均0；八条公告日期正证据不外推全池公告发布时分或支付时钟。 |
| 时间与行业PIT | 本机响应接收、ingestion、cache published_at均有部分记录；membership12780行有effective/known_from等字段 | 三类时钟须分开。历史实际公告/行情原始发布时间未证；effective标签不能单独证明当时已知。日线known_at/15:05/日历OPEN是模型约定。 |
| 使用权限 | TA README/docs保留原用户指定客户端的只读研究授权；本轮只读取已存文件 | 第三方行情对具体用途/再分发/商用的许可范围 UNKNOWN；未外连核验。不由“未找到许可”推断违法，也不把本地读取授权当供应商授权。 |

详见 [my-quant盘点](data_myquant/READOUT.md) 和 [TradingAlarm盘点](data_tradingalarm/READOUT.md)。大日线只核 footer；有限小表做必要列检查；没有把采集任务 succeeded 当完整历史保证。

## 4. 最小修复合同与停止条件

以下是接口修订说明，**本轮未实现、未修改策略**。

- 保留前收盘信号。把原单一 OPEN 拆成：行情收到→决策/数量冻结→发送→接受→部分成交回报→可用余额确认；分别记录 exchange_time、received_at、decision_at、send_at、ACK/fill/cancelACK 和数据来源。这是逻辑阶段，回报接收可乱序；可验证的 fill 先到时不必等先收到 ACK 才处理。接受委托不等于成交，成交也不能无依据等同本机资金已可用。
- 只由当时已确认可交易余额资助买入；卖单未成交余量继续占库存和退出责任，部分成交仅释放已确认部分。资金预留原子扣占，按order/fill ID去重与乱序对账，取消仅在确认后释放。不能假设经纪商条件单。
- 买单以决策时已收到、未过期的有效报价与明确限价决定数量/费用预留，成交由更晚事件确认；限价允许零/部分成交。不能看完最终 OPEN 再追记参加已经完成的那笔撮合；同价后来可能成交并不证明代码的同价必成。
- 历史重放必须有目标证券/日期匹配的行情频率、价域、时钟、可交易状态/费用版本；涉及资金回用还要有可追溯成交及资金可用时序。仅tick成交打印不证明本单成交或双边容量。
- **缺这些数据时，停止“历史细粒度可执行重放、实盘收益、同OPEN卖款可用”的认证。** 现有账户仅保留为明确的日线代理研究结果，不能宣称收益下界；源码/账务核对仍可继续。只把 delay 改一格，若仍读最终 H/L/V 和回填原 OPEN，不能修复因果。
- 若未来另获授权做粗粒度代理修订，可把日线 postcheck 结果的确认/卖款回用置于后续事件，并在收单前冻结已知数量/限价；它只能消除指定的信息回流，仍是代理、未证实盘口/队列。不能把它自动称为原策略可实现收益，本轮不运行该改动。
- 当前第三方许可范围不明时，不新增外部取得或扩大用途承诺；继续现有本地只读审计。缺行情、许可或回报时钟各自是对应后续阶段的阻碍，不是拒绝完成当前取证的理由。

## 5. 复核范围

[独立复核](review/READOUT.md) 将源码/协议原文身份、交付文件绑定、现金顺序和分阶段STOP分别记录。它不复算无卖款路径，也不认证未来策略收益。未改动原账或原代码；未读取密钥、私有账户数据库。
