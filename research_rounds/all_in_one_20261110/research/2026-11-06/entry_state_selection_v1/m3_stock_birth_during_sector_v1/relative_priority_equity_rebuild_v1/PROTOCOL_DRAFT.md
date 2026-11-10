# A+B与fresh优先权益一致重建技术方案

状态：待独立审查的差异合同。只授权方案、只读盘点和本目录证据文件。经济执行、下载、全账户均未授权。
日期：2026-11-07。
范围：原2022出生窗，以及原2024-09-01至2024-12-31出生窗的可支持性审计。逐股生命周期，不是共享资金账户。原快入口未纳入；独立2026H1半导体出生窗不自动加入。本次仅把两个既定出生窗的已持有管理延续至2026-06-30。历史资料已见，静态NON-PIT股票池与历史实际可成交许可UNKNOWN不变。

## 结论与运行门槛

需要重建两个自身状态的连续消费者：原A_UNION_B与唯一RELATIVE_UP_PRIORITY对照。现金修订没有改变冻结A/B、I、S/M3、PVR、relative时钟，却解除了一批原UNKNOWN锁定，因而影响真实退出、FLAT、后续队列、落选股和后续权益资格。旧selected不得作为新动态臂的固定输入。

2022可先用已审402、precision24、entry10做固定旧许可回归，再在同一有限已验证经济事件表下建立两个动态臂。737/2334仅是原2432许可CORE_ONLY回归断言，含追加相应为687/2345；均不是动态baseline目标、不是完整策略胜率。任何新路径碰到未验证事件继续UNKNOWN。即使2022，也不声称所有新路径权益资料齐备。

2024尚不具备与2022同等级的已审现金事件合同。它可以立刻进行本地证据复核和技术回归；如只用现有已准入表做动态运行，须明确仍有大量事件UNKNOWN，不能用于宣称跨窗支持或否定。新查到的本地历史API行不能未经事件审查自动升级为准入。

独审通过只代表技术合同可实施；任何实现/经济执行须父任务分别明确放行。此目录不提供可运行经济脚本，不产生新收益。

## 一 不可继续沿用旧队列的实证

最新FULL_CORE_PLUS_ADD_FIXED_PERMITS中402+24+10共436条修复，432闭合，其中417条于2022年内退出。按原baseline DECISIONS.blocking_round_id连接这些路径，并取event.day>=修复exit_day：
- 1548条旧BLOCKED_UNKNOWN收据，394股，690个日期×行业队列、104交易日。
- 这些队列原始全体5025行。1548不是新增交易数，394不是新增买入股票数。
- 其中1110条原I/PVR合格；只读调用原close检查、尺寸和费用函数，1098 PASS、12最小手数/风险拒绝。
- 新入场后会再次改变后续状态，因此不能把全部1098条机械当FLAT或成交，也不能把逐日静态插回旧队列当重建。

首个明确分叉：300390.SZ天华新能，旧2022-03-16因factor变化锁UNKNOWN，修复后2022-04-12完成I退出。2022-04-29电池URFI881281队列中，恩捷手数/风险拒绝，安孚PVR51.3786保留第1槽；天华49.5175的I/PVR/close检查均PASS，应占第2槽，亿纬锂能49.2464落选。旧relative臂当天恰已选天华，因此这处旧两臂差异会消失。另有5月6日焦点科技补空槽、5月30日中信特钢替代久立特材的独立行业实例。

证据输出：RELEASE_EXPOSURES_2022.csv、AFFECTED_QUEUES_2022.csv、COVERAGE_SUMMARY.json。只读计算方法是旧账本因果对齐，不是新经济结果。

## 二 复用函数和最小改动边界

原lifecycle_v1/simulate.py的finite/true/false/lineage/flags、DayFrame、load、getmeta、fee、size、checkclose为基础。源数据、费用/尺寸、原容量算法及close可行性不改。held_close原I退出与CP追加语义不改；held_open的退出优先级、CP追加卖出、盈利门槛、单次追加和风险计算不改。

复用已审cash_dividend_402_scenario_v2/run_scenario.py：
- mark = 原现金及库存净变现值 + 本回合已确认应收。
- accrue、settle、rebase的代数与NET80假设。
- 股息不改变股数、买入成本分母、既有费用；rebase只转换addfloor/addpending及持仓fac，保留pending exit flags。
- ledger独立重算和已知派息在股票退出/UNKNOWN之后继续处理的语义。

复用precision24/run_precision.py的d_source与d_cash分离，以及每次盈利门槛日志与两现金端点动作对齐测试。不得放宽factor容差，不能用d_cash/d_ref去改原factor。

复用entry10的entry_open坐标补丁思路：已验证纯现金桥用当前已存Fnew翻译前信号保护L，原raw OPEN及费用、预算、风险和手数重算保持不变；登记库存0不享股息。

必须拆除而不能复制的旧实验绑定：
1. pub[old_round_id]、old_by定位并固定旧许可的run_round循环，改成共同经济事件查询，动态队列自己产生新回合。
2. FULL登记Q必须等于旧register_held_qty的断言，仅保留为固定许可回归；动态臂须使用自己的库存快照。
3. 单一dividend_applied/receivable针对“一次首事件”的布尔和金额，改成逐事件claim；多个事件要逐项可审且不能重复记。
4. 对任何qrec<=0一律REGISTER_OWNERSHIP_UNKNOWN的held专用分支，不能套到BUY_PENDING。已知0与无法证明的Q未知须分开。
5. 原round_id作为交易、归因、claim所属回合的审计键可保留，但不得决定公司行动事实是否有效。
6. prefix对旧路径精确相同的断言，只在回归模式使用。动态路径可不同，但每次差异必须来自已授权状态/权益/排序差异。

## 三 共同经济事件主表

生产主表使用稳定canonical economic_event_id，由sid及逻辑分配事件或经证明的合并事件身份确定，与evidence_version分离。ex/record/pay为可修订事实字段，不把证据版本或日期更正当新的经济事件。每个run冻结单一证据版本；旧来源别名、组件、合并和日期修订须映射回同一canonical ID，禁止因版本升级重复claim。sid必须包含并核对交易所后缀，证券代码相同但市场不同不得合并；不得用old_round_id或股票简称充当经济主键。相同日多次分配必须依公告证明可合并，不能任意相加。本次CSV的observed_sid_ex_key仅为旧首中断盘点连接键，不是拟生产事件注册ID。

最低字段：
- sid、event_id、event_type、record_date、ex_date、pay_date、日期语义及来源/哈希。
- d_source：只解释封存source factor；d_cash：合资格普通持有人精确税前现金；d_ref：公告交易所参考价扣减，可为空且不可默认为d_cash。
- Fold、Fnew、前一有效原价收盘及日期、source lineage、比例、factor残差和验证容差1e-11。
- coordinate_verified与其适用scope；entitlement_verified与其适用scope；unresolved_reason；来源身份检查与审查版本。
- pure_cash_verified；送股、转增及其他非纯现金不自动放行。
- NET80情景标签、非真实个人税/扣税日期/非PIT标签。

适配precision24时，ADJUDICATED_24.csv沿用的reported_pure_cash=False或旧coverage_status仅是历史匹配记录，不可再次用它们否决已审24事件。新准入依据是notice_code_verified、notice_cash_context_verified、notice_clock_context_verified、scenario_permission_basis及冻结证据。402中已审composite包括601808.SH 2022-06-17、600188.SH 2022-07-14，必须保留组件和合成事件身份，确保幂等。

两权限独立：
- 坐标通过但现金/日期未证：只能在登记Q明确为0的pending入场使用坐标桥，不给股息。若本臂此前已持有，必须停UNKNOWN，不能补猜权益。
- 现金/日期通过但source坐标未证：不得跳过factor失败。
- 两者都通过且登记Q已知：按本臂Q记权益、桥接已持仓保护，再继续原管理。
- 10条旧entry桥证明坐标，不自动授予未来held路径现金准入。402+24事实可以按同一经济事件复用，但库存和新路径结果必须重新计算。
- 后续未知event、送转、source变化、缺价照旧UNKNOWN；禁止以“这个股票以前审核过”放行另一日期。

## 四 每臂库存与claims

每个arm/window独立从FLAT开始，使用自己的BUY_PENDING、HELD、UNKNOWN、实际买卖数量、I/CP挂起动作和逐股round序列。市场信号和经济事件事实共用，只读；状态、动作和claims绝不共用。

登记日CLOSE取本臂实际core+add，不取close proxy手数、不取旧表Q、不含尚未成交买单：
- 登记收盘仍持有，即使已发I卖出指令待次OPEN，仍取得权益。
- 登记日OPEN已sell_all后无库存，则Q=0。
- 收盘才生成BUY_PENDING，Q=0；除息次开买入不享此次股息。
- UNKNOWN导致库存或登记资格不能确定时不补猜。若之前登记已确认，既有claim仍然保留。

登记、应收、派息按统一经济事件日历调度，绝非只有遇到factor变化才记股息。Q_UNKNOWN（登记资格/库存无法证明）不同于已知Q=0；不得用冻结后的静止数量推定继续持有。

claim键包含arm/window/sid/economic_event_id与所属原持仓round/lot的审计引用。每一claim分别记录登记Q、d_cash、确认额、应收、已派金额及可用日期。它不是新回合的持仓状态。
- 已确认claim在股票退出、UNKNOWN后继续结算，不用后续价格延伸UNKNOWN持仓。
- 同sid以后重入产生新round，不继承上一round股息到新round的盈利追加判断。
- settle只做cash与receivable内部转移，不再增加PnL；同事件恰一次确认、恰一次结算。
- 原固定INIT24000、SLOT48000、RISK3000与1200000参考NAV不变。股息不增预算、不增行业名额、不变共享现金规则，因为本实验没有共享现金账户。

若既定数据终点仍有有效应收，且已知pay在终点后，保留终点receivable及未支付状态，不强制提前结算、不丢弃、不转给同sid新round。股票是否闭合与现金权益是否已结算分开报告；缺pay事实或Q未知仍UNKNOWN。

NET80统一80%仅为同合同的显式历史情景，不是差别化红利税、FIFO持有期税务、税款实际扣除日期或真实证券账户。若将来改税合同，两臂同时另版，旧路径门槛稳定性不得外推。

## 五 精确事件顺序

沿用已审cash402及precision24时钟，在原run_window插入明确事件钩子，不重排原验证与动作优先级：

1. 当日ex OPEN前，先对已锁定Q的有效claim确认Q*d_cash*0.8应收。缺OPEN也不抹去已登记债权。
2. 对需要经过该经济事件的持仓或pending，按原raw OPEN存在性、source lineage及source factor验证次序处理对应坐标桥。持仓保留exitpending/addexitpending；pending用L_signal/Fnew翻译保护。
3. 原OPEN：BUY_PENDING入场；HELD先sell_all，再sell_add，最后符合原门槛的addpending。T+1、原费用、风险、容量及NOFILL规则不变。
4. 原HELD CLOSE：当日完整flags/close/I/CP检查、mark、I退出、CP保护/追加决策。不得把仅在日终已知的flags、close或CP前置成OPEN可交易条件。
5. 登记收盘库存快照在原held-close处理后取得；合法卖出挂起不清实际Q。当天close新pending不计Q。
6. 同一CLOSE在OPEN和held-close状态变化之后，处理冻结A/B出生队列。AB按原PVR降序/sid升序；relative只在可行且relative已知的位置上按fresh优先/PVR/sid重排，relative UNKNOWN保持原可行槽位置。两槽、无非UP过滤、次开失败不替补。
7. pay-date CLOSE所有信号决策后，将已确认应收转cash，下一共同OPEN视为可用。这是保守日期级惯例，不是假称实际盘中到账；预算仍固定。
8. 持仓实际sell_all完成才FLAT。当日OPEN退出后CLOSE新的真实出生边可以再参加，不回放旧收据。
9. 截止出生窗末停止新A/B，但持有管理、原可盈利freshCP追加和已登记claim继续至既有数据终点2026-06-30；不强平。

原stock UNKNOWN锁与可独立结算claims分别记账。检测到事件证据不充分不能沿用未知后的价格计算新收益。

## 六 固定许可回归与动态比较分开

阶段G0，仅技术资料和审查：本方案及只读CSV；本次完成到这里。

阶段G1，代码实现与固定许可回归执行分别需要父任务明确放行；实现授权本身不包含任何固定许可经济重放。获各自许可后：
- 桥关闭时逐列/逐动作复现原baseline和relative消费者。
- 固定原2432许可，逐条复现最新cash402+precision24+entry10结果与登记库存、股息、动作和终态。
- FULL原条件指标687/2345、86 UNKNOWN、1 NOFILL，仍保留11条空rights源旧条件结果；只有CORE_ONLY在此回归中额外排除该11条，指标为737/2334、97 UNKNOWN、1 NOFILL。不得把FULL称严格完整权益覆盖。共同闭合2334上的口径按原report复现。
- CORE_ONLY额外11条空权益源UNKNOWN必须保留；此模式仅回归，不擅自成为另一新排序臂。
- 这是工程回归，不产生新入场策略结论，不要求动态结果复现这些数量。

阶段G2，经独审通过并单独经济授权后：
- 两臂仅有A/B排序一项差异，二者共用同版经济事件表与成本/风险/管理合同，分别从窗口起点演进自身state和队列。
- 动态队列不冻结旧selected、不固定新交易数、不把同事件原盈亏自动粘贴到新round。
- 首次分叉前应可解释地一致；之后记录state_before、blocking_round、feasible ranks、fresh、股息权限、真实登记Q、追加门槛、入场与退出。
- 只报告逐股条件回合的自身分母及共同可比较分母；UNKNOWN/CENSORED/NOFILL分别列出。覆盖不对称不假设随机，按事件类型、入场期、持有长度和两臂分开报告。
- 原独立fee core拆解和完整含追加回合仍须区分；不把它们当同一策略模式，不把逐股PnL相加称账户回报。

主比较严格只有两条FULL管理消费者，各自state和queue。core只对本臂新round的真实入场/实际退出时点与初始数量做独立初始层诊断，用本臂core登记权益重算现金，并以原dated fee独立计算初仓买卖费用，不分摊FULL费用、不搬旧core标签，但不得把core另行释放的state混入FULL队列；不形成第三、第四条动态策略。若未来要core-only自身状态双臂，必须另列合同、选择分母和授权。

C不进入本轮两臂。未来先用修订AB自身state重做marker/配额预检，再决定是否另授权ABC自身状态经济实验。

### 动态执行状态与财务覆盖状态

必须分开execution_status与financial_coverage_status。前者只按原时序中的raw/source/factor、已知经济事件准入和I/CP执行事实更新；缺OPEN、未审已遇事件等按原时点锁stock UNKNOWN。后者对每段实际持有区间单列LOCAL_NO_ACTION_EVIDENCE、VERIFIED_ACTIONS_SCENARIO、COVERAGE_UNKNOWN及原因。空rights不是已证无行动，禁止给它认证完整财务闭合。

最小方案对“只有事后源覆盖不足、没有已知时点执行失败”的路径使用独立coverage标记，不根据未来退出后的审查结果倒灌改变历史state。其动作/队列只能称在当前封存输入下的条件轨迹；覆盖不足不等于真实经济零影响。两臂同时报告条件执行结果、财务证据可用结果和共同证据可比分母，不静默删空源或将其当随机缺失。对后续结论保留该覆盖不足的来源依赖，不能只剔一个PnL就宣称整个动态结果已获完整认证。

如果父任务希望一见源覆盖不足就冻结stock而改变队列，必须另行事前定义可因果确定的触发日、语义及双臂同规则并审查；这不是本最小方案自动授权的改动。已闭合区间无行动检查为actual entry<event<=actual exit；入场当日现金权益通常为0，但entry坐标桥必须另审，不能跳过factor检查。本次2024全部持仓UNKNOWN均发生在OPEN验证、原买卖动作之前，已知持有前缀只检查entry<event<status_day，status_day的已知首行动单列terminal_day_actions，不把失败日认证成完整持有或退出。入场UNKNOWN和NOFILL没有已确认持仓区间，不伪造entry_day。未来出现CLOSE失败必须另按实际阶段定义边界，不套用此OPEN规则。已知区间外的远古未解析配股保留在源报告中但不冒充当前事件；无日期未解析则保守判覆盖不足。CSV明列区间起止/开闭、失败阶段、全历史未解析、区间内未解析、无日期未解析、raw哈希及原因。

## 七 2024现有本地证据与精确缺口

此次读取原2024两臂全部2686许可、对应本地actions/原始rights以及已有巨潮缓存；未联网。

旧AB1343许可：1165闭合、151持仓factor UNKNOWN、4入场factor UNKNOWN、17缺OPEN UNKNOWN、6 NOFILL。
旧fresh1343许可：1168闭合、152持仓factor UNKNOWN、2入场factor UNKNOWN、16缺OPEN UNKNOWN、5 NOFILL。
两臂共同1162事件、各独有181。旧闭合共同1011/只旧154/只新157；经本地rights非空和持有区间无事件检查可条件支持1003/154/156，另9个唯一闭合event的权益源为空。它们只是旧已选路径的本地覆盖证据，动态新增路径仍须重新检查。

309个factor中断回合合并为167个股票×首次事件：
- 165纯现金，2送转。事件日期2024-09-06至2025-07-04；不能在2024出生窗末截掉2025持仓中断。
- 原本地vendor每个事件均唯一对应条款；只读前收/因子公式核验167个均在1e-11内。送转公式匹配不等于股权或可卖日已证。
- 原2022已审cash402/24及entry10对白名单事件的准入覆盖为0，不能按sid延续审核。
- 已存巨潮cache覆盖其中58个事件：57个唯一同ex日期行，1个双行事件；其余109事件无该股票缓存。
- 165现金中：51个已有唯一cache行，公告/登记/除息/派息顺序、原cash数、登记日=前观察日及source factor算术相符；5个精度冲突；1个同日双行需公告证明合并；108个无本地巨潮缓存。
- 57个唯一同ex缓存行（56现金、1送转）全部pay=ex，未见延后或越过2026-06-30；双行002352的两行也都record=2024-11-06、ex=pay=2024-11-07。这只描述可见缓存，不能填补108现金事件的未知pay，也不能将pay=ex设为通用规则。延后派息、退出后派息和终点后未派claim仍是必须单元测试。
- 51只是本次待独审的字段匹配候选，尚未做完整证券身份、返回完整性、实施公告语义、真实本臂登记Q及执行合同准入，不能直接计作51修复。
- 5个精度冲突：301031.SZ 2024-09-27（source .1004，cache .1003962）；002831.SZ 2024-10-11（.3302/.3302356）；600938.SH 2024-10-18（.6765/.67653）；601006.SH 2024-10-24（.1292/.12924）；600873.SH 2024-11-22（.176/.17596）。必须沿precision24三量分离逐事件裁定，不能放宽容差。
- 双行002352.SZ 2024-11-07：本地两条记录不可未经实施公告合并。
- 送转300857.SZ 2025-05-12，source总倍率1.40、现金.293，本地cache有登记/派息及10转4派2.93条款；仍缺正式准入所需新增股可卖日/分配/税务语义。688005.SH 2025-03-06，source倍率1.49、现金0，无巨潮cache。两条保持UNKNOWN；不引入送转新算法。
- 4个唯一入场事件002847.SZ 2024-09-06、600754.SH 2024-09-27、301196.SZ 2024-09-27、603233.SH 2024-10-23；它们可先做独立source-coordinate准入审查，登记Q=0时不需要伪造股息权。301196/603233无本地巨潮cache，不妨碍识别坐标证据和现金证据不同，但不能将坐标证明扩大为held现金许可。
- 两臂缺OPEN合并17个股票×日期，33个回合；单列MISSING_OPEN_2024.csv。不得用未来OPEN、理论除权价填补，不能据此认定停牌或退市。

现在可做的最小步骤：审查上述51候选的既有原件与身份/完整性，审4个pending坐标案例，并准备5精度冲突和1合并案例的精确待验证字段。其余108现金事件的record/ex/pay、精确持有人d_cash、身份与来源证据需另行取证授权；2送转继续不运行。缺OPEN和9个空rights闭合事件继续单列。任何恢复之后暴露的第二/后续事件是新的缺口，167只是旧路径首中断下界，不能称完整动态覆盖清单。

因此2024可支持技术回归及有限证据盘点，尚不支持与2022“等覆盖修复”的经济比较。即使后续批准有限事件动态情景，也必须在标题/分母披露不同窗口覆盖程度，不能拿旧38.80%或旧fresh负效应作为新合同结论。

## 八 必须通过的测试

1. 原桥关闭控制：原事件、排序、close检查、买卖动作/费用/数量、UNKNOWN及期末状态精确；代码AST差异只落在批准钩子。
2. 固定2432许可回归：两仓位模式分别对齐当前终值、动作、登记Q、应收、现金及UNKNOWN。金额容差不得掩盖离散决定变化。
3. pending跨ex：Q=0、权益0，验证L_signal/Fnew与raw OPEN定量；失败NOFILL回FLAT且不替补，未知则锁UNKNOWN。
4. held跨ex：各臂不同Q均正确；股数/买入成本/旧费不动；addfloor和addpending同Fold/Fnew转换。
5. register CLOSE已有I退出挂起仍有权益；record OPEN已退出为0；ex OPEN sell_all仍保留已登记claim。record前卖掉追加仓不计其权益，record后卖掉追加仓仍保留该批登记权益。
6. 缺OPEN/换源与应收：原验证顺序不改，claim确认/结算不依赖后续股价；未知库存不猜。
7. 支付：ex与pay同日、延后支付、退出后支付、UNKNOWN后支付各恰一次；cash+receivable转移守恒。
8. 同sid新round不收到旧round债权；同action两臂不同Q独立计息；不同交易所证券不可误合并；canonical事件升级evidence_version、更正日期或合并别名不生成第二claim，同一run锁单一证据版本；多event及composite分别去重/归属，precision d_source!=d_cash不混用；未验证第二event仍UNKNOWN。
9. strict profit gate -0.0001/0/+0.0001分别拒绝/拒绝/通过；cash不同可影响门槛，不预设路径相同。
10. 保留dated fee/minlot、T+1、24000初仓、48000标记slot、3000风险、原正成交量20观察容量和5bp不利滑点；无账户NAV/资金扩张。
11. 独立账本：每笔cash/receivable/qty/fees/buy-cash重建；sellable库存与T+1无负数，退出零库存与股息claim尾项分开。
12. 队列：OPEN真实退出后CLOSE可再入；仍held/pending/UNKNOWN不可参加；relative未知固定可行位次；行业每日至多2；次开失败不替补。
13. 前缀因果性：截断至决策时点仍一致；OPEN不读取当日收盘flags/close/CP；source factor只作封存坐标一致性证据，不伪称历史盘中可得。
14. 2024证据分级：51待审、5精度、1多行、108缺cache、2送转、17缺OPEN与9空rights记录能从源文件重算；未获准事件不放行。
15. 结果报告：两个arm分别unknown/censored/nofill、覆盖类型与持有长度；尾部同事件与同股持有区间并列，配对使用新账本重新建立。

## 九 旧结论的适用范围修订

原文件全部保留不改，以下是用途修订，不是覆盖历史结果。

| 旧结果 | 可保留 | 必须撤销或重算的用途 |
| --- | --- | --- |
| 2022旧core506/1913=26.45%至fresh518/1930=26.84% | 原factor即UNKNOWN合同的条件结果 | 不能否决权益一致的新fresh主线；新分母和自身state必须重建 |
| 旧同日行业74对26/74对14/74 | 原双方已选且共同闭合条件样本 | 不是fresh消费者效应；闭合选择偏差下须新定义配对分母 |
| 2022 core净额差+26520.75，2024 -8078.84及>=50%尾56至49 | 原账本加总及原持仓区间归因 | 不能直接当新权益合同跨窗证据；event_id不保留不等于股票行情未覆盖的纠正继续有效 |
| 20组提前及26组延后同股同退出配对 | 原冻结事后机制诊断 | 新退出/再入、数量、追加、税/费用或尾部身份变化后重建配对，不粘贴旧收益 |
| C 1/20、shadow160/236/6、未来AB冲突足迹 | 原AB状态、旧固定间隔、从不执行C的预检 | 不代表新state scope、ABC成交或胜率，也不足以继续否定或宣布重开C经济 |
| A/B身份、source坐标M3/I/relative、fresh日期、same-day与缓存标签 | 冻结市场事实和定义逻辑 | 不自动推出新动态臂可行或盈利 |
| 737/2334与任何静态拼接fresh数字 | 前者仅固定许可回归；静态差异可展示覆盖不对称 | 禁止作新策略排名、动态验收目标或真实算法结果 |

C的9例无新UP、9例非persistent及17例首次UP与旧AB同日，只保留固定旧病例/旧时间窗市场日期事实。新状态或目标间隔变更后，必须重新界定病例和分母。已发现130条C broad收据/111股处于修复退出后而旧baseline仍UNKNOWN；新AB资格、合法落选marker及剩余槽尚未重建，不能直接把130计为新C。

## 十 交付及独审输入

- PROTOCOL_DRAFT.md：此差异合同。
- FINANCIAL_COVERAGE_2024.csv：原两臂逐许可状态、rights覆盖和持有区间检查，不含新收益。
- FIRST_ACTION_EVENTS_2024.csv：167个首factor事件、source公式与已有公共缓存字段诊断，明确未准入。
- FIRST_ACTION_ROUND_MAP_2024.csv：原309个回合至167事件映射。
- MISSING_OPEN_2024.csv：33原回合/17股票日期。
- RELEASE_EXPOSURES_2022.csv、AFFECTED_QUEUES_2022.csv：1548释放暴露与690队列，不是新选择。
- COVERAGE_SUMMARY.json：计数与方法。
- SOURCE_MANIFEST.json：读源路径/哈希、计算边界及本次新文件身份；旧文件只读。
- OUTPUT_HASHES.json：本目录交付哈希。

独审应逐项复核事实/坐标与持仓权益分离、旧round绑定拆除范围、OPEN时序、claim独立性、737仅回归，以及2024覆盖分级。审批意见不得被程序解释为已授权经济；未收到父任务明确运行许可时停在方案阶段。

## 十一 从封口CSV生成的计数核对

- baseline许可1343，旧闭合1165，闭合区间本地无行动证据1157，闭合覆盖不足8。该计数绝不表示UNKNOWN路径已解决。
- economic许可1343，旧闭合1168，闭合区间本地无行动证据1159，闭合覆盖不足9。该计数绝不表示UNKNOWN路径已解决。
- 首factor映射309行，唯一事件167；分类：{"CASH_NO_LOCAL_PUBLIC_CACHE": 108, "CASH_FIELD_MATCH_PENDING_INDEPENDENT_REVIEW": 51, "CASH_PRECISION_CONFLICT": 5, "SHARE_ACTION_UNSUPPORTED": 2, "CASH_MULTIPLE_ROWS_ADJUDICATE": 1}。
- 缺OPEN映射33行，唯一股票日期17。
- 2022释放暴露1548行，394股，690队列；原队列上下文5025行；close复核{"PASS": 1098, "MINIMUM_LOT_OR_RISK_REJECT_AT_CLOSE": 12}。不是新入场数。
