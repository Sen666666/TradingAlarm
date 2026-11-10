# 执行冻结补充：最终采用最小 A 合同

日期：2026-11-10。状态：仅研究合同，未实现候选、未运行history。

本补充覆盖原DESIGN.md第2.3节的“联合优化/主动给donor加帽”与第3节的“可成交保证/所有无谓卖单都消除”等过强表述，也覆盖原MINIMAL_TEST_PLAN.md中依赖这些强承诺的用例解释。原DESIGN及原ARTIFACT_SEAL不修改，保留审查轨迹。事实表、健康定义、M5角色、M7单因素控制及RESIDUAL无保量下限不变。

## 1. 最终收敛的唯一动作

P0 = 相同账户、相同当时已知输入，只删除全部新MATURE SEED请求后，按**原M7的OPEN可知规则作只读条件自然投影**。这里不是直接调用原完整执行方法：完整方法内的全日OHLC no_fill必须留在最终事后撮合阶段，不能进入选枝预测。原排序、费用、股数和保护语义不改；相位拆分接口尚未实现。

每个候选N子集也只按原M7的排序、donor卖量规则、费用/股数、reference和现金规则自然投影。不给donor主动加帽，不抢先预留ADD的钱，不换顺序、不选另一receiver组合，不求资金最优解。

只对投影结果作两个布尔检查：
- 每个当前健康且已验证的lot，候选融资卖量不得超过对应P0融资卖量；
- 每个合法ADD或EVENT请求，候选OPEN可知可提交数量不得低于P0同身份数量。
RESIDUAL没有保量下限。

任一检查失败，删除最低冻结原优先级的新MATURE SEED再投影。N为空时严格等于P0，终止不需要特殊豁免。不是先截donor，再偷偷让新的贪心路径挤出别处。

影子和各分支分别删除相应请求后，重算原D、K、X、T、envelope、sector floor和排斥关系；原W/capped_water公式不变。包含N的full参考目标不能拷给P0。

## 2. 三种数量必须分开

- bar_q[b,r,C]：分支b在CLOSE明确授予的原规则买量上限。至少绑定原planned_q、capacity、dated quantity、_ref_q、经济SEED股数、CP/票身份及分支reference。这是条件许可，不是成交预测。
- q_hat[b,r,C]：同一分支用CLOSE已知价格作完整原贪心资金投影后可提交的量，可能因现金/整手为0。
- q_hat[b,r,O]：OPEN当时已知信息重核后、进入原事后撮合判断之前可提交的量，受该分支bar_q约束。不是最终成交量。

因此：
q_hat[0,r,O] <= bar_q[0,r,C]，
但不保证 q_hat[0,r,O] <= q_hat[0,r,C]。
价格和条件预测现金变化时，shadow OPEN可以比其当晚投影提交更多。不得把CLOSE“投影买不到”写成“没有合法CLOSE请求”。

### 对父级问题的直接回答

**可能。** 某ADD在shadow的CLOSE原_ref_q上限为正，但当晚资金投影为0；selected-full也可能没有给它可提交量。OPEN变化后shadow能提交该ADD，而full分支受自己较小的_ref_q/资金/target限制无法跟上。

处理：
1. 双端条件候选簿必须在CLOSE收录shadow及所有允许回退分支的receiver，不仅donor。
2. full分支不能借shadow的bar_q、CP、reference、floor或现金字段来临时补买。
3. 若full的自然OPEN投影达不到shadow q_hat，则该分支失败，按已冻结退让序列选下一分支。
4. 最终shadow分支本来就有该请求和数量许可，进入它不是OPEN新造请求。没有任何CLOSE分支授权的sid/round/CP/原signal身份，一律不得OPEN新开。
5. 若CLOSE比较的shadow投影量本身已经>0，CLOSE获选分支必须提交不少于它；不存在“忽略这个正量，留到OPEN再补”的合法状态。

## 2A. 健康集合H必须来自共同快照，绝不分支重算

CLOSE的共同锚点：原CLOSE的I/CP更新、已知保护锁、原权益/收盘现金处理、事件/票身份更新已经完成，任何候选融资/买入投影尚未发生。

OPEN的共同锚点是**OPEN可知的条件预测prefix**，不是冻结引擎已经跑过no_fill的真实prefix输出：只用当时已知的原权益桥、保护判定、OPEN价格/滑点/费用和股数规则，按可提交OPEN成交假设预测强制退出，再预测现金、残余库存与info_open；不调用整日OHLC no_fill。在任何候选可选融资或买入之前冻结一次共同预测状态。预测强制退出后不存在的lot不再是该条件投影的可选donor。

原exit_open本身也调用全日OHLC no_fill，故不能先调用原exit_open、把其实际模拟现金/H作为锚点。真正实时已观察到的执行回执与历史日线no_fill不是同一种信息；本次历史研究合同只采用上述条件预测锚点，不把后者假装成OPEN已知回执。

从该锚点为每个现有lot冻结：
- health_snapshot_id、lot/round身份、共同条件库存；
- 同一round已发生现金流、股息权益及共同条件prefix预测的退出现金/残余库存，按同一OPEN报价和dated费用/滑点计算的条件清算净利；预测部分必须单列，不能记作已经真实成交；
- 同一post-SEED CP/信息确认证明、当时I/CP有效保护、退出锁、unknown及原融资资格；
- H_close或H_open布尔与逐项原因。

**本次P0及全部PN必须引用完全相同health_snapshot_id和H映射。** 融资卖一层会改变现金流/费用，买新层也会改变库存，但这些分支内变化不得重算本次比较用H。否则同一lot可因某分支先交易变成“不健康”而逃过y_hat约束。

每个OPEN相对当日共同快照重新计算H一次是合法的；不能把前夜H当永久角色。但不能在同一OPEN的不同分支之间改它。CLOSE同理。所有H判定都在原同尺度报价/权益桥下，不能用后来CLOSE或事后匹配结果补证明。

逐单成交后实际净利/H变化可另列为诊断，明确标记POST_TRADE_DIAGNOSTIC_ONLY，不参加本次不挤出比较。候选新生成的lot不能加入共同H集合、改变其他lot待遇或作为本次donor。

## 3. CLOSE冻结有限分支，而不是两份字段的并集最大值

用完整原排序冻结N的删除序列。从最先通过CLOSE比较的选中子集起，继续预生成到空N的有限后缀，每个子集都只跑一次相同原规划的只读自然投影。每个分支均有**独立**receiver、donor、reference、预算和投影结果。

- 分支保留原排序删除序号、N身份集合、CLOSE两项比较结果。
- 只允许CLOSE比较通过的分支成为OPEN条件执行分支；中间失败的分支只留审计记录，不因OPEN有利而重新启用。
- 空N分支就是P0，始终在已认证的候选集合；若源未知使P0不可认证，沿原atomic block，不能宣称一定可交易。
- 这是一条最多|N|+1的固定删除链，不搜索任意seed组合，不按收益择枝。
- 选中分支之前已经被CLOSE删除的N，不会在OPEN复活。
- 请求/lot并集只用于预检、列出所有潜在身份及原数据需要。它**不提供执行数量，也没有一个可用的跨分支max上限**。

具体冻结字段见EXECUTION_FREEZE_FIELDS.json。最关键的约束是：每次执行必须选一整份branch_id，所有reference、receiver和donor字段来自该同一分支。禁止用full的receiver上限、shadow的donor上限，再挑二者更低sector floor。

## 4. 每个receiver怎么冻

全局稳定身份：
request_id、sid、kind、原signal_day、plan_day、round_id（ADD）、cp_id及cp_date（ADD）、ticket_id（若有）、allocation_phase、event_id、quote origin和factor lineage。请求身份不可用当前日期重建。

分支专属：
- 原资格状态和拒因、原planned_q/capacity/_ref_q/econ_q、dated quantity rules。
- bar_q_close及其来源；不存在、被删除、原不合法、原_ref_q=0必须显式为0，不能用“并集中存在”默认授权。
- q_hat_close、原rank、分支reference/stock/event/attempt/cash约束、费用/报价依据。
- CP/I/因子身份、event资格和spent快照、原资本角色（只有成交时按原规则落lot，影子不落lot）。

OPEN：
- 数量只能按该branch的原冻结上限及原OPEN规则重算；不得扩量、换CP、换信号身份或新添票。
- 限于已知OPEN来源、价格、旧CLOSE保护/计划、dated metadata、进入OPEN前真实到账余额与共同条件预测保护退出余额，二者分项标明。不取当日CLOSE的M/E/F或未来CP。
- OPEN q_hat可能高于同分支CLOSE q_hat，但不能高于其明确冻结bar_q。提高到已有条件许可不是临时新买。
- 最终选枝后所有状态变化只按原真实生命周期执行一次；scratch投影没有副作用。事件spent按原真实成交计，原EVENT的priority_attempted可能在真实尝试时就消费，即使未成交也不能一概保留。CP consumed仍按原成交语义，不能把真实尝试的EVENT消费规则简写成“只有成交才更新”。

## 5. 每个donor怎么冻，怎样防止max绕过健康上限

全局稳定身份：
sid、round_id、lot_id、原capital_role、close_qty、bought、T+1状态、原mobile/frozen数量、当前有效I/CP保护、来源/因子/公司行动桥、健康状态及证据。

分支专属：
- 原donor排序rank/reason；
- 原plan_transfers生成的max_q、frozen_lot_qty、close_sector_floor；
- 分支reference状态/hash、原sell规则、fee/slippage、CLOSE预计卖量/净款；
- CLOSE自然执行投影所得y_hat_close，及与P0同lot的比较结果。

禁止这样做：
max(full.max_q, shadow.max_q)作为实际卖量许可。
它会把两个互斥分支合成一套不存在的筹资方案。

正确做法：
1. 在分支b里，自然OPEN投影只能用b的原max_q、b的floor和b的receiver/cash计划。
2. 同时从shadow独立原投影得到y_hat[0,l,O]。
3. 若当前H(l,O)=1且y_hat[b,l,O]>y_hat[0,l,O]，**拒整个分支**；不得仅截该donor然后重做另一贪心路径。
4. 换下一个已冻且CLOSE通过的分支。选中后每个健康lot的实际“可提交融资卖量”自然已满足shadow界。
5. y_hat[0,l,O]=0的健康lot，任何N分支的正卖量都不通过。并集里存在shadow或full记录不能改变它。
6. 原强制I/CP退出仍先执行，不纳入“可选融资卖量”比较。UNKNOWN沿原规则，不借此扩大许可。

健康是当前状态，不是永久资本角色。比较在CLOSE和OPEN各做一次；OPEN不能靠使用后来CLOSE的数据证明健康/失效。dated单位或公司行动转换只走已认证原桥，未知不得换单位绕过数量上限。

## 6. OPEN选择与事后撮合分相

### A. OPEN已知选择阶段
先在只读副本上完成共同条件预测prefix：原权益桥/保护判断、按OPEN可提交成交假设预测退出及现金/库存，再预测info_open；绝不调用全日no_fill。然后在任何候选融资和买入之前冻结一次条件H及health_snapshot_id。所有分支只引用该H，不在分支卖出/买入后重判，也不读取随后真实模拟prefix的结果来重选。用这个相同条件快照：
1. 投影shadow，得到q_hat0、y_hat0。
2. 按CLOSE已冻顺序逐分支自然投影。
3. 通过原已知约束和两项不挤出比较后选择第一份分支。
4. 没有合格N分支则选择shadow；若shadow原先因未知不可认证，按原block处理。
5. 在任何真实订单之前完成以上比较。这里可消除的是“**本次新增N造成的边际挤出**”，不是重新修复全部M7筹资/撮合。

### B. 最终原执行与事后撮合阶段
原ST no_fill读取当日OHLC；这些整日结果在OPEN不可知。它既出现在强制exit_open，也可能出现在donor/BUY撮合中。不能提前调用来构造选枝现金/H、取消receiver、缩donor、换枝或重分配。

选枝完成后才运行**原真实模拟prefix + 选定分支的原执行**，保留所有no_fill位置与撮合规则。原prefix结果与条件预测可能不同；原后续贪心执行据真实模拟现金自然得到的q/y/H也可能不同。若事后模型判任何强制卖出、donor或buy no_fill：
- 该结果只进入原撮合/实际账户输出；
- 不倒流到shadow、不重新选枝；
- 不撤回已经执行的donor，不事后换另一个receiver；
- 不保证最终ADD fill量仍达到shadow“可提交量”，也不保证实际融资卖量逐lot仍等于条件y_hat。承诺对象是同一OPEN已知条件下的q_hat/y_hat不挤出比较，不是未来撮合实现值。所有偏离单独记录原因与数量；不能把不同实际现金/H再喂回选枝。

原no_fill的全日数据依赖仍是继承模型限制，不因新增影子而获得PIT认证。本研究不替它修撮合规则。需要实现的只是明确隔离OPEN可知条件投影与原最终执行，不能伪称现有M7已有安全可调用的完整投影接口。

已封存93日执行边界日志中BUY_NO_FILL/DONOR_NO_FILL/SELL_NO_FILL三类记录共0；这只解释当前案例未出现该偏离，不允许未来选枝利用这项事后统计。

## 6A. 新退让N的资本等待、原生命周期与preflight

删N只作用于本次只读规划working set，**不删除真实pending、不消灭ticket、不创建新round**。未来实现必须有单独明确的资金等待结果FUNDING_NONDISPLACEMENT_WAIT，不能伪造REFERENCE_CAP、结构False或成交失败来借原工具链吞掉请求。

等待记录必须保存：
- 原request/ticket身份、sid、signal_day、birth_type及原round/attempt关联；
- 原nav0、attempt budget，不能以重试日NAV重定预算；
- 原origin/source lineage、ifloor、factor/current_factor与last_verified_day；
- 原allocation_phase、event_id、原经济股数/最低股数、capacity、planned_q及已有保留票状态；
- 本次decision_day、拒绝的branch_id、触发的不挤出比较、原rank；
- 未成交且未新建lot/round的事实。

原phase作为本次被退让快照保存，后续是否按原生命周期重新分类只能遵守原prepare/refresh规则；不得为了绕限制把MATURE改EVENT/RESIDUAL，也不得把EXPANSION改INITIAL。原票身份、nav0与budget不因合法的原phase刷新而重建。

真实OPEN对这些等待票仍完成原本应做的结构/来源生命周期检查：
- 已知原结构False，按原原因取消；
- unknown，按原原因暂停或原block；
- 因子/权益桥等沿原预检，不能因本次不买而略去；
- 真正仍合法但资金竞争不通过，才记新的资金等待，下一次沿原票身份重试。
本合同没有实现这项等待接口，synthetic必须证明不丢票、不扩大预算、不伪造原拒因。

**保留全部原preflight targets。** 在删N之前保留原active、pending、retained及原经济预检目标；条件分支candidate并集只可能补充明确需要的目标，不能拿筛后的N集合缩小原校验范围。不得因删票绕过原Q0/持仓桥/来源/公司行动核查，403受限外部补源仍暂停。原失败回滚和scan_restored_targets规则保持。

EVENT与CP副作用：
- 所有scratch分支不消费priority_attempted、event spent、CP、ticket，也不更新真实保留状态。
- 真实最终流程按原规则消费：EVENT的priority_attempted可能按真实尝试即消费；event spent按真实成交；CP consumed按原实际ADD成交。
- 新MATURE退让本身不能消费EVENT资格或CP，也不能阻止另一真实EVENT尝试依原规则消费。
- 事后no_fill仍原位处理，不能借其结果让此前真实尝试“未发生”。

## 7. 保留原筹资整数残余，不假称每笔卖款都有真实ADD归属

P0完全保留原M7：原transfer按desired筹资，之后受现金/整手限制，可能仍有请求q_hat=0和剩余现金；不把desired当成q_hat。

已保存原M7实例：
- 11/7 OPEN desired=583,732.339121084111，净筹资533,037.657450020700，剩余缺口998.63775239384625。000700 EVENT经济1000股成本约7,609.29，但最后cash_reserve仅6,610.65，实际q=0。
- 12/13 OPEN desired=452,673.469991770182，净筹资402,554.1257415408475，剩余缺口4,058.17962541000010。600050 MATURE经济1400股成本约7,429.19，最后cash_reserve仅3,371.01，实际q=0。
这些证明demand/筹资/最终整手量不是一回事，不证明这些日子的全部卖款无用途，也不是新shadow已经算过的结果。

如果某个P0确实在没有可提交A时仍按原规则卖了健康lot，y_hat0仍原样保留。候选N可能在不增加该卖量的情况下使用它本来留下的现金。本规则只能诚实承诺相对未改M7影子“不额外挤出”，不能声称所有健康donor现金都为真实ADD/EVENT而卖。

本版不增加“最小合法筹资前缀”、不清理phantom、不设置空N豁免。若以后要修原M7这项边界，必须独立执行修正对照，不能混入当前单因素。

## 8. 追加必测与限制

未运行、不得宣称PASS：
- shadow CLOSE投影0而原_ref_q>0，OPEN q_hat转正；full缺同量时必须拒枝，不能借shadow字段临时补买。
- 分支原max_q与自然投影卖量不同，跨分支max会越shadow；只能拒枝，不能截卖量改变原路径。
- 某删N中间分支CLOSE失败而OPEN有利，仍不得越过冻结CLOSE状态。
- 原排序自然投影造成ADD不足：删除N，禁止预留/调序偷偷把ADD救回来。
- phantom/整数残余保留，N为空严格等于P0；不能以更“干净”的shadow代替原M7。
- 强制exit_open、donor及buy的no_fill全在最终原执行/事后撮合阶段；共同预测prefix也不得读全日OHLC，无事后重选或donor回滚。
- 所有分支只读无CP/票/event状态消费，最终commit一次。

追加等待接口测试：退让N保留原身份/nav0/budget/phase快照；真实OPEN False取消、unknown暂停；全部原preflight targets仍检查；EVENT真实尝试即消费的语义保持，不以scratch或no_fill伪造重试资格。

本附录只修正合同，不实现分支规划、不启动历史测试。现在的事实核验不等于上述新机制的synthetic通过或经济有效。
