# 首轮执行组件输入契约与交付边界

更新：2026-10-23。组件后已接通共享数据的真实日循环和B0年度整股调仓，历史账户运行仍0次。最终运行契约及82项合成验证见 [RUN_PACKAGE.md](RUN_PACKAGE.md)。经济协议尚待root统一冻结。本文件不把今日行业/市值/港股通资格扩展成今日成交规则倒填历史。

## 交付与主调用

- `../code/sector_account.py`：CNY账本、逐单预算/股数上限、预约确认、部分成交、退出锁存与完成回执、延迟结算、现金分红应收及有限整股送转。
- `../code/current_fixed_pool.py`：显式今日固定资格、真实历史状态时钟和原准入纯函数的兼容层。
- `../code/run_first10.py`：固定S0/T0/T1各base/cost2/delay1与B0_base的描述、证据校验和冻结包运行入口。`history_runner.py`运行共享状态的日循环，B0由独立`b0_rebalance.py`形成年度整股订单，不误用6槽初仓器。

行情桥的`Bundle.at_decision`提供`clock, evidence, lines, historical, sectors`。调用方构造闭包`decision_factory(previous, occupied, bootstrap, completed_exits)`，返回`decide_current_pool(...).decision`。用`commit_cutoff(account, decision_factory=..., clock=..., quotes=..., marks=..., previous=..., bootstrap=..., completed_exits=...)`连接准入与资金。

`commit_cutoff`对每个推荐进行真实预约；失败者本截点临时跳过，继续补位。它不伪造持仓、Q或历史事实，最后恢复失败候选的等待记忆，确认预约以真实Occupancy反馈。返回`CutoffAck.accepted/rejected/occupancy/memories/decisions`。调用方持久化返回记忆；不要使用中间临时记忆恢复工作。初始化与退出完成事件只首次投递。关闭本体后的`account.completed`保留稳定ExitCompletion，按事件ID/游标增量反馈。

## 数据桥与执行资料的分工

| 记录 | 必需内容 | 谁负责真实性 |
|---|---|---|
| `DecisionQuote` | 稳定证券/发行人/行业ID、CNY或HKD、决策原价及known_at/source、FXQuote、QuantityRule、FeeSchedule | 价格来自原价桥，执行元数据由已冻结规则表或显式代理提供。所有报价键必须与security_id一致。 |
| `FXQuote` | cny_per_local、known_at、source_id；CNY严格为1 | 只允许决策/成交时已知的汇率。不会取未来最终结算率倒看。 |
| `QuantityRule` | rule_id、buy_minimum、buy_step、sell_step、allow_full_exit_odd、fill_step | 初次提交量与撮合部分成交步长分开。禁止全池默认100股。 |
| `FeeSchedule` | schedule_id与逐项name/rate/minimum_local/maximum_local/rounding_unit/rounding_mode/amount_basis/side/order或fill计费及stress字段 | 本组件没有真实税率或佣金默认值。每个成交窗口按历史venue提供当日有效费表，费率变更不重算前期成交额。面值计费不能改乘成交价。 |
| `FillWindow` | event/security/time、真实raw_open、施加明示滑点后的execution_price、当时FX/数量/费用规则、capacity_shares、market_open/buy_allowed/sell_allowed、sellable_at、cash_due_at、source_id、execution_basis | 日历、涨跌停、T+1、南向可交易性、过去量容量和日线事后容量判断由调用方提供。未知布尔值不允许成交。 |
| `Mark` | 原价或明确除权单位转换参考、known_at、FXQuote、source_id | 持仓用实际股数估值；CNY持仓拒绝非1 FX。保留真实原价观察时点；停牌除权时须冻结明确参考转换政策，来源记录derived_ex_reference，不充当成交价；详见RUN_PACKAGE。 |
| 现金分红 | event_id、sid、currency、净总金额net_local、ex_at、paid_at可空、source_id、entitlement_basis | 调用方按真实记录日权益股数、原币每股条款和税规则算总金额，留下依据；组件不猜每十股/每股、税或记录日库存。 |
| 到账证据 | event_id、actual at、payment_known_at、payment_evidence_id、FXQuote | `pay_dividend`需到时且证据已知；不会因过了若干日自动把缺支付日应收变为现金。 |
| 有限送转/合股 | event_id、sid、ratio、effective at、new_shares_sellable_at | 日期必须由真实字段或首轮统一冻结代理提供；新增股与原有股可卖日期分开。分数权益、供股和实物分派留给单独明确适配，当前报错。 |

行业、股票信号及排名只由数据桥计算一次。执行组件不计算趋势、改算法、改排序、改退出或自动补数。

## 固定会计与下单语义

初始账户CNY100万元。策略的新增初仓上限仍是`0.90×decision_NAV/6`，再受`0.90×NAV−存量市值−未成交gross预约`和已结算可用现金约束；费用另预留。预算与股数上限同时冻结。低开不扩目标；高开必须先满足当时实际可提交的最小量/步长，不能把不足最小量的零股当新委托。已提交委托的部分余量则按`fill_step`继续，不重复套用新委托最低量。

初仓、费用预约、现金交收分开记账。部分成交消耗剩余gross预算；如按次最低费或当日费率使费用增加，只能从free现金补费用，不能突破gross预算或借用其他订单的预约。成交窗口需按原策略优先级调用，先锁存退出再买；组件没有按收益重排权力。

净值核对为：

`available + order_reserved + settlement_locked + sale_receivable + dividend_receivable + inventory − payable = NAV`

买入待交收现金已锁定；locked与相应payable同额，不能再花。卖出所得在cash_due_at前为应收，到账后才进入available。`settle_due`重复调用不会重复到账。可用现金非负，不使用杠杆。

初始目标完成/取消后不再补仓；赢家增值超15%或整户90%不主动卖回。退出请求锁存，个股恢复不撤销卖单。退出本体清零才产生一次完成事件；未支付分红应收继续存在，不因出清被删除。

`delay1`跳过每个订单第一次本来可以实际成交的事件，休市、封板、无可卖股/无可成交量不消耗延迟；同一event_id重放不能再消耗延迟或再次成交。它不等于加一个自然日。

费用支持原委托累计最低费与按次最低费两种显式组件。cost2仅按冻结组件中的stress标记执行；rate和minimum是否被加倍分开记录，不发明全市场统一费值。成交保存当日费用分项及来源。

## 已实现、待统一冻结的研究代理

父任务已接受先实现此明确选项，但尚未把它当首轮正式协议：成交使用当时已知参考FX锁定CNY应收/应付，现金仍按显式交收日延后可用。所有Settlement/FillReceipt标记`known_trade_time_reference_locked_until_settlement`。它不恢复港股通最终结算FX变化，不能称真实券商结算。

现金分红缺支付日采用`receivable_no_reinvestment`：除权/权益生效时记应收和NAV，没有实际支付证据前不再投入。组件不会将缺字段扩成自动在线补齐任务。新增股份可交易日的代理仍待统一协议确定，代码不猜日期。

## 验证、独立审查与剩余工作

18项初版会计测试首跑通过；独立审查进一步推动区分新旧股可卖日、初始委托与部分撮合最小量、固定证券报价线路、CNY估值FX，以及连续卖单余量。又增加同截点真实预约补位和持续卖出边界。组件阶段10项资格＋20项会计＋13项入口结构，共43项合成测试通过，输出保存`test-combined-attempt-01.txt`；后续新增B0和日循环边界，当前总计82项通过，见`test-runner-combined-attempt-02.txt`。这些不是历史经济账户。旧资格测试的首次标签预期失败仍保留。

独立只读审查已确认账户钱包核对、候选预约反馈和持续卖出修复无阻塞。原Fact与趋势算法未改。审查修复不算策略或算法机制实验。

真实事件循环、逐日账、B0年度目标差额订单已实现。还需要：数据池结项、root对当前AH行业/权益缺口作有限可行性裁决，并冻结一致的实际规则及研究代理；随后才可运行获准区间并开展周期归因与四阶段主观复查。当前没有正式全池生产manifest，不能称完整历史输入齐备或首轮10账户已执行。运行入口不得绕过这些明确步骤。
