# 开盘执行真实性：同OPEN定量与成交尚无实盘证明

**先明确口径：盈新、海能达的“原实际成交”是原回测账本实际填单，不是券商/交易所实盘回报。** 本轮只读源码、原账与公开交易规则，没有新账户、回测、执行测试或价格路径。

## 代码真实顺序

[joint_v3.py:302](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:302>)先调用卖出window、填单与结算；311—318读取当日raw OPEN→LR.preview→实际No60 route搜最终q→reserve；320—322再查买入window，断言其execution_price等于preview的OPEN×1.0005，然后fill_buy。没有更晚的报单/外部ACK/撮合时间。

[study.py:56](</Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:56>)的`p=op*(ONE+SLIP)`及`op<=floor`拒绝都发生在最终OPEN已读之后。preview/route返回why时尚未创建这笔新BuyOrder，不能叫撤销已提交委托。reserve后无window则保持待单，后续expiry/cancel ACK走模型内部状态，不是已验证的券商撤单协议。

前CLOSE的`clock.decision_at`仍写入BuyOrder.created_at/日志signal_at，另有OPEN reserve.at与known_open_funding=True；这些字段没有记录最终q的计算结束、client send、交易所收到或实际撮合时刻。模型delay_events=0，ledger允许window.at=earliest_execution_at，receipt.at取window.at。[源码完整片段](code/EVIDENCE.md)。

FastMarket还在OPEN使用执行日全天H/L/V构建窗口与容量。买window在融资后查询，但卖window先于卖款结算/买入融资，因此后验日线条件可经卖款反馈影响买入数量。不能笼统声称全天数据只影响事后填单而不影响资金选择。[输入与时钟证据](data/EVIDENCE.md)。

## 两条链的原时钟

信号均为15:10，原reserve/fill均标nextOPEN 09:30；没有交易所申报、接受、撤单ACK或逐笔成交ID/时刻。

| 原案例 | 先前信号/冻结值 | 读OPEN后的原决定 | 同次事件的代理结果 |
|---|---|---|---|
| 盈新68 | 2022-01-10；rawC2.74、cap3200 | 1/11读rawO3.01，reserve100 | fill100@3.011505 |
| 盈新1/20未买申请 | 1/20；rawC3.29、MOBILE cap5900 | 1/21读rawO3.28，preview/route后拒绝提交 | funding=`cash_or_original_reserve,sector_capital`；无新reserve/fill |
| 海能达1994 | 2024-10-14；rawC8.76、cap1400 | 10/15读rawO8.90，reserve100 | fill100@8.90445 |
| 海能达2039 | 10/21；rawC13.15、cap1100 | 10/22读rawO14，reserve1000 | fill1000@14.007；不是前轮新风险纸算的500 |

原九笔均精确等于rawOPEN×1.0005。[完整九笔原时钟](cases/NINE_ORIGINAL_EXECUTION_CLOCKS.csv)。它们证明模拟规则如何记账，不证明该数量在真实开盘时有可成交对手盘。

## 集合竞价、限价委托与开盘后的区别

历史规则核对使用[深交所2021年3月交易规则原文](https://docs.static.szse.cn/www/fund/guide/W020210331716400647184.pdf)及[2023年交易规则原文，中银证券镜像](https://www.bocichina.com/file/attach/20240905/%E6%B7%B1%E5%9C%B3%E8%AF%81%E5%88%B8%E4%BA%A4%E6%98%93%E6%89%80%E4%BA%A4%E6%98%93%E8%A7%84%E5%88%99%EF%BC%882023%E5%B9%B4%E4%BF%AE%E8%AE%A2%EF%BC%89.pdf)。2021版2.4.2/3.3.1/3.5.1—3.5.3、2023版2.3.2/3.3.1—3.3.2/3.4.1—3.4.4/4.2.1—4.2.2给出时段、确认和成交规则：开盘竞价9:15—9:25，连续竞价从9:30开始；申报接受时间与撤单限制有明确规定；连续成交由届时申报簿决定。开盘价可能来自集合竞价，也可能来自之后第一笔连续成交。

以下是据此作的时序判断，而非声称读到了原策略真实申报：

- 若要参与开盘集合竞价，普通数量/限价委托须事先进入该次撮合；不能等最终竞价价格已产生，再按它选择q并回到该次竞价。预先冻结q/limit是另一套执行政策，当前代码没有证明它与原OPEN自适应q等价。
- 若OPEN来自9:25竞价，09:30知道这个数值本身可以因果成立；**不能因此保证**09:30新送限价单仍以OPEN或OPEN+5bp成交。按OPEN设置限价只能限制可接受价格，不保证成交。
- 若该股没有竞价OPEN，日线OPEN可能是稍后第一笔成交。看见这笔成交后才计算/发送的单不能倒插进已发生的成交；后来可能同数值成交，但需新报价和实际撮合证据。
- 9:25后准备、9:30报入普通限价单可构成待实现版本，但没有券商具体协议/日志不能假定9:25—9:30的接单/排队行为，更不能假定条件单。5bp是成本假设，不是延迟或队列模型。

## 建议的明确修订：首次可用报价后发普通限价单

1. **分开事件。** 保留前CLOSE SignalIntent及h/信号cap；另建QuoteReceived、OrderDecision、OrderSent、VenueAccepted、FillReceived、CancelConfirmed。signal_at不再冒充最终数量的decision_at。跨系统时间须有可核同步/误差范围。
2. **报价条件。** 进入连续竞价且股票可交易；在轮到原PVR候选、当前实际资金可用之后，取客户端收到的第一条有效买方ask/卖方bid报价。缺盘、陈旧、状态未知或资金仍在待退/未ACK单中，不提交；等待/expiry规则必须先固定，不挑后来有利价。不能以计划卖出净款代替真实已确认available。
3. **普通限价委托。** 一个最小版本是买单以所见ask1作为合法tick限价、数量不超过冻结cap及所见ask1量，再按该限价最坏支出、费用与全账责任定量；卖单对称看bid。报价量不是未来成交承诺。只提交普通限价指令，不借未确认的券商条件单能力。
4. **发送以后不能回填。** 成交来自订单到达之后的订单簿重放/真实回报；价≤买limit、qty≤剩余单量、时间不得早于交易所接受。允许0或partial。价变后撤改须等撤单确认，未ACK前保留现金/风险责任。客户端收到订单ACK不必早于收到fill，不能强加错误的全序；但venue接受先于venue成交。
5. **现金反馈也异步。** 优先提交已有退出意图；仅确认到达的真实卖出回报/可用余额用于后续买入。其它未卖股票继续占库存/责任，不因计划出售释放。新买资金按实际PVR队列提交时更新，不假定所有股票同09:30完成全部卖出、结算、计算和成交。

所需数据至少：逐笔或足够细的双边报价/可用量与交易状态、exchange事件时间和feed接收时间、订单send/venue接受及回报时间、实际fill/cancel ACK、dated tick/涨跌幅/停牌/交易单位与费用。若要历史模拟准确排队、partial和延迟，还需相应深度/订单流、延迟假设及撮合模型；只有L1快照只能构造发送决策，无法精确识别到达时可成交量。

目前日线库不具备这些字段。不得把09:30标签当真实receive/arrival，也不能用全日volume做第一秒可成交深度。

具体源码改点（只列方案，本轮未实施）：保留PreparedRunner的CLOSE信号事件，另接quote/order/fill/cancel回报事件；把J.opening的读raw.open/搜q/reserve拆到on_quote及真实回报驱动；LR.preview接带receive时间的可执行报价/限价，不接事后日线OPEN标量；FastMarket.window不再用全日HLV和固定OPEN价生成实盘fill；BuyOrder分开signal_at与实际order_decision/send，FillReceipt只由真实回报或明确的因果撮合模型生成，cancel_ack不能由本地同步函数冒充。仅把delay_events从0改1不够：它是原事件计数，不是quote/报单实测延迟。时间戳精度可能造成同毫秒，须保因果序号/时钟误差，不能只靠把相等号改成严格大于来认证真实性。

## 数据缺失时的结论边界

原结果应保留标记为`DAILY_BAR_EXECUTION_PROXY: known_OPEN_then_same_OPEN_plus_slip`，真实可实现fill/资金路径/PnL为UNKNOWN。信号因果与代理内部现金/费用一致性仍可单独审；同一代理下对照结果不能直接解释为实盘收益、回撤或改进。

可列预先固定的不同成交假设作敏感性研究，但本轮不运行。日高买/日低卖仅可能是固定交易集合的静态逆价压力，不能作为内生组合收益下界：成交集合、未成交、重入、仓位与资金反馈会变。无数据不能给可靠悲观收益界，也不能把分钟bar的OPEN再包装成已证实盘成交。

[独立源码审查](independent_review/READOUT.md)已确认这些边界，未授权或运行新测试。

另更正旧报告标签：[OPEN mark更正sidecar](data/CORRECTION_OPEN_MARK_DOMAIN.json)记录原native在当日OPEN可得时使用rawOPEN；此前七点桥中的前CLOSE估值仅为比较域。原JSON已保存的rawOPEN域七点拒绝不变，旧封存账/数字未改。本轮结论依赖读OPEN/下单/填单顺序，不依赖旧标签。
