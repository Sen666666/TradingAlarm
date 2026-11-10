# M7 新 SEED 入场机制与诊断
## 结论
本轮不建议冻结任何新入场过滤器。两条原候选均被具体反证削弱：
1. G1「MATURE 新 SEED 要求行业 5 日绝对收益为正」对冻结请求零区别，撤回。
2. G2「已知亏损后收复旧轮最高收盘再入」只覆盖少部分晚期损失，混淆融资迁出与结构失效，并显著推迟真实赢家，不推荐实施。
经父线程另行授权，仅追加一次两相邻日 M 资格检查（M2D），不扫 3/5 日参数。它有区别，却同时延迟 9/24 启动中的大量成熟新参与者，尚不足以冻结。
最有价值的新事实是：晚期 412 个 retained MATURE 入场多数不是长期排队，而是初次 EVENT/RESIDUAL 小试未成交、1–5 个交易间隔后转成 MATURE。其中 261 个等待期间既无 I 线抬升也无新 CP receipt。但这是机制现象，不是它导致亏损的证明。

## 1. 范围与可观测性
- 仅使用本地冻结文件。无网页、网络、CNINFO 或替代来源读取。
- 原基线 mainline_m7_cash_batch_design_v6/once_20260630，认证止于 2025-01-20，共 93 日、1677 个实际 SEED 轮、3596 单。晚期新轮从实际 2024-11-07 OPEN 起共 954 个。
- 检查原 OUTPUT_HASHES：ORDERS、ATTEMPTS、EVENT_REQUEST_PLANS、SECTOR_DAILY、DAY_LEDGER、HOLDINGS、EQUITY_EVENTS 全部相符。
- 实际买单一律按 plan_day CLOSE 判定。9/24 OPEN 只能用 9/23 CLOSE，9/24 新收盘证据最早支持 9/25 OPEN。
- 窗口已经被观察，全部是开发诊断，不是样本外验证。价格、行业映射、公司行动时点及非 PIT 限制继承原基线。
- 被标记轮的「原净利」包含其原始 ADD、退出、费用、已确认股息和终点估值，只用于机会成本对照，绝不等于删去它就能得到的资金闭环增益。
- G2 的请求分类用实际基线已发生的亏损历史。假设过滤后，这些历史可能改变，所以不是反事实账户。
- 未改正式或冻结引擎；新脚本只写本诊断目录。

## 2. 真正入场状态机
### A/B 与行业事件
joint51_candidate_v9_facts/engine.py:30:
- A：行业 state 从 0→1，个股当日 stock_state=1。
- B：行业前后均 1，个股从 0→1。
- UNKNOWN 不制造 A/B。A/B 后仍要 I 真、有效报价、复权因子/保护线、容量、最小量等原门槛。

mainline_candidate_v4_known_sector_fix_v2/engine.py:29、89:
- 行业 0→1 创建 event_id，初始试仓事件上限为出生 NAV 的 2%。
- 事件状态随行业 state 变 ACTIVE/CLOSED_FALSE/PAUSED_UNKNOWN。
- 尚未优先尝试的事件，满足原知识条件，可将 SEED 标为 EVENT。
- 否则只需当前事件 ACTIVE、M=1、E>0，SEED 就成为 MATURE。
- M=0 的同事件其他 SEED 是 RESIDUAL；不符合为 PAUSED。
- 所以 MATURE 是资金分配阶段，不是「该个股已证实成熟趋势」。新个股不必先拥有本轮 CP 或盈利记录。
- MATURE SEED 在 M5 计为 EXPANSION；EVENT/RESIDUAL SEED 才是 INITIAL。不是只有 ADD 才属于扩张。

### 既有 M/E/W
mainline_candidate_v1/engine.py:20:
- Q：行业 state 真，并且当前和前一交易日行业真个股各至少半数。未知按上下界三值逻辑判定，不直接补零。
- 慢路径 S=Q & RS10>0 & RS20>0 & 行业10日收益中位数>0。
- 快路径 F=Q & RS5>0 & RS5较前日改善 & 行业5日收益中位数>0 & 至少半数成分股创前20日收盘新高。
- M=S 或 F；若 M 真但 RS5 未知则 M=UNKNOWN。
- E=max(RS5,0)*n/N。
mainline_candidate_v5_expansion_competition/engine.py:33:
- 分配权重 W_alloc=E+max(E−前日E,0)，前日 E 未知不额外奖励。
- 它不同于原信号表中名为 W 的布尔弱化状态，报告中不可混同。
mainline_candidate_v7_demand_capped/engine.py:43、77:
- 现有 M7 已按独立合法需求封顶分配；不是缺少 E 加权。
- 行业慢路径理论上未强制 R5>0，但实际本样本所有 MATURE 请求都已 R5>0，理论漏洞不等于真实损失原因。

### 代表性与 CP
mainline_candidate_v4_known_sector_fix_v2/engine.py:63、142:
- stock_excess5=该股5日复权收益−该行业有效股5日收益中位数。
- 个股需连续6根有效日线、相同source/segment、价格和调整因子一致；比较行业中位数继承冻结原口径。
- excess5、stock_true_streak、capacity_value 用作代表排序，不要求 excess5>0。
- 同行业先排 ADD，再排已知分数 SEED；已知但负分 SEED仍可以成交。
mainline_candidate_v3_core_reference/engine.py:53 及 M6 修改:
- CP 只有实际 SEED 当日或以后形成，且当前保护未破、I有效、M=1、本轮净利>0，才支持信息确认/ADD。
- 信息确认还要次日 OPEN 再核；资金是否充足不决定信息确认。
- CP 在实际 ADD 成交才消费。M6取消成熟轮4%名义槽位，但保留单次2%原始NAV等规则。
- 不应以「已有当前收益」重新限制新 SEED；用户接受趋势本金风险。

### retained 不是亏损重试记忆
allocation_ablation_v1/allocation_rules.py + mainline_candidate_v1/engine.py:355:
- retained 是原 A/B 因资金约束未成交的票，保留原 signal_day、NAV、预算、origin、factor/ifloor身份，不产生新 CP。
- 每日核 source/factor/公司行动；source变更取消，缺未核桥接不擅自通过。
- I/行业/个股已知 false 或保护破位取消；UNKNOWN 暂停。I 线只上调。
- 实际成交后票 CONSUMED；此后亏损平仓并没有专门的旧结构失败记忆。未来新 A/B 可再开一轮。
- 同股重复失败不能直接说成「原地很快买回」：另一已封存序列表显示多数相隔多日，且大多数确实已经出现新的 A/B。

## 3. 两条原候选及等待语义
### G1，已否证
公式：仅当 kind=SEED 且 allocation_phase=MATURE，增加 sector.return5_median(plan_CLOSE)>0。
结果：全部14624条冻结SEED请求、1677个实际SEED均不受影响；晚期479个MATURE全部通过。无实施价值。

### G2，待否决设计
其准确名称应为「已知亏损后旧高重获门槛」，不能叫已验证结构失败识别。
- 亏损判据使用实际全平时已知本轮订单现金流+此前已确认ACCRUE_NET80权益。
- H=该亏损轮原signal_day至最后持仓CLOSE的最高有效复权收盘。
- 同股新SEED要求当日C>H；未解锁时后来的失败不能降低H，严格上穿才清除。
- 股票级记录，不占用其他赢家的风险空间，不采用亏n次暂停，不全市场冻结。
- 现有原始诊断包括所有净亏轮。未来若设计「仅结构失效」版本，理论上应把 I/CP/行业退出与纯资金迁移分开，并在冻结前定义，而不是按收益挑选原因。本轮不再追加这种择样重测。

若继续研究，必须是显式 STRUCTURE_WAIT，而不是删掉一次A/B就假设将来还能买：
1. 保留原票身份、signal_day、原NAV/2%预算；不为等待重新出生。
2. 每个CLOSE继续原source/factor/公司行动桥接、当前容量/dated lot、I线递增检查。
3. I/行业/stock明确false、保护破坏或source变更取消原票；UNKNOWN暂停，不能凭unknown解除H。
4. 等待本身不占现金或新增风险；事件优先权/预算不因等待重置；事件已false取消后须新A/B产生新票，股票H记录仍保留。
5. 结构条件在CLOSE恢复后nextOPEN才能执行，重新走全部原开盘报价/限价/容量/费用/保护/预算/现金检查。
6. 等待日phase必须按当前真实事件和M状态重算，不能永远把原EVENT标签冻结为EVENT。
7. G2从2024-09-02开始没有更早实际账户亏损记忆，冷启动边界须明确。未知旧高不得用部分有效K线凑出。
8. 后来出现的权益或会计修正只能按发现日记录新事实，不得改写历史当晚入场决定。

这是一项尚未实现、未冻结的完整票状态机。WAIT_TIMING_FOCUS仅核日线/现有I、行业、stock、source条件与nextOPEN保护，不核完整资金/事件分配及成交。

## 4. 9/23–9/30真实时序
实际OPEN中的SEED：
- 9/23：10 EVENT+23 MATURE，G2挡1个中国太保；G1不挡。
- 9/24：36 EVENT，all-in 280781.25；28 MATURE，all-in 212746.87；G1/G2均不挡。
- 9/25：3 EVENT+32 MATURE，G1/G2均不挡。
- 9/26：14 EVENT+16 MATURE，均不挡。
- 9/27：37 EVENT+13 MATURE，均不挡。
- 9/30：10 MATURE，均不挡。
以上实际OPEN共222轮，all-in1825866.14。不要把「9/23–9/30计划CLOSE的195轮」（包括10/8开盘）和实际OPEN口径混用。

关键股：
- 常山北明：9/13第一次EVENT，9/18 OPEN退出−94.00。旧H=11.42546；9/18 CLOSE=12.04555已超过H。9/23 CLOSE信号、9/24 OPEN第二次EVENT仍可进，原轮净32513.29。
- 拓维信息：9/23 CLOSE→9/24 OPEN首次EVENT，原轮净19147.37。
- 银之杰：9/23 CLOSE→9/24 OPEN首次EVENT，原轮净10982.60。
- 上述三只通过不代表整个9/24行情机会无损。
- 中国太保：原9/20 CLOSE→9/23 OPEN成熟新轮被G2挡。9/24 CLOSE才重获H，若原票一直等待且其余条件维持，最早9/25 OPEN；该开盘较原9/23开盘高10.78%。只取消A/B后，冻结基线下一请求到10/22，这不能冒充实际首次可恢复时点。

## 5. G2误入/重试与机会成本
晚期954轮，G2标记98轮：
- 原路径净−11868.14，包含毛亏19541.48、同时牺牲毛利7673.34；85已平、13未闭。
- 它仅对应晚期总损失的小部分，且不能解释成可挽回11868.14。
全窗标记112轮的原净反为+11813.34，原毛利33607.68高于原毛亏21794.34。

反例：
- 聚和材料：原9/27轮在10/14行业false退出−4081.13，不是融资迁出。旧H90.33957；10/23 CLOSE82.62381，挡原10/24 MATURE新轮（原净+21655.88）。
  10/25 CLOSE89.86718仍不足，10/28 CLOSE106.22098才过H。若留WAIT票，最早10/29 OPEN110.22507，较原10/24 OPEN高34.62%。不能以只等到突破就说没有错失。
- 香农芯创：挡10/24成熟轮原净+983.94，等待到10/29行业false取消；又挡11/12轮原净−1052.24，11/13个股false取消。一个旧H同时抑制有利/不利重入。
- 中文在线：原12/3−786.20与12/11−717.25两轮都在旧H下；对应待票在12/3个股false、12/16行业false取消。
- 东方明珠：挡12/11轮原净−3277.35，但H来自11/8「CURRENT_NON_MAINLINE_SEED_RETIREMENT」融资迁出−189.44。因此不能把此项描述为结构失败识别成功。
- 银之杰：1/16 CLOSE237.45175仍低于10月旧H308.49199，原1/17新EVENT也被挡，至1/20仍待修复。这个末端原净+183.41未闭合，不能评价最终成功。

主要亏损行业被G2覆盖的原净：
- 金属钢铁：5轮−417.86，全为终点未闭合，远不能解释行业−16795.05。
- 游戏传媒：8轮−4967.71，其中东方明珠的触发原因是融资迁出。
- 医疗服务：1轮−186.83，远小于行业−13597.45。
- 自动化与机器人：4轮反而+365.55。
- 证券保险：2轮−280.80。
- 电子元件材料：3轮−1009.56，2未闭。

## 6. 亏损记忆的会计/退出原因审计
1547个已闭合轮逐轮核对：截至实际exit_day的订单cashflow+截至当日已ACCRUE_NET80权益，恰等于最终marked_net，0差异。本样本没有后来到款或新事实改写平仓当晚盈亏。
934个已闭合负轮：
- CURRENT_SEED_TRIAL_SECTOR_FALSE：639
- I_OPEN_PROTECTION：17
- CP_LAYER_EXIT：3
- CURRENT_NON_MAINLINE_SEED_RETIREMENT：160
- NON_MAINLINE_EXPANSION：71
- MAINLINE_EXPANSION_SURPLUS：44
后3项共275轮为资金迁移，不可仅因净负就叫结构失败。G2误挡聚和的反例即使排除纯迁移仍存在。

## 7. 仅追加的两相邻收盘 M 诊断
公式：MATURE新SEED要求M(t)=M(t−1)=1；严格相邻交易日、均已知，UNKNOWN暂停。EVENT/RESIDUAL与已有持仓、ADD均不变。
- 晚期MATURE479挡385：原净−93635.64，原毛亏124186.50与毛利30550.86同时被标记，279已闭/106未闭。
- 全窗挡682：原净+17352.23，不能据晚期单窗认为是好规则。
- 9/24 OPEN挡28 MATURE里的18（all-in135513.35），包括地产/汽车整车；保留10 MATURE+36 EVENT。
- 9/25 OPEN挡32 MATURE全部，含同花顺、指南针、软通动力等。
- 9/23–9/30实际OPEN挡106轮，原净+82145.18。保留三只原EVENT赢家不代表捕获整体主线不变。
- 若保留WAIT票，延后收盘是否仍M、stock、I有效以及重新分配必须逐时点重走，不能将上述原轮净损益当作消失。这一步没做资金重放，也不据此冻结。

## 8. retained迟到的事实，非新过滤器
晚期479 MATURE中412先被资本拒绝，细表 RETAINED_PRICE_CP_DETAILS：
- 全412第一次拒绝都发生在原signal的首个nextOPEN。
- 原signal→实际fill：2个交易间隔302轮，3间隔72，4间隔20，5间隔10，6间隔8。中位2，p90=3；首拒→fill中位1，最大5。
- 首拒phase：EVENT318、RESIDUAL68、MATURE23、PAUSED3。大多数是试仓/残余票后来转成成熟阶段，不宜笼统称成熟队列长期滞留。
- 实际fill前CLOSE较原signal CLOSE：308轮价格更高，中位+1.93%，p90+9.96%。
- I线仅47轮抬高；保护距离(C−I)/C中位扩大1.13个百分点，128轮缩窄。
- 等待期间134轮有新的CP receipt，最新receipt在已知OPEN/CLOSE至计划日保持未破；CP状态无unknown。
- 261轮既无I线抬升、也无signal之后的新CP receipt。
- 实际fill OPEN比原signal次OPEN价中位+2.05%、p90+11.69%，这只是价格路径事实，不是可实现收益差。
- pre-SEED CP只是市场字段，现引擎不会把它算成实际轮information_confirmed，也不冒充post-SEED CP。
- 另一冻结序列表的已闭合组：retained313均−286.70，非retained60均−516.36。因此不能把retained总亏更多直接归因于等待，样本量、行业及后续路径均不同。

可继续研究的问题是「原EVENT试仓票转MATURE时新增了哪些可观察的个股结构证据」，而不是机械过期N天或自动追加CP门槛。本轮没有提出/测试新CP或I改进筛选公式。

## 9. excess5的纯描述核查
定义及已知规则见第2节。比较对象是行业中位数，不是大盘；原值以收益小数计，乘100才是百分点。
按冻结字面正/负，不改变策略：
- 晚期MATURE479：正366，原净−95010.29；负113，原净−25097.42；字面零/unknown均0。
- 仅已闭合：正284均−334.75；负89均−288.19。不能由总亏推出正值更好。
- 9/24 MATURE28：正15原净+16985.61；负13原净+17241.70。负组包括浦东金桥+5904.62、华泰证券+2380.53等。
- 全窗MATURE833：正618原净−67360.86；负215原净+34237.15。负组含禾望电气+10845.52、协鑫集成+9410.52。正组也有新华保险+12922.90、钧达+9169.43、粤传媒+8195.03。

数值边界必须单独披露：
- representative_score用Decimal收益，行业中位数来自float，真正中位并列可留下10^-16级残差。聚和材料−1.24e−16不能被称为行业落后者。
- 仅作数值并列提示，不是交易参数：全窗15个abs(excess5)≤1e−12，原净+25675.93；去掉这些后，实质负206仍原净+13174.54。
- 晚期数值并列5个都字面负，总−684.36；实质负108原净−24413.06。
- 9/24并列1个为新城控股+3544.01；剩实质正14、实质负13。
- 不据此推出excess5>0门槛，不扫任何百分位或阈值。

## 10. 交付索引
- FORMULAS.json：原G1/G2公式和边界。
- REQUEST_CLASSIFICATION、FILLED_SEED_CLASSIFICATION：原请求/实际种子逐条分类。
- SUMMARY、SECTOR_SUMMARY、REQUEST_SUMMARY：覆盖量及原路径损益/机会成本。
- STARTUP_ACTUAL_OPEN_BY_PHASE：9/23–9/30实际OPEN严格时序。
- KNOWN_FAILURE_ANCHORS、G2_UNLOCKS、LOSS_REASON_CLASSIFICATION、BLOCKED_ANCHOR_REASONS：旧高、已知时点及退出原因。
- WAIT_TIMING_FOCUS：重点反例的逐日等待/取消路径；不是成交重放。
- M2D_SUMMARY、M2D_STARTUP_ACTUAL_OPEN及逐请求/逐SEED表：唯一追加的相邻收盘诊断。
- RETAINED_PRICE_CP_DETAILS/SUMMARY：412票原signal、首拒、实际fill、价格/I/CP变化。
- EXCESS5_SIGN_SUMMARY：各组闭合/未闭合分别统计及主要赢家。
- OBSERVABILITY_QA与各SOURCE_HASHES：本地源哈希与已知平仓净利时点核验。
