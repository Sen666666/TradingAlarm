# 为什么“小试仓”仍产生账户大回撤：代码与实际路径复盘

**当前“小试”主要是单次投入及probe池的局部约束，不是全账户逐步授资，也不是累计试错损失上限。confirmed许可、活仓资源反复释放、仅记账的亏损预算和20%才触发的ACT组合，允许账户在较高仓位下持续试错。** 这是代码与已发生路径共同支持的解释；不等于已证明某个新风险门能盈利。

按用户最新要求，本轮暂停新增回测、账户和参数测试。只读冻结源码、已有原账与审计证据；恢复实现未启动，NOT_DOWN入场质量不另开重复研究。

## 1. 优先结论：ACT管的是阶段20%，不是全程最多亏20%

实际`ACT20_BREAK`在每个CLOSE更新活动阶段峰值`peak=max(peak,NAV)`，`1−NAV/peak >= .20`便off并请求退出全部真实持仓。下一OPEN才尝试卖，仍有T+1、容量、合法数量和HL代理限制。

off时peak冻结；真实股数为0、无exits、无buys，并且原合成市场M严格超过此前63日高、当日上涨、原广度B>60%，才能恢复。恢复时peak重置当时NAV，episode加1，最早下一OPEN按原完整权限申请资金，没有账户级分批状态。ACT20_BREAK不要求FAST先关后开。代码及五次原路径、阈值/执行区别详见[ACT精确复盘](ACT_FREEZE_CODE_REVIEW_V3.md)。

No60首次2022/4/20触发时已经回撤21.49%，清到flat后为22.02%。恢复后阶段峰值重置，旧亏损仍在钱账，但不再作为本阶段峰值；纯算术100→80→64，两段各亏20%也可累计亏36%。原No60三年收盘MDD38.09%并不与ACT20矛盾。D2024/9/27恢复后，9/30买49笔，CLOSE仓位82.90%，体现“长时间等待后，恢复即大量授资”。

## 2. 生效版本与真实仓位公式

| 版本 | 实际差异 |
|---|---|
| J.v3母版 | 有全账户名义风险3%和confirmed池资金60%检查 |
| 同1709池原PVR_SLOT1 | 已继承NoAccountBudget，移除3%检查 |
| No60 | 在上述基础再移除confirmed60的迁池、请求、路由三处检查 |
| D_GROSS10 | 继承No60，仅在已知市场DOWN时增加TOTAL gross10%准入门；NOT_DOWN不加这条门 |

所以**3%检查不是No60相对同池原PVR新取消的**；不能混淆旧407池PVR、同1709池原PVR和当前两条路径。实际源SHA已与冻结full manifest匹配，见[独立源审](algorithm_risk_source_audit_v3/SOURCE_BINDING_AUDIT.json)。

mobile每次计划：

\[
\mathrm{budget}=\min(0.02N_d,\max(0,0.10N_d-V_{\rm stock,d})),
\]

其中N_d为决策CLOSE权益。2%是**这次计划gross买款**，不是全账户风险；新鲜CP1可生成后续新计划。[joint_v3.py:255](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:255)。

core随后覆写计划量：最大合法q满足假设保护价卖出时`protection_risk(q) <= .0025*N_d`，同时gross最多10%N_d。这里包含按原保护价及5bp滑点估算的买卖费，不等于最终最多亏0.25%。nextOPEN还按真实OPEN重检冻结合同。[study.py:21](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:21)、[同文件:42](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:42)。不能把mobile也称为这个core合同。

实际还保留：probe池总gross10%/名义风险0.5%；单行业名义风险1%；probe行业gross2%，confirmed行业按等级10%/20%；单股gross10%；决策NAV的10%现金留存。它们都不是“总仓位始终最多10%”，现金留存也不是按实时NAV强制卖到90%。现行路由不使用底层另一个`accept_decision`的6股/3行业通道，不能搜到未调用常量就当它生效。

并发资源定义：

\[
R_t=\sum_{\rm live}q\max(P_{mark,t}-F_t,0)
 +\sum_{\rm open/cancel\_pending}q\max(L-F,0).
\]

这是当前市价到参考线的金额，不是累计本金已冒的风险，也没有包含实际跳空尾部和全部费用。价格已经跌过F但尚未卖出的仓位，在这个坐标里可显示零名义风险，实际持仓/退出责任仍存在。[model_without_account_check.py:106](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/model_without_account_check.py:106)。资源与财务NAV不等同，未把其变化当可实现损益。

## 3. 暖启动是特例，但高风险许可不是只发生在首日

两套原账户首日2022/1/5均实际买53笔、53股票、25行业，gross899,637.52元，显式费344.80元；CLOSE股票896,010.03元/NAV996,027.71元=89.9583%，保存名义风险62,970.90元=6.3222%。原journal是50笔mobile-confirmed、3笔core-probe，日末3个core也已迁confirmed。

首日原因确实含初始化：START前行业历史状态/CP1被正确暖机继承，空账户不会把历史confirmed都重置为probe。**它不证明历史信号有未来数据，也不自动构成初始化bug。** 它证明账户本身没有“先经历有限小试，再凭自身反馈放大”的授资阶段。行业/股票技术确认与当前账户已控制住新增风险是不同事实。

持续许可同样存在，以下为原No60的10/9—12/31共60个CLOSE及严格303笔新增实际fill，不借用D的归因：

| 观察 | 原No60保存事实 |
|---|---:|
| 新增角色/池 | mobile-confirmed237笔，mobile-probe13笔，core-probe53笔 |
| 新买gross / 显式买费 | 2,837,940.31元 / 1,696.91元 |
| CLOSE股票仓位均值 / 中位数 | 74.2859% / 86.9311% |
| CLOSE并发名义风险均值 / 中位数 | 6.1171% / 7.2209% NAV |
| CLOSE并发名义风险最高 | 9.6911%，12/6 |
| 60日中名义风险>3% / confirmed gross>60% | 50日 / 47日 |
| 55个非空CLOSE中confirmed占股票市值均值 | 97.1071% |
| 后段shared_loss新增 | 222,736.23元，仍仅record_only |

303中有52笔模拟历史首次买该股、106笔清仓重入，直接通过mobile-confirmed获得资金，不以同股先有试探仓为必要前置条件。扣除10/10这个后段首个有买入的OPEN，此后仍222笔confirmed实际新买。因此不能只用首日暖启动解释后段高仓位和持续授资；也不能仅靠重新初始化行业状态声称修复。

这是收盘快照及真实fill统计，**不是盘中峰值、不是准入违规计数**。并发风险会随价格和保护线变化。原字段/逐日比率、303实际pool/role/gross/费用另经独立源审核查；少数派生均值在Decimal运算顺序下出现末尾约1e−27个百分点差异，原差异保留，公布精度相同。见[原保存事实](act_recovery_native_readiness_v3/POST60_SAVED_RESOURCE_FACTS.json)、[独审及范围](algorithm_risk_source_audit_v3/POST60_SAVED_RESOURCE_REVIEW.json)。

单笔与周转另列：303层中250个mobile的初始nominal/decision-NAV中位0.1412%、P90为0.2754%、P95为0.3287%。全部303层初始nominal金额相加303,254.16元，各自初始占比相加42.4537个百分点；这是**反复投入的周转统计，不是任一时点42.45%并发风险或最大损失**。上述6.12%/9.69%并发量又含10/8旧仓，母体不同。[原薄表](act_recovery_causal_cases_v3/POST303_RISK_AND_CONCURRENT.json)。

## 4. 多次小损失为什么不会自动停止

`shared_loss_budget=20000`，但`exhausted_policy='record_only'`。亏损负差与费用仍按原行业/episode累计，没有被迁池或卖出抹掉；只是策略不以它拒新买或撤单。[joint_v3.py:16](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:16)、[model:87](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/model_without_account_check.py:87)、[同文件:236](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/account-risk-ablation-20261031/model_without_account_check.py:236)。No60原2022/1/17已记22,092.71元、ACT仍on，当天又实际买5笔；D同日虽也超2万元，但0买，不能照搬No60动作。

资源只由活仓及open/cancel_pending剩余订单占用。卖出成交后股数占用释放；卖款须到原settle_due才可花。当前原OPEN先卖、结算、sync再新买，已有同OPEN卖款可用的原记录。仅请求退出或撤单未ACK不会提前释放，不能把这一机制说成账本重复花钱。问题是**过去失败不再占活仓资源，而亏损记录又不阻断新风险**。

行业CP1推进可将当前有效attempt内probe层迁到confirmed，要求责任已处理，但不要求每股盈利或保护线≥entry。迁池不改变NAV或全账户resources，却释放probe池余量；行业确认不等于本金已经安全。

也不能说毫无去重：原有canonical CP1 consumed、当日fresh CP1、core_epoch锁、pending exit/buy锁、行业失败后的新证据要求。缺口在于**新CP1/换股获得新许可时，没有生效的累计失败消耗约束**；新证据并不自动证明此前错误已修复。纯算术示意：若每次亏当时权益0.25%，重复100次，累计约−22.14%；这是数学例子，不是把原303笔都当相同亏损。

实际303中core53层贡献−11,161.44元，mobile250层−101,296.16元；首次68/追加85/清仓重入150层分别−45,595.78/−32,488.11/−34,373.71元。盈利84层共+106,763.36元，亏损219层共−219,220.96元，净−112,457.60元。这些已独审的原期间财富变化不是删除交易可省损。2022—2023初始nominal≤0.25%参考的1133个mobile层也已净亏188,543.81元，说明只盯少数“大单”不能覆盖主损耗。

## 5. 止损及时执行，也不等于兑现初始风险预算

mobile先在CLOSE检测旧floor，触及时请求，未触及时才向上更新I/CP1保护线。core以i_target失效退出，planning分支没有额外`close<=last_core_line`强制退出。**core的I失效是否已蕴含相同线价条件仍UNKNOWN，不能仅凭分支差异判bug。**

No60后段303层中，薄核301层在首次退出请求后的下一交易日09:30成交，粤传媒2241/通鼎互联2265两层多等一个OPEN。该分布不能证明按F价成交；受阻具体原因需原证据，未核不填。来源和追加审查状态见[后段薄核](act_recovery_causal_cases_v3/READOUT.txt)。

这301/303的原native请求及完整成交已由[另一代理直接独核](algorithm_risk_source_audit_v3/POST303_EXIT_AND_ACT_SYNTHESIS_REVIEW.json)，实际partial层为0；两例延后的具体阻挡原因UNKNOWN。初始风险兑现的描述读表则显示：mobile177个亏损层中1个因公司行动参考UNKNOWN单列；176个可比层中103个净损耗超过1R、19个超过2R，分别对应负贡献155,507.99/35,879.92元。core42个亏损层有13个超过1R、2个超过2R，但后二者负贡献合计仅212.84元。原net含费与股息/AR，初始R不含这些费用且不是动态保护线，更不是core的含费all-in合同，**比值不能叫违规或止损保证落空**。根直接从既有风险表和已审303母体独立join，分类/计数及金额一致，见[描述统计交叉核](algorithm_review_root_v3/INITIAL_R_DESCRIPTIVE_CROSSCHECK.json)。

已独审的银之杰D于10/10 CLOSE请求、10/11 OPEN卖，亏9,342.84元中请求日已亏5,546.77元，次OPEN再少3,796.07元。另有原000620层113在线已高过entry后仍亏4,886.43元，原代理两次flat-HL拒卖。故`F>=entry`不保证保本，但也不能把主亏都归结为执行积压。海能达同类追加赚钱、剑桥科技阶段回吐但全年仍赚钱，均保留为过早收紧保护的反例。

## 6. 相关性与具体机制：先修合同，不直接翻开关

已绑定实际route/request按单股、sector ID与池计算；未见跨行业相关性矩阵或共同因子限额。首日25行业或2022最多53行业不等于相互独立。**本次没有计算收益相关系数或共同因子敞口，其实际金额仍UNKNOWN。**

与小亏大赚目标最直接的设计冲突是：局部确认标签可释放probe额度，却没有生效的账户累计试错预算；正常权限可一次用满较高仓位，直到约20%阶段回撤才全退；之后等待63高，再直接恢复原完整权限。它可以同时出现熊市持续小亏、恢复偏晚及恢复后继续大量试错。

应先明确三项可实施合同，现阶段均不视为已验证候选，也未准入新回测：

1. **分开市场信息成熟度与账户资金权限。** 保留历史行业confirmed作信号输入；它不自动让全账户获得满额资金。新增试探额度应同时约束probe与confirmed，不能靠迁池绕开；已有赢家仍按原结构保护，不要求为满足新买上界强卖。首次授予、追加授予与失败缩额必须有明确的当时证据，不能只因每日新高次数或浮盈跨股发信用。
2. **把资源存量与失败消耗分开。** “退出释放持仓资源”不应自动等于“失败预算全部返还”。需要明确某一可追踪试错阶段的已实现负损耗/费用与未完新承诺共同占用预算，以及其何时凭独立新证据重新授权。预算不得随换股、迁池、重复CP1随意重置。不能直接把现有`record_only`翻为`all_new_risk`：当前shared_loss跨历史只增不减，盈利也不抵扣，固定2万元会很快永久冻结；同样不能复活已失败的F>=entry成本额度并宣称解决。
3. **将风险估计与真正退出权利对齐。** core若按某条线预算，先核该线穿越但I仍有效的增量母体、金额和赢家代价；若是同义或覆盖小就停。core仅占303净损耗约9.93%，当前不能将这项未明语义提升为主亏驱动。mobile保留CLOSE→下一OPEN与缺口风险的真实合同。账户在ACT20前的“缩新增权限”和ACT全退出应是独立动作；恢复可以分批，但不能用reset峰或不记旧失败来美化风险。

这些是需要先讲清的资金与失败反馈机制，不是以新阈值保证盈利。旧成本额度和单笔缩量均有强趋势误伤，简单恢复3%检查也没有被本次证明有效；它的市价到线坐标还包含赢家利润回吐。未解决范围、反例和实现成本前，不进行新账户或参数测试。

## 证据边界与恢复入口

直接代码、已存真实订单/成交/日账与新薄统计分开保留。source独审见[完整读本](algorithm_risk_source_audit_v3/READOUT.txt)；风险/执行语义及赢家反例见[独立逻辑复盘](act_recovery_logic_v3/README.md)；[2024完整财富归因](explanation_2024_root_v2/READOUT.md)和[后段分类财审](audit_2024_account_v2/POST_OCT8_CLASSIFICATION_REVIEW.json)继续有效。所有原源只读。

已确认：实际版本绑定、ACT规则、首日原路径、持续期No60资源/成交池、原已审303财富归因。未验证：完整盘中风险、真实排队/企业行动外部权利、收益相关性、core保护语义增量覆盖，以及任何新机制的账户收益。新增读表统计的有界审查范围以各收据为准，未扩称全历史独立重算。本轮无新回测，研究成果是定位设计缺口，不是得到可接受策略。
