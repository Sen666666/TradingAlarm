# 弹性CP距离加仓：待审查的单因素研究设计

## 状态与研究目的

状态：仅设计与既有产物只读分析。未实现候选、未运行候选历史、未修改策略或原研究产物。保存此文档不构成实现、回放、参数扫描或实盘许可。

目标仍是抓住主线大行情，普通行情避免参与或小额试仓及时退出。用户接受为趋势承担本金风险。不能把保护缓冲跨零自动当错误，不能默认利润全覆盖、单轮新增硬风险限额或恢复已否定的共享试错池。

以下候选可被审查、否决；不是已经证实有效的默认修改。原M7/M10保持冻结。

## 1. 先保留已有弹性，不重复造一层强弱评分

原M7/M10已经具有：

- 主线资格：M为真、有效未消费CP、CLOSE与OPEN整轮费后净利均为正。
- 行业强度：E = max(RS5, 0) × n/N；W = E + 已知正ΔE。前一日E未知时不伪造新增强度。
- 资金竞争：按W分配；M7以现存移动持仓K + 当前合法需求D封顶，通过原水位分配求X与行业参考目标。
- 原ADD每个CP使用2%初始轮次NAV预算，同时受单股10%、现金10%底线、容量、法定数量和参考资金约束。
- M6已经删除会被上涨市值占满的整轮4%市值槽。它不是累计本金损失限额，不应悄悄恢复。
- 当前赢家INITIAL核心与EXPANSION身份分开。普通行情仍通过原种子、试仓和退出机制处理。

因此不再给ADD乘一次E、M持续天数或“赢家分数”。这会重复计权并增加调参自由度。所有行业使用既有sector51映射和数据字段，不另造行业划分或未来赢家名单。

## 2. 唯一候选：结构风险明显变宽时软缩量

### 2.1 可检验假设

原主线判断与资金竞争不动，只减少“新买入价离本次真实保护线，比该轮最初试仓更远”的ADD下注。结构距离没有变宽则保留原预算。允许新增本金风险，允许整轮实际分层floor-net转负。

这是新增“本次结构风险距离”因素，不是利润覆盖规则，不增加单轮累计风险上限。既有现金、个股和CP预算约束仍保留。

### 2.2 只用当时既有字段的公式

本轮实际SEED买入时永久记录：

- p0_plus：实际模型买入价，已含原滑点；
- I0/A0：当时I保护线转换到当时原始价格坐标；
- p0_minus = (I0/A0) × (1 - SLIP)；
- d0 = 1 - p0_minus/p0_plus，即本轮初始结构风险距离。

当前ADD决策阶段：

- pt_plus = 当前阶段可观测价格 × (1 + SLIP)；
- Ft = 原引擎在该阶段实际将赋给新ADD的有效floor，即既有I与当前合法CP确定的线；
- pt_minus = (Ft/At) × (1 - SLIP)；
- dt = 1 - pt_minus/pt_plus；
- gt = min(1, sqrt(d0/dt))；
- 原预算B0 = 0.02 × 该轮原始NAV0；
- 候选预算Bt = B0 × gt。

“当前价格”仅指CLOSE阶段已经完成的CLOSE，或OPEN阶段已经可观测的OPEN。Ft、At也仅使用该阶段已被原引擎准入的状态，不读取当天未来CP、HLCV、未来factor或未来成交结果。

风险距离只用于预算缩放。所有手续费、最小佣金、法定买量、容量与数量取整仍由原size/fee函数处理。不能直接对最终成交股数乘gt然后随意取整，也不能把风险距离当净损失率或预测亏损概率。

### 2.3 参数自由度与防止后验寻优

唯一新增设计参数为指数，固定为1/2。初始d0是该轮真实入场状态，不是历史校准参数；1倍风险距离分界与min(1, ...)明确冻结。

平方根比完全按距离倒数缩量温和。风险距离变宽时，允许承担的绝对结构风险仍可增加，不变成每笔固定风险额。不试完以后在1/3、1/2、1或不同锚点之间选收益最优者。

本窗口已经被观察，选择这个候选本身也属于开发期设计，不声称是未见数据前的独立发现。若发生实现错误，仅能按预先冻结含义修复并记录；若改变经济公式，应作为新的研究假设，不能改完只展示最好版本。

### 2.4 时序与实现边界

- CLOSE先按当时已知状态计算B_CLOSE，再进入原独立需求D与参考分配。D以及后续资金路径因需求数量改变而变化，是同一预算因素的内生结果。
- OPEN预算为min(B_CLOSE, B0 × g_OPEN)。只能缩减或取消，不重算行业水位、不新增受资对象、不突破CLOSE冻结最大量。
- SEED数量、M/E/W、CP生成和消费、退出、M10保护、资金调拨规则均不改。
- 全部ADD统一适用，不只挑已采用M10保护或已经跨零的8轮。
- 初始锚点取真实SEED成交时的I与factor，不能取后来提高的I或终值。数据缺失、非正或来源异常作为技术阻断，不补一个有利常数。
- 部分真实成交仍按原规则消费CP；缩到无法合法成交时，保持原未成交语义。
- 不借用其他股票利润，不因另一轮亏损扣减本轮预算，不新增共享池。

## 3. 真实订单的静态例子

以下仅将公式代入既有M10决策快照，没有重放资金路径，不能称候选实际成交或收益。

|订单|初始d0|CLOSE距离|OPEN距离|最终预算系数|
|---|---:|---:|---:|---:|
|常山北明000158.SZ，10/11|40.13%|18.29%|9.21%|1.000|
|紫光国微002049.SZ，10/9|18.19%|9.51%|13.77%|1.000|
|电科网安002268.SZ，10/10|22.31%|8.59%|9.39%|1.000|
|银之杰300085.SZ，9/25|39.82%|12.56%|27.12%|1.000|
|聚和材料688503.SH，10/8|18.59%|12.43%|26.03%|0.845|
|奥特维688516.SH，10/8|15.18%|12.99%|27.49%|0.743|

年份均为2024。这些静态例子的初始锚来自SEED_FLOOR_RISK与真实BUY_SEED订单；当前风险线来自ADD_FLOOR_RISK的OPEN已知保护；CLOSE价格来自对应signal_day持仓记录；计划与参考数量来自CANDIDATES、REFERENCE_REQUESTS。

- 常山10/11原计划1400股，M10参考分配1000股并实际买1000股。该因素本身不削减它的原票面预算，但完整候选的组合资金竞争仍可能改变，不能保证最终仍成交1000股。M7同日仅成交100股，差异来自旧分配机制在不同现金与库存路径下的结果，不是常山自身提前保护退出。
- 紫光、电科仍允许原规模下注。电科原缓冲由+1018.93转-1236.25元，候选没有要求保本；不能因为事后整轮亏1955.33元再为它加特殊惩罚。
- 聚和、奥特维在9/30 CLOSE不缩量，10/8向上跳空后离保护线变远才在OPEN缩量。这既可能减少追涨风险，也可能少抓主线加速段，两种代价必须同报。
- 银之杰初始I很宽，所以27.12%的ADD距离仍不缩量。候选不保证控制所有高风险交易。

### 3.1 初始I锚定的缺点

初始I宽度不是主线质量。最初I宽的股票会被相对宽容对待，I窄的股票相对严格，未必合理。软件个案初始距离约40%，不能被包装成这类股票理应获得更多风险的证据。

该锚定假设必须接受否决。若它不能提供区别于原M/E/CP信息的实际价值，维持M7/M10原版就是合法研究结论，不应为了新增规则而实施。

候选也不直接识别假主线。若目标要求改善假主线识别或普通试仓退出，应另建单因素研究，不与本候选混合。

### 3.2 必须区别OPEN与当天CLOSE的风险线

8例跨零表使用的是跨零当日CLOSE最终有效floor，不是当日OPEN下单时可知的风险：

|ADD|OPEN已知floor增量风险|当日CLOSE抬线后的缓冲消耗|
|---|---:|---:|
|银之杰9/25|6200.39|2884.90|
|聚和材料10/8|6707.59|4454.53|
|奥特维10/8|7081.66|3361.01|

金额为元。聚和OPEN假设卖价31.4532，CLOSE有效raw floor约35.2032；后者抬升发生在当日后续阶段，不能回填OPEN。候选静态系数使用真正下单阶段已知floor。

## 4. 8例跨零ADD的实际风险收益已补齐

来源：mainline_m10_winner_giveback_diagnostic_v1/BUFFER_RISK_REWARD.json。

|目标ADD|股数|当日CLOSE缓冲消耗|该ADD实际净贡献|
|---|---:|---:|---:|
|银之杰300085.SZ，9/25|1200|2884.90|+7755.50|
|600177.SH，9/27|3200|1346.36|+622.21|
|电科网安002268.SZ，10/10|1300|2255.18|-2749.02|
|盛视科技002990.SZ，10/10|1000|824.43|-1564.61|
|兆易创新603986.SH，10/8|200|1465.39|-2179.83|
|聚和材料688503.SH，10/8|604|4454.53|-4818.45|
|奥特维688516.SH，10/8|414|3361.01|-4435.65|
|紫光国微002049.SZ，10/9|300|2997.44|-1124.01|

金额为元；8个目标lot均已全部卖出，无目标lot股息权益。奥特维原轮200股SEED对应137.60元净股息不属于此前已卖出的414股目标ADD。

结论仅为实际风险收益交换：2个目标ADD盈利、6个亏损。缓冲跨零不构成违规，不能自动推出当时应禁止这些ADD。银之杰该ADD赚7755.50元，是“本金风险可能换来真实主线收益”的直接反例。

实际混合卖单费用按股数分摊；lot贡献不等于阻止ADD之后账户可增加的因果收益，没有进行替代融资、重投或禁止ADD策略回放。上述6笔亏损不能简单求和宣称新候选能省下同额亏损。MFE限于实际观察到的CLOSE快照，不是盘中最高价。

## 5. 对照安排必须分清

主实验建议为：

**M10 + 弹性ADD 对 M10原版。**

这样唯一新增因素为ADD预算函数。M7原版同时展示，作为原主线框架参照；不能把“M10 + 弹性ADD对M7”的全部差异归因于弹性加仓。

若需要识别是否依赖M10保护，须另行批准同公式的M7 + 弹性ADD，形成完整2×2：

1. M7；
2. M10；
3. M7 + 弹性ADD；
4. M10 + 弹性ADD。

分别报告两组配对差。两对效果不同只能解释为实际路径交互，不把行业贡献差或某笔释放现金称为已识别的唯一因果来源。

“无约束基线”准确说是“无新增弹性约束的基线”。M7/M10既有现金、个股、CP预算等限制仍然存在。

2024-09-02至11/06的41日已用于观察和设计，只能称开发验证。固定10/31与11/06端点，不因结果改指数、换锚点或挑区间。后续验证区间应在查看候选结果前锁定，与既有事实扩展计划一致；事实不足按原规则停止并回滚，版本间使用共同可信边界，不静默裁剪。

既有M10 11/06 NAV为1490922.40元，M7为1479555.31元；最大收盘回撤12.928932%对13.107807%。这不是本候选结果。既有M10改善主要含资金路径让常山多买900股的影响，不能把它概括为普遍提前锁住赢家利润。

## 6. 评价目标首先是主线捕获，再看代价

### 6.1 主线捕获

- 原固定M7前20轮及常山、拓维、银之杰、紫光、钧达个案不换名单；它们是已知开发样本诊断，不用于给策略贴未来赢家标签。
- 全部轮次报告有效CP机会、实际成交数量、持仓时间、MFE、最终/端点净利和回吐。
- 报告INITIAL核心是否保留，EXPANSION是否因缩量错失主线加速。
- 报告既有M主线阶段的实际投入、持仓暴露与贡献，不能只看盈利保护次数。
- 同股票同机会的直接数量变化，与释放资金后买入其他股票的组合连锁分开。
- 不能用降低总体仓位后绝对亏损变少，替代对大行情捕获能力的评价。

### 6.2 本金与跳空代价

- F_before、F_after、增量floor风险与实际成交损失分列。F使用各lot真实生效floor、实际现金流、已确认股息、滑点与明确费用。
- 正缓冲转负不自动判失败，必须连同这些ADD换来的实际收益、MFE及尾部行情参与度评价。
- 保护触发后，跳空越过当时有效floor造成的实际损失单列；同数量、同实际触发线的假设所得与成交所得相比，不能拿后来线位回填。
- 静态floor不是资金承诺、保证成交价格或最大损失。
- 报告全路径最大回撤金额与比例、峰谷日期、恢复时间、现金、集中度、换手与费用。

### 6.3 普通行情是否仍小试错

- 报告非主线INITIAL与EXPANSION资金占用、失败轮成本、持有时间及退出延迟。
- 缩ADD释放的现金可能增加以后普通种子参与，不能预先宣称它必然减少试错。
- 本候选不修改假主线识别或原SEED退出。若需要改善这些方面，应另做单因素研究。

### 6.4 审核与否决条件

以下任一情况均应保留否决候选的结论：

- 改善主要来自少参与大行情、压低仓位，却显著损害主线利润捕获；
- 初始I宽窄造成的偏差明显超过新增信息价值；
- 大多数减量只是法定数量取整的断崖，或主要损害早期主线；
- 开发窗改善但后续固定区间不稳定；
- 数据时点、因子坐标、费用或账户核验失败。

现在不编造“允许牺牲多少主线收益”的数字门槛。先冻结评价维度，再呈现实际收益风险交换，不能只按期末NAV最高选择版本。实现审查时还应核验gt=1分支与原数量/资金路径等价、OPEN不放大、未知状态阻断、CP只在真实成交消费，以及原子回滚和source/output hash。

## 7. 尚未完成与许可边界

- 8例跨零ADD实际lot收益已补齐，见第4节；不再列为待办。
- 尚未计算全体合法ADD请求的候选预算、法定取整影响与未成交机会。
- 尚未进行任何候选完整资金闭环反事实，没有候选NAV、回撤、捕获率或改善结论。
- 初始I作为风险距离锚点仍待审查；指数1/2也属于明确的预先设计自由度，不是已验证最优值。
- 尚未批准实现、历史回放或扩大策略研究范围。此文档只保存候选设计。
- 若不采纳该候选，继续冻结M7/M10和事实扩展完全符合研究目标；不需要为了给出新规则而修改策略。

## 8. 主要证据

- M10_PREDECLARED_EVALUATION.md。
- ROUND_OWN_FLOOR_BUFFER_RESEARCH_QUESTION.md。
- mainline_candidate_v10_positive_cp_initial_protection/CONTRACT.md。
- mainline_candidate_v7_demand_capped/CONTRACT.md与engine.py。
- mainline_candidate_v5_expansion_competition/CONTRACT.md与engine.py。
- mainline_candidate_v6_mature_round_cap/CONTRACT.md。
- mainline_candidate_v3_core_reference/engine.py。
- mainline_candidate_v10_positive_cp_initial_protection_run_v1/once_20241106下的ORDERS、SEED_FLOOR_RISK、ADD_FLOOR_RISK、HOLDINGS、REFERENCE_REQUESTS和CANDIDATES。
- mainline_m10_winner_giveback_diagnostic_v1下的READOUT.md、OVERLAP_AND_BUFFER.json和BUFFER_RISK_REWARD.json。

下列SHA256仅记录保存本设计时读取的相关证据；未修改这些来源。

|来源|SHA256|
|---|---|
|M10_PREDECLARED_EVALUATION.md|f6114d54a6e227d3a4bf5d450d832f2baace89f53d943bf730491dade4393394|
|ROUND_OWN_FLOOR_BUFFER_RESEARCH_QUESTION.md|0e942588a0f9c107548dc43ab2777d353821c8e4e4e9b22bec6ac1b230a7b767|
|mainline_candidate_v10_positive_cp_initial_protection/CONTRACT.md|19934a5711f17c32208f772a6315107c9a2a0b6ddfc8cf9476b318d72737a86b|
|mainline_candidate_v7_demand_capped/CONTRACT.md|5dd19ad3696a819049e1c92ad5b1f34cb8781d20515abad93898e8d7d3d26e1c|
|mainline_candidate_v7_demand_capped/engine.py|804d56f8b5a8e4b26d5a89caac5874c037911a38c339db9c6dfd5e99882aab6a|
|mainline_candidate_v5_expansion_competition/CONTRACT.md|4405906ad553a0a159bc0b240cd6827c9435a8f528d60fd22bd5ed0d13c7c650|
|mainline_candidate_v5_expansion_competition/engine.py|54f3d42846c97e63bf79b886564e186df182c5b9a1d0b69c1a8797dec7de9fa9|
|mainline_candidate_v6_mature_round_cap/CONTRACT.md|7ea6fc192f889c75aea3c66a8b1a05eab14ffb7297ebab727d0ce8a80cb8c7c8|
|mainline_candidate_v3_core_reference/engine.py|690a3cde9121c50e5b994d79c45049441cc89a2ad47ddb478ab27ae7e05b0a7b|
|mainline_candidate_v10_positive_cp_initial_protection_run_v1/once_20241106/ORDERS.json|e5b1707109d05a1edd0a24581c6aedca6ad3fb6a81d8b0783c612327e7b0478f|
|mainline_candidate_v10_positive_cp_initial_protection_run_v1/once_20241106/SEED_FLOOR_RISK.json|af007abaa290b96e6aca2634b142a37e62ac2e9a1267b58d149ed353964a2451|
|mainline_candidate_v10_positive_cp_initial_protection_run_v1/once_20241106/ADD_FLOOR_RISK.json|58bc8c29a96a36acd499d34026a6ceb4df38ad127c9e850b68050d2497f8be24|
|mainline_candidate_v10_positive_cp_initial_protection_run_v1/once_20241106/HOLDINGS.json|4ca81aed90aac3088769fa18c6e00b415c1d346f674829c8381c427e13be5dfc|
|mainline_candidate_v10_positive_cp_initial_protection_run_v1/once_20241106/REFERENCE_REQUESTS.json|770b4c494c068ecc9ee6dc1d23e4c42924c6a7912643d39048eaca797d8b1ea7|
|mainline_candidate_v10_positive_cp_initial_protection_run_v1/once_20241106/CANDIDATES.json|27d7f552f82d7d811194616ce9aef0a2bc13357133b8ac11016444c98a38ce85|
|mainline_m10_winner_giveback_diagnostic_v1/READOUT.md|f83dc09dedd176dc05aa481580f06f4ca7307d9909d8cd36250c908dccd8e377|
|mainline_m10_winner_giveback_diagnostic_v1/OVERLAP_AND_BUFFER.json|cb6adfd7ad7b5f1932af91eeb4c304bc5b514c18518db95701bec230a4644118|
|mainline_m10_winner_giveback_diagnostic_v1/BUFFER_RISK_REWARD.json|ce44e82db428a2da4141ed18713746f1dbf3a302b0737ae5022d90cf329871f5|
