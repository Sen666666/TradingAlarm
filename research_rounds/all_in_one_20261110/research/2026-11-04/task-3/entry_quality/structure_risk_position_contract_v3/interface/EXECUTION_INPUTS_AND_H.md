# v3执行风险输入与真实保护接口

本件只读原源码、原规则JSON和task4最新最小合同，不执行模型、Account、proof、runner或回测，不下载外部数据。数值情景是待冻结假设，不是历史规则补齐或策略有效性结果。

## 先钉死最新保护合同

本次读取的是task4 **upside_revision_v1/MINIMUM_CARD.txt** 及 **logic/MINIMAL_INTERFACE_AND_INVARIANTS.txt**，不是旧upside_state_v1/PAPER_CARD。

最新MINIMUM_CARD:19–38仅补“真实held、当日原core_Q、canonical CP已知缺席”的typed HELD_I_INCREMENT，confirmed-only。原CP、原CORE、旧层保护不改。41–53按原I线与原CORE0.25%单笔参考预算冻结cap，OPEN只可缩量；55–60还要求尚未实现的全账压力grant。**这些只是当前纸面合同，不是已有可调用H函数或可执行typed接口。**

新I层持有见MINIMUM_CARD:63–79、93–98及MINIMAL_INTERFACE:60–65：沿原CORE **I_target结构退出、last_core_line风险参考**，不能把stored entry x.floor当成原CORE已有的独立直接价格止损。原上游I已经在 `policies_g1.py:20–24`按旧I floor检查CLOSE失效，再由J:225–229全股退出；不加同CLOSE新ratchet后线的重复stop。旧MOBILE仍按J:235–240自己的旧有效floor，未触发才max(I,新CP)，不能静默转成宽I。

风险输入应逐层携带 `holding_contract` 与 `line_role`，不能只有一个不分来源的H：

| 层类型 | 当时实际有效的参考/退出合同 | 必须保留 |
|---|---|---|
| 原CORE | 最近决策已知last_core_line及上游I_target | I旧线先检查；entry x.floor是初始快照，不额外永久max；OPEN不读本日未来CLOSE的facts |
| 原MOBILE | 本层实际x.floor；ACT/I优先；旧floor先检查后ratchet | 各层可能不同；已有sell_layers不更新，不因新candidate撤销退出 |
| 新HELD_I_INCREMENT（未实现） | 最新卡要求新增显式kind/regime，按原I定量/持有，last_I_line镜像 | 不能假kind=core或stock_cp1；必须先做typed/ledger镜像合同，不修改旧CORE epoch |
| 未来H宽线提案 | 只有另行批准后才成为实际合同 | 先计全部改宽后责任或原子申请；不能按紧CP释放风险却用宽H持有 |

旧PAPER_CARD中 `H=max(entry冻结max(I,entryCP),current I)` 属另一个持有提案，不能拿来定义本次新I层。来源切换/segment变化也不能自动被说成原生强制退出；原直接账户出口是ACT off/I_target false。对UNKNOWN，保留最后真实责任并停止新增，而不是捏造新H或强卖理由。

## 原dated规则究竟提供什么

真实消费文件：`pvr-act-comparison-20261027/execution-rules-v2.json`。本次只读递归字段核查，顶层为schema/calendar/venue/quantity/availability/security_metadata/fee_versions；**没有limit_up、limit_down、limit_ratio、tick、halt、suspend、is_st或risk_warning字段**。security_metadata只有code/name/industry/native/par_value及来源/sector。

`build_market.py:29–45`明确是回溯research mapping：非BJ历史venue按source/current code映射，quantity映射整手；availability唯一冻结值为 `A_availability_no_historical_ST_delisting_tag`，buy_allowed=True、sell_allowed=True，属于批准研究代理，不是逐日ST/退市/停牌事实。

`market_rules.py:33–60`能按from≤date<to解析已验证或批准proxy的版本；无版本抛RuleUnavailable。这里的“dated”不等于PIT：版本没有原始known_at/公告可得时钟，不能仅凭from/to声称当时已知。当前venue/current suffix也不足以恢复历史ST、首次上市无涨跌幅期、特殊交易日或规则变更。

| 输入 | 目前能否直接取到 | v3状态/用途 |
|---|---|---|
| 当日真实涨跌停比例/有效上下界 | 否 | `UNKNOWN_NO_DATED_LIMIT_RULE`；不能由venue直接填确定比例 |
| 价格tick、合法参考价及逐日除权参考 | 规则JSON无tick/逐日limit reference；native估值另有theoretical ex reference | 严格legal-bound压力须UNKNOWN；估值参考不自动成为可成交报价或官方跌停基准 |
| 历史停牌状态/原因/队列 | 否；protocol明确未恢复 | `NOT_RESTORED`。缺bar、非observed、零量或无window分别保存，不能等同停牌 |
| buy/sell availability | 有dated research proxy，原始值可能unknown时不得补true | 保留basis/proxy/source/version；不是证明未来当日能成交 |
| 真实盘口 | 无L1/L2深度、bid/ask、排队序位、实时spread或open auction成交量 | `ORDER_BOOK_UNAVAILABLE`，5bp滑点不替代盘口/冲击模型 |
| 整手、matching粒度 | 有dated quantity mapping，approved proxy | 用原QuantityRule，不按今天代码擅自替换历史规则 |
| T+1和结算 | 原protocol A卖出可用lag=1、现金结算lag=0；实际lot存sellable_at | 压力必须尊重真实已可卖批次和新买不可日内卖，不能将0现金结算lag误读为T+0卖股 |

原slow market `history_runner.py:283–290`虽有external_columns分支，但本轮protocol选 `conservative_hl_proxy`，FastMarket:58还直接assert该值。不能因为代码支持external_columns，就声称当前source已有真实limit列。

## Wholelot、T+1、pending的真实变量

`sector_account.py:57–77`的QuantityRule包含buy_minimum/buy_step/sell_step/allow_full_exit_odd/fill_step。冻结映射为主板/创业板100起、100步；STAR200起、1步；BSE100起、1步；sell全仓可奇零，matching fill_step=1（build_market:41–44，属于原research proxy）。买单第一次提交仍要合法minimum，已提交partial remainder用fill_step，不能每个callback重收最低额或重造新单（ledger:693–725）。

T+1使用每个InventoryLot.sellable_at（ledger:727–729、750–758）；送股新单位另有可卖时钟。真实position.shares与策略layers.qty必须一致，risk账不能预先减去待卖目标。ExitOrder.remaining_target/submitted_remaining只描述退出订单，不产生已卖股数。实际fill后才改库存、产生sale settlement，due_at到了才进入available（746–809）。

J:92–128的budget/真实订单桥在callback完成及cancel ACK之前禁新增准入；open/cancel_pending的买单剩余部分持续占本金、费预留和风险。无fill、partial、cancel ACK分别处理；partial已成交数从订单转库存，不能两边计两次。

## 费用schedule的实际组成与缺口

`history_runner.py:156–162`按sid的dated venue取fee_versions，生成真实FeeSchedule。`build_market.py:47–62`给出五个组成：

| fee component | 原口径 |
|---|---|
| net_brokerage | notional×.0002，逻辑订单最低5元，basis=order |
| stamp_duty | 仅sell，2023-08-28起.0005，此前.001，basis=fill；原cost2不加倍它 |
| handling | 按venue/date；非BJ 2023-08-28起.0000341，此前另有2015-08-01边界；BJ另有.000125/.00025/.0005阶段代理 |
| regulatory | notional×.00002，basis=fill |
| transfer | 按venue/date；2022-04-29后非BJ .00001，此前历史阶段不同；早期SSE按par_value，不能用市价notional替代 |

这些是原假定净佣金与规则/历史费用代理，非用户实际券商逐单合同；BSE部分历史费用与早期SSE面值有明确proxy。排队/价差/额外市场冲击没有被这五项覆盖。5bp是execution_price中的原滑点，不能又当fee分项重复扣。

`FeeSchedule.incremental:115–155`接paid/accrued、shares/par_value，处理basis order/fill、最低额、可选maximum与rounding；真实 `_fee/_remember_fees:461–472`按同logical order累计。反复按虚拟层各自收5元、重新以空paid/accrued计算已有partial订单，都会错。原base/cost2接口只接受multiplier1或2；本合同不动已封旧成本wrapper，也不默认为任意倍数可用。假定未来清算费还须说明所用日期/已知schedule；跨未来费制无法确定就保留scenario assumption/UNKNOWN，不能冒称实际未来费用。

## .01×过去20正量：如何因果冻结

原FastMarket:54–60，positive索引的定义在14：**finite(raw volume)且>0**，不是另外经过valid/observed过滤的20行。原窗口容量是

`min(mean(last20_positive_raw_volumes_before_execution_date)*.01, execution_date_full_volume)`。

完整量/H/L是事后执行代理；J:319–322在所有资金预留之后才读取。v3授信不得调用next日FillWindow.capacity、不得看next日volume/H/L，也不得先猜前排买不到再回收其预算。

如抽取其历史部分作为待检事前provider，冻结于信号CLOSE后的已知时钟：保存sid、source/segment/raw-volume单位、cutoff_at、20个原观察日和值/源SHA、last_observation_at、positive mask口径、participation=.01、count=20及known_at。对nextOPEN而言，截止信号日已公开的正量可包含信号日；不能排入next日。少于20、源不可得或单位/CA桥不清则UNKNOWN，不填零/跨无依据数据段补齐。

原.01和20来自已冻结成交参与率代理，足以解释研究候选的依据；**不证明它是适合持仓总量或退出天数的最优参数**。若要把同一历史限额应用到总持仓而非当日成交量，这是新增risk provider语义，须明确冻结；不能声称原route本来就在限制总持仓流动性。

同一sid的承诺总量至少应统一读取：

`Q_committed = actual_inventory_shares + Σopen/cancel_pending_buy.remaining_shares + proposed_new_q`。

已成交partial不再包含在remaining_shares；pending-exit是inventory的子集，不另加一遍，也不预先扣掉。若provider限总持仓，可用于约束Q_committed；若只限新增单，则要另报既有持仓的潜在清算负担，不能把两种定义混用。数量超过候选限额只应按本增量合同拒新增；不暗中变成对健康旧仓的强卖规则。

源volume为raw shares且split跨历史观察时，原平均值本身并未承诺按今天股份单位重标。必须保留原口径，若要CA单位归一化另立显式provider版本；不能改volume单位同时仍称原formula exact。新股份、pending股数、line单位和货币责任通过原split桥同步，货币预留不因拆股扩大。

## 一步/多步跌停压力：可定义，但不是最坏界

执行情景应分开标记：

1. **VERIFIED_DATED_LEGAL**：只有sid/date的真实规则、ST/特殊期、基准价、tick/rounding和来源时钟都可得，才逐日推合法limit边界。当前snapshot缺这些字段，不能返回该状态。
2. **ASSUMED_SNAPSHOT_RATIO**：可把10%/20%/30%列为公开规则家族常见比例的**待核研究候选**，本次未进行外部规则核验，未将任一比例映射为某sid历史日的法律值。只是scenario参数，非PIT。比例及使用对象须由风险合同另冻结；不能“缺规则默认10%”。
3. **UNKNOWN**：严格需要合法bound但规则/基准/tick缺失，或不适用普通涨跌幅制度时返回UNKNOWN。缺这项的新增risk grant应DENY/NOT_EVALUABLE；旧仓责任继续在账，不零化，也不据此虚构强平或成交。

对已冻结比例序列，连续乘积 `P0×Π(1−λ_j)`只能是未经tick/ex-reference修正的压力路径示意；不等同真实合法跌停价。一步/多步须尊重T+1及不可卖期间，固定情景次数只是所覆盖延迟，不是最长停牌/最长连续跌停期限。多个sid同一场景同时承压，以同一个风险快照汇总，不能各自消耗一份独立账户预算。

“一字跌停”按原H=L代理不成交；不能一边假设locked limit-down、一边假设在该价即时卖完。若另假定后续某合法session恢复流动性，须记录清算时点、可卖量和容量假设，未卖部分继续承责。也不能直接把 `limit_down*(1−5bp)`当作该日合法卖价：滑点后的价必须重新核该日bound，否则只能标为额外跌幅压力价，不能称合法成交。

即使有完整每日涨跌停规则，一/多步也不涵盖任意长停牌、复牌跨期冲击、无成交队列、后续多日规则变化及公司行动；它是压力，不是保证最大损失。不要以参考保护价或若干limit步把未知未来责任说成已完全封顶。

## 可交付接口，不伪造可执行性

RiskSnapshot至少携带：book_version/asof；逐层holding_contract、实际qty与当前有效line坐标/known_at；库存sellable批次；pending buy/cancel/exit及paid/accrued fees；dated quantity/fee/availability/venue的source+basis；原资金/行业/单股门的真实余额与分母；causal liquidity历史窗口；price-limit/suspension/orderbook各自status；scenario定义与未卖剩余责任。

RiskGrant必须绑定该snapshot版本、typed proof、proposed q、实际保护合同与有效时钟，在原真实reserve成功时原子commit。任何必要input为UNKNOWN则不制造grant，原订单、库存、应收、ACT与退出责任照旧。压力金额和账户/行业剩余额度尚需风险主卡冻结，本审查不以原mark-to-floor0代替它，也不新增测试账户。
