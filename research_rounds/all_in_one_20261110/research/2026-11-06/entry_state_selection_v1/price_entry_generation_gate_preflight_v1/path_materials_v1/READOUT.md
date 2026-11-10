# 固定167轮的后续市场路径：只读材料

## 结论与用途

167个共同实际BUY中被固定entry-generation gate拒绝的旧轮全部保留：2022年117轮、2024年50轮，156只股票。材料包含13,115个逐日锚点路径行、1,414个事件行。消费工程任务已封存的完整市场tape，没有重复market replay、经济、费用或股数计算。

最重要的事实：2024原27个FULL赢家全部在原初仓窗口内出现同一PRICE父root中的合法新代以及后续原PRICE receipt；其中26个至少有一次原来源“假设尚无parent”的行业四项及CLOSE/nextOPEN条件size检查通过。2022原96个FULL亏家中，43个有同父root的窗口内后续合法receipt；计入原root结束后的第一个新root出生，83个有窗口内合法receipt、81个有条件size检查通过。

这些是市场许可与旧来源条件检查，不是新策略已恢复的订单、持仓或利润。旧正净额/原赢家身份不能否决会后续重新参与的固定规则；同样，后续出现合法receipt也不能证明追回原利润。完整新动态队列、费用和参与结果由另一个固定经济比较给出，本文不据静态标签决定升降级或改变参数。

## 范围和时钟

- 入口固定为COMMON_167_DENY_BUYS.csv的全部167轮，标签来自旧FULL结果，只用于解释，不用于筛选或豁免。
- 每轮从原拒绝signal CLOSE，保留至原父root首次FAIL/UNKNOWN及其后的第一个不同父root出生。该“下一root”只保留出生点，未在此材料继续遍历其整段生命周期。167轮均观测到原父root FAIL及下一root出生，没有父root UNKNOWN或末端未终止样本。
- 只有2022全年、2024年9–12月可以新开初仓。2023/2025等尾部是市场观察，不能产生本比较的新初仓。窗口最后signal的立即next-common OPEN仍遵守原合同。
- 原root、C、S_old、S_new、receipt及拒绝状态在167个锚点全部与原事实一致。每日旧S和当日新S分别保存，不把当日E0抬线当事前保护。
- 行业、AB事件/I/PVR资格、原PVR、原队列和条件size均直接关联已存旧来源。原joint队列missing、旧持仓占用或HELD不是新动态路径的阻断证明。
- nextOPEN只记录实际原始OPEN、已存独立unstarted size及费用条件；不使用该日high/low/close或一字板后验事实判断OPEN可交易。真实订单、ACK、成交与tradability仍UNKNOWN。

## 全量作用域

下表“同root新代”可发生在窗口以后；其余标注窗口的列仅限原新初仓窗口。所有分子均按原轮计数，同一股票不同原轮分别保留，不是新交易次数。

|原窗口/旧结果标签|全部轮|后来同root新代|窗口内同root合法receipt|窗口内同root或首个后继root合法receipt|窗口内行业+CLOSE条件size通过|再加nextOPEN条件size通过|
|---|---:|---:|---:|---:|---:|---:|
|2022 全部|117|66|62|102|100|100|
|2022 原FULL赢家|21|21|19|19|19|19|
|2022 原FULL亏家|96|45|43|83|81|81|
|2024 全部|50|38|38|42|39|39|
|2024 原FULL赢家|27|27|27|27|26|26|
|2024 原FULL亏家|23|11|11|15|13|13|

2024原赢家中唯一没有条件size通过的是财富趋势688318：9/24新代及原receipt后，窗口内九个合法receipt的原CLOSE检查均为Q0_MINIMUM_LOT_OR_RISK_NOFILL，行业四项均真；OPEN检查没有被到达。这说明合法market gate与原风险/最小单位可行性仍是两层条件，并不等于新动态系统一定永久不能参与。

新代出生也不自动发原票。例如江苏银行600919原10/16信号被拒，12/10新代出生，但首个满足原receipt的是12/18；申能600642原11/1被拒，12/5新代出生、12/9才有原receipt。相反，688027原10/31赢家后来新代到2023/1/19才出现，不属于2022窗口可新开仓。

## 三个代表性具体链

下面金额单位为人民币，股数为股。后续日的CLOSE/OPEN费用均逐字取自原已存条件size结果，不是本次重新计算的费用，也不是新路径实际费用。原策略实际proxy账只列其已发生的原记录，仍不是券商真实成交。

### 浪潮信息000977：2022原亏轮

- 原root出生2021/10/26。2022/1/5有原PRICE新frontier receipt，但entry-generation已退役，固定gate拒绝；原joint当天为SELECTED_PENDING。
- 原账1/6 BUY_CORE为600股，含原滑点proxy价35.927955，原费用6.9120857651。原轮还包含1/19 ADD及2/8退出；该轮FULL为−4599.8246948063，只描述旧账。
- 原root在2/7 FAIL，期间没有合法后续新代/receipt。直到6/8才出现第一个新PRICE root，其gen1及原receipt同日成立。
- 6/8行业四项全真，原PVR 78.353698876；CLOSE条件900股、条件费用6.8368315568、计划风险2162.9925568711。
- 6/9原始OPEN 25.80，原独立unstarted OPEN条件900股、条件费用6.8283277070、计划风险2054.9300530213。
- 6/8旧joint无队列行、旧AB事件许可为false。新动态队列/占槽/资金/实际proxy参与未由本文重建，不能把missing当新路径失败，也不能称6/9已买入。

### 游族网络002174：2022原赢家轮

- 原root 11/2出生。11/8原receipt到来时旧entry-generation已退役，gate拒绝；原joint为SELECTED_PENDING。
- 原账11/9 BUY_CORE 2800股，含原滑点proxy价8.344170，原费用6.8387213012。该旧轮FULL +28421.2323799342，不代表新策略损失或保留此金额。
- 11/17同一父root生成gen2，同时产生原PRICE receipt。行业四项全真，原PVR 81.2108691661。
- 11/17 CLOSE条件1900股、费用6.3524270756、风险2892.5491565475。
- 11/18原始OPEN 8.71，独立unstarted OPEN条件2500股、费用6.7145493463、风险2977.3503775987。
- 11/17旧joint无队列行、旧AB事件许可false。1900不是2500的执行上限；OPEN注册时仍可按原规则独立求2500，但是否在新路径获得该候选/队列席位及实际proxy参与必须等完整动态账。

### 汉得信息300170：2024原赢家轮

- 原root 8/1出生。9/19原receipt到来时gen2已退役，gate拒绝；原joint为SELECTED_PENDING。
- 原账9/20 BUY_CORE 3600股，含原滑点proxy价6.553275，原费用6.5122337390。该旧轮FULL +29937.9574292692。
- 9/20同一父root生成gen3，同时满足原receipt。行业四项全真，原PVR 67.4575191743。
- 9/20 CLOSE条件3300股、费用6.4137269102、风险2976.7183895224。
- 9/23原始OPEN 6.66，独立unstarted OPEN条件3400股、费用6.4522061402、风险2998.5805858013。
- 9/20旧joint无队列行、旧AB事件许可false。原路径已在9/20 OPEN买入，而新gate下此处是另一个未注册初仓候选时点；不能沿用旧持仓状态去否决，也不能把3400股直接当新账成交。

## 更正记录：CLOSE预检不等于固定Q

本次协作中曾误说“后续OPEN容量受CLOSE注册固定Q约束”。此说法已撤回并同步父任务、工程及独审。准确合同是：

1. CLOSE的close_q只用于可行性预检，不是固定Q，也不是执行量上限。
2. 原joint_engine.py:145–162在实际nextOPEN调用initial_open独立求q。
3. 该OPEN结果进入_proxy_buy/OpenPermission，随后open_target（:128–140）才创建固定Q。
4. 只有已成功注册parent之后，后续重试才受固定Q−F余量约束；零fill既有parent也不能被当成无parent重新gate或定Q。

因此游族1900→2500、汉得3300→3400是符合原时钟的独立OPEN条件量，不能取min(close_q,open_q)或人为封顶。本文提取代码只抄原值，没有这种裁剪。后续条件量及费用不是新动态成交；动态的候选、槽位、资金状态和实际费用仍需完整消费者账。

## 文件、封存和限制

- PROTOCOL.md、prepare_paths.py、FREEZE.json在本路径提取前固定；这是已见旧标签的开发性路径检查，不声称盲测或OOS。
- 生产者market_tape/PRIORITY_156_COMPLETE.json封存后才消费156股文件，前后SHA一致。工程生产者拥有完整market tape，本任务没有另跑尾部market adapter。
- ALL_167_DAILY_PATHS.parquet：逐日原root、gate代际、S_old/S_new、原receipt及旧来源条件。
- ALL_167_EVENT_CHAINS.csv：原receipt、代际变化、原父root终止和首个新root出生。
- ALL_167_SUMMARY.csv、SUMMARY.json：全部167轮的first日与分母。
- ORIGINAL_QUEUE_ROWS.csv：原DECISIONS/RANKING_AUDIT原行，不是新队列。
- QA.json：167锚点一致、0经济/市场重演/费用或size计算、0窗外新初仓、原源哈希不变。
- SOURCE_HASHES.json、OUTPUT_HASHES.json保留原提取产物seal；本READOUT为结果之后的叙述，另存READOUT_HASH.json及附加来源哈希，不改封存证据。
- 原旧结果关联的财务覆盖、独立CORE及静态判断撤回，以../../old_result_association_v1/final_correction_v2/READOUT.md和../DECISION_CORRECTION_20261108.md为准。

本材料既不宣布新gate有效，也不否决它。固定公式与身份不变，继续完整动态参与比较。
