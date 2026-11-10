# 实际仓位、风险额度与持续试错：只读源码及已存账本

按父最新指令暂停恢复实现及全部新账户、参数测试。本目录0新Account、0回测、0新指标、0新估值；仅抄录原源码定义、读取已审saved daily/journal及复用既有初始风险报告。下述原账事实与数学示例分开，不能把示例当策略反事实收益。

**关键结论：当前No60和D10在非DOWN时，并不是“账户先小试，成功后逐级加风险”。行业已confirmed即可为新股票直接授予confirmed资金，原全账户3%名义风险检查及confirmed60%资金检查均已移除。保留的probe小额度只约束probe池，不包住confirmed。损失记录不是累计试错上限，卖出后可继续复用资金。**

## 1. 当前实际公式，而非旧框架名称

令N为原决策/费后权益（各约束沿原程序具体时点）；P为可得价格，F为已知保护参考；所有价格/F先按原factor换同一raw单位。

| 层级 | 真实定义与约束 | 不能混称 |
|---|---|---|
| core冻结合同 | LR.resize_core：`risk_budget=.0025*decision_NAV`；求最大合法q，使`max(0,q*(reference_price-F*(1-SLIP))+buy_fee+sell_fee_at_F)<=risk_budget`，且gross<=.1NAV；次OPEN仍复核冻结q/budget和同一含费风险合同 | 0.25%为单张core合同，非账户总风险或累计亏损上限；保护线不是保证成交价 |
| mobile计划量 | J.planning先给`budget=min(.02*N,max(0,.1*N-held_qty*decision_raw_price))`，按原合法量给cap；次OPEN受原preview、可用资金/行业/池等向下约束 | **2%是本张买单gross计划，非2%风险预算**；mobile没有core同款0.25%含费合同 |
| 并发gross | `Σ活仓q*mark + Σ真实open/cancel_pending买单q*limit` | 不含已平仓的历史周转；与累计买款不同 |
| 并发nominal | `Σ活仓q*max(0,mark-F)+Σ真实open/cancel_pending买单q*max(0,limit-F)` | 当前到参考线距离，非初始成本风险、累计已亏或最大可能损失 |
| probe总池 | 资金<=费后权益10%，nominal<=0.5% | 只包probe；迁confirmed后不再占probe |
| confirmed总池 | No60移除了原60%资金上限；继承的NoAccountBudget已移除了原全账户nominal3%检查 | 不能再引用原3%或60%作为当前总硬约束 |
| 行业 | probe单行业资金2%；confirmed/expanded为10%/20%；各行业nominal<=1% | 多行业可相加；没有行业相关性/共同主题冲击折算 |
| 单股/现金 | 原OPEN单股已有市值+本单gross<=决策NAV10%；`cap+fee<=min(available-.10*decision_NAV, mirror_cash-reserve)` | 留10%决策NAV现金，非每日current NAV股票市值硬锁90%；行情上涨可越90% |
| D10附加门 | 已完成CLOSE的原510300 TR低于MA63且MA63下降时，新买后TOTALgross+真实买单承诺<=费后权益10%；允许原高仓自然退出，非DOWN撤此附加门 | 不自动减旧仓、不改变ACT，也不限制全NOT_DOWN的2024后60日 |

精确源码：`joint_v3.py`的planning/route/opening，`lot-risk-allocation.../study.py:18–20,42–65`，`budget_v3/model.py:106–116`；当前实际删除位置为`account-risk-ablation.../{adapter.py,model_without_account_check.py,route_without_account_check.py}`和`pvr_pool_feasibility/component.py`的三项No60变更。**原J.route留着的account_risk3%行不是当前No60调用的route。** 路由与模型两个实际检查点均已删该全局项，未发现此项偷偷在另一个请求层恢复。

confirmed来自行业新CP1证据推进及有效attempt，不要求本账户此前获利、此前持有过该股、当前有同股core、或试探仓已进入保护盈利。J.planning中mobile只须原fresh CP1和continuing Q，未要求held；route的mobile可直接选confirmed。模型migrate按行业level/有效性/未完probe订单ACK等处理，不读试探盈亏或盈利保护反馈。

## 2. 100万元原账户的首日事实与持续期事实

原No60第一CLOSE决策2022/1/4 NAV=1,000,000，共421个候选intents。1/5实际买53笔：**3笔core/probe、50笔mobile/confirmed**（原reserve与fill journal一致）。当天收盘股票896,010.03元、NAV996,027.71元，gross89.9583%；probe资源0，confirmed资源896,010.03元，到线nominal62,970.90元=6.3222%NAV。D10同日也相同，当时其附加DOWN门未激活。

具体单张原合同：北化股份core的decision risk_budget=2,500元，冻结cap700、budget7,975.56元；实际700股×11.235615元，初始nominal2,369.93元，买入含费7,870.63元。哈药股份mobile的budget=20,000元，cap5,400；实际5,400股×3.641820元，初始raw F=3.42094845，初始nominal1,192.71元，买入含费19,672.57元。后者2万元是gross而不是风险。

首日只说明暖启动路径；**不能以首日代替2024持续期解释**。以下单独取原No60 2024/10/9—12/31的全部60个CLOSE及303次新买：

| 保存资源统计 | 全60 CLOSE | 55个非空CLOSE |
|---|---:|---:|
| 股票gross/NAV均值 | 74.2859% | 81.0391% |
| 股票gross/NAV中位数 | 86.9311% | 87.0179% |
| 总nominal/NAV均值 | 6.1171% | 6.6732% |
| 总nominal/NAV中位数 | 7.2209% | 7.4149% |
| 总nominal/NAV P90 | 9.0893% | 9.1125% |
| 总nominal/NAV最大值 | 9.6911%，12/6 | 同左 |

60日中50日保存总nominal>3%NAV，47日confirmed资金>60%NAV；只是当前数据相对旧阈值的观察，**不称为当前合同违规，也不称最大盘中风险**。非空日confirmed占活库存均值97.1071%，中位97.5018%。该60日资源capital之和与库存值最大差1e−10，是原float镜像资源尾差，原值全部保留。

最高nominal日12/6：NAV699,756.32元，股票611,965.36元=87.4541%；probe nominal1,164，confirmed nominal66,650.26，合67,814.26=9.6911%NAV。ACT仍on，shared_loss记录已1,218,787.85元。10/9 gross最高89.1276%，但当日nominal仅2.2035%：相对10/8，NAV已减少51,028.08元，名义到线距离却随当日价格/保护线重估同时下降。此例没有拆出价格和抬线各自贡献，不能全归因某一个；它足以说明较小nominal不是前面损失被赚回或已平仓。

303次新fill=**237笔mobile/confirmed、13笔mobile/probe、53笔core/probe**。confirmed/mobile中，52笔是本模拟历史首次买该股，106笔是实际清仓后重入，79笔是已有股追加。持续期内也存在无已有同股试探仓便直接confirmed新买，不能归结于2022首日初始化。另一方面，历史首次不等于没有其他股票反馈；这里没有计算或证明账户级反馈与这些成交盈亏的因果关系。

这303笔新买gross合2,837,940.311025元，买费1,696.91元；同期全部297笔卖出费3,443.62元，合显式费5,140.54元。gross周转远大于当时本金，**不是同一时刻约283.8万元仓位**。新303层原阶段贡献−112,457.60元；原旧75层阶段贡献−54,596.72元。当前并发资源与层初始nominal分布、最终阶段财富是三个不同量，未相加冒作风险上限。

原已独审初始nominal报告只复用：303中mobile250层初始nominal/NAV中位0.1412%、P90 0.2754%、P95 0.3287%；初始保护距离中位9.85%、P90 16.75%、P95 19.10%。这不是60日并发风险；也不是把初始nominal相加后的账户风险。报告显示单层偏大不是多数主亏的充分解释，本次不复活单层缩量或R0参数测试。

## 3. 为什么退出、亏损后还能再试

资源只含活仓和真实open/cancel_pending订单；原native实际卖出后，层qty下降，sync反映该部分资金/nominal占用释放。仅退出请求不会释放持仓；仅cancel请求不释放订单，ACK后才释放。原J.opening顺序是所有卖出→settle_due→sync→新单route/reserve→真实买入；可用现金仍须等其保存cash_due_at，不提前花应收。

实际首笔卖出：No60 2022/1/6 09:30康弘药业900股，净卖款18,316.85575567元；其保存settlement due_at及实际settle均同一09:30。该原模型允许此OPEN到账后用于随后新买；不指定某笔新买究竟用了哪一元可互换现金。一般结算晚则仍要等，不把本例推广成任意现金已到账。

`shared_loss_budget=20000`而`exhausted_policy='record_only'`。`loss`记录原负交易贡献加费，累计盈利不抵消；`record_only`下不会因超过2万元而取消/拒绝新单。它不是净亏损，也不是被硬执行的2%账户试错额度。No60 1/17已记录22,092.71元、ACT仍on。后60日shared_loss从1,049,429.17增加到1,272,165.40元（增222,736.23），53个CLOSE ACT on；这些较大的毛负额可与较小的净亏损并存，不能直接当账户净损失。

行业证据继续有效时，实际资金/nominal资源随卖出下降，新的fresh信号可再获资金；没有同股失败累计次数/全账户累计试错金额的硬额度，也没有相关行业共同冲击的联合限额。这样“小单”可以频繁周转，合计造成大亏；不是单笔必有超大风险才会发生。

## 4. 数学机制示例，与原账分开

仅作公式可容纳的量级示例，假定100万元、11个confirmed行业各买4只股票，每只gross2万元，价格到线距离10%，忽略费用/跳空/交易离散。总44张单gross88万元；每行业gross8%、nominal0.8%，单股gross2%，均不超过当前行业/股票上界；但全局nominal已8.8万元=8.8%，因为没有原3%全局项。实际费用会降低可买合法数量，不能把这组示意数声称为真实可执行订单。

若其后可重复补位且连续三轮各损失当时权益8.8%，数学上`100万×.912³=758,550.528元`，累计亏24.1449472%。前两轮累计仍未达20%，第三轮CLOSE才可能触发ACT20，下一OPEN执行还可能有跳空。这只是说明局部限额和小单不推出累计小回撤，**没有证明原60日恰好按这三轮交易**，也不构成收益/止损保证。

ACT本身是episode峰值20%触发，而非全历史20%或35%硬上限：活动时peak上移，暂停后冻结；真实flat并BREAK恢复时peak重设为当时权益。多次episode亏损可以叠加；CLOSE检测和下一OPEN成交也可能穿越阈值。原No60第一次pause为2022/4/20 NAV785,066.18，相对episode峰100万元已经−21.4934%；6/17以779,819.31重启峰值；2023/7/20相对新episode峰942,596.01触发−20.6242%。不能把每次重新设峰的20%当成初始100万元最低保证80万元。

## 5. 当前研究决定与证据

恢复代码/小额恢复方案暂缓。先审“行业确认授资”与“本账户/同股真实试探反馈”之间的差别，以及持续资金复用和全局风险累计；当前事实支持这是需要解释的机制，不自动证明恢复原3%/60%或一刀切停买有效。那些限制会触及赢家，必须先看完整正反与既有失败，不在这里开新网格。

`SAVED_RISK_FACTS.json`保留两臂固定日、各年峰值、首次20k记录、原首日53笔journal、两只原100万初始合同及一笔卖出到账；`SOURCE_BINDING.json`绑定原源、脚本和输出SHA。

`POST60_SAVED_RESOURCE_FACTS.json`保留60日完整保存资源、全样本/非空分布、极值、303成交的role/pool/action、实际gross/费，以及原初始风险报告完整population原样副本；`POST60_SOURCE_BINDING.json`绑定母体。独立源审agent已直接收到这两份文件并核验；审查状态以其收据为准，不能把本派生表自检写成独审。

读数边界：saved CLOSE资源不是盘中暴露；当前nominal不是最大损失；初始risk之和不是并发risk；原层贡献不是删单可实现省损；当前行业身份不是PIT。没有新账户、参数或恢复实现。
