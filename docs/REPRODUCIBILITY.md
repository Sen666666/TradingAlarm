# 安装与复现

**2026-10-25：RC1渐进恢复原型结项，无账户。** 入口`research_rounds/gradual-recovery-rc1-20261025/README.md`；规则freeze.json、前缀验证修正repair-freeze-v1.json，有效results-v1；首次results仅前缀类型校验失败未完成，保留。当前结果输出均独占创建，不在原路径重跑；复制新轮重新冻结再按README顺序复现。图表/未来价格标签不是资金收益；旧IX背景弱时的参与尚未消除。

**2026-10-25：多尺度/交接有限诊断结项，账户0。** 有效目录`research_rounds/multiscale-resource-review-20261025/`：模型freeze-v2、资源解析handoff-v1、全池gate-audit、report及validation。旧handoff最小单位解析失败已明确superseded，analysis-attempt0/1和技术/核验失败保留。现存结果脚本多为独占创建，不在原路径重跑；复现请复制新轮目录，重新记录路径/哈希，按README顺序操作。本轮描述和价格标签不是资金回测，局部恢复新收据仅设计。

**2026-10-25新增：IX全市场四入口轮已结项。** 入口`research_rounds/ix-a-share-entry-20261025/`，先读CONCLUSION、PROTOCOL、freeze、complete；经济48、技术旧E0控制4＋物理截断16。原金融循环只更换决策入口、账户规格及显式entry_mode，纯事实缓存经40完整决策/68440资格对照，旧4账户载荷精确一致。有效输出accounts/analysis/misses/report，不直接重跑code/run_multi.py、prepare_ix.py、analyze_ix.py或post/finish_analysis.py到原目录。截断技术由post/run_prefix.py完成，勿再重复调用code/run_multi.py 2023-12-29。需要复现时在独立副本另设输出并登记差异；post仅展示/描述统计，不能按结果改买入规则。本轮未重下行情，旧结果完整哈希核验；post保存只读身份脚本的路径/字段适配失败，不涉及经济重跑。

**2026-10-25最新：RS-H1与买单日有效联合修正已完成，不晋升。** T0/T1/S0/S1各100万元仅A股，同一2015—2026-10-22数据；12经济账户＋12真实前缀。新基础收益/回撤为−66.64%/75.58%、−65.84%/83.33%、−85.92%/92.33%、−56.57%/77.45%，均未改善收益，所有情景未达20%回撤目标。整批代码回退0、首次成交最长1市场日、34,392经济日账独立重放及17,532前缀日账通过；原30文件、旧数据/结果不变。E0未改，换仓未加，规则结果后修订0。[新轮与复现边界](../research_rounds/rs-h1-execution-20261025/README.md)。未新增行情，旧源缺口和当前快照选样偏差保留。本轮结束，不自动续跑。


**2026-10-25当前入口更新：** [固定E0 A股全市场轮](../research_rounds/a-share-selection-e0-20261024/README.md)已完成数据核验和13个有效账户，唯一有效版本为inputs-v2/prepared-v2/accounts-v2；旧行业映射误用及13未完成账户中止记录保留。5576原始股、1709合格股、90行业，源缺口与权益/成交代理逐项披露，不称无缺口PIT全池。13账独立重放与12截断技术重放通过。当前S0扩展不晋升，T1虽基础盈利28.67%但最大回撤65.25%；排序缺失整批代码回退和陈旧逻辑意图限制解释，细节见本轮报告。算法不变；完成后不再自动补数、续跑账户或寻参。下方历史进度若有冲突，以上方本轮结项为准。

**2026-10-22用户决定：80%保留为大行情愿景和观察项，不再作为每轮研究的通过、晋升或继续搜索门槛。** 20%仍为回撤研究目标，30%仍只是尾部分类界线；低胜率、正常右侧回吐和少量普通净损耗可接受。固定主要账户与主要对照，先评价机制、收益结构和成本后经济取舍；局部小池相对中间方案改善不能重置整个研究的停止计数。保持旧九资产停止，继续历史全池板块→个股研究，先核实数据、再作有限对照和主动图检。

D1本地盘点已有产物，D2第1批已有18次公开GET及6次原生请求；先复核已有响应和字段语义，再接续剩余预算，不重跑盘点或重置批次。新全池经济账户0，历史资格/行业/执行仍须通过。详见[当前计划](NEXT_RESEARCH_TASKS.md)。

## 2026-10-21及此前记录（当前动作以上方更新为准）

**2026-10-21当前入口已转到[历史全池两级选股](../research_rounds/sector-stock-20261021/README.md)。** [方案](SECTOR_STOCK_STRATEGY_PLAN_2026_10_21.md)已写成，`protocol.proposed.json`仅为设计件，尚无新全池执行器、冻结快照或账户结果；不要调用旧runner冒充新轮。先盘点本地名册/缓存，再做已授权节点的有限数据取证；每批记录预算与覆盖，保留原始证据，不覆盖旧文件或重新全量补数。下文冻结与复现记录仍有效，但不是当前自动执行队列。

**2026-10-21共同算法复查已完成：** `research_rounds/pv-strategy-20261020/diagnostics/common-algorithm-review/`保存两阶段冻结、9张原始图及先看记录、9张完整状态图、4,392机会分类/244不同信号、全部连续簇和逐观察分解、R1三情景配对。`outputs/v2`为最终分析，`verification-v2.json`为独立逐项核验。`outputs/v1/failure.json`保留None/NaN比较失败；`verification-attempt1.json`保留可缺失整数CSV解析失败，两次类型修正均有独立收据和代码副本，未改信号、数据或账户。诊断不导入账户引擎，累计877账户/422前缀/119测试不变，研究保持冻结，无待自动执行实验。

需要复现时，在独立研究副本使用`code-v2/review_common_algorithm.py`与`code-v2/verify_common_algorithm.py`恢复当时分析身份，配合`code/bridge.py`及冻结/类型修正记录，执行诊断`run --output 新目录`；随后用`code-v3/verify_common_algorithm.py`及核验修正记录核对新输出并指定`--receipt 新文件`。不要在当前已更新核验代码的树中直接重跑旧分析并称身份相同；不要再次freeze原目录。`review_raw_history.py`及`summarize_common_algorithm.py`默认路径拒绝覆盖，重放须在独立副本调整输出并记录代码差异。完整研究结论见[报告](../research_rounds/pv-strategy-20261020/diagnostics/common-algorithm-review/REVIEW.md)；当前不需要重跑已通过的旧账户或测试。

**当前策略研究环境（2026-10-20）：** 项目内`TradingAlarm/research/.venv/bin/python`已修复，使用本机Python3.13.7，numpy2.4.3/pandas3.0.1/matplotlib3.11.2/pyarrow26.0.0/lxml6.0.2导入验证通过；不再依赖外部工作副本。原断链保留为`bin/python3.13.legacy-link`。依赖安装统一使用`python -m pip`，原迁移环境内个别包的命令行包装脚本仍可能保留旧shebang。已把原价权息HTML解析所需lxml加入requirements。

新研究目录`research_rounds/pv-strategy-20261020/`；`data/v2`为9资产通过桥接的不可变快照，`data/v1`初次严格日期检查失败保留。无需重抓数据或重算算法。执行器合成验收入口：

```sh
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/tmp/tradingalarm-mpl \
  TradingAlarm/research/.venv/bin/python research_rounds/pv-strategy-20261020/code/test_retry_budget.py
```

策略R1—R14及R16已完成，累计877账户及422组真实截断前缀通过；当前119项合成测试通过（上述入口包含原105项和R16新增14项）。R16为72账户、48前缀、36完整旧控制、8,784次准入独立重建、499结果文件hash通过。`retry_budget.py`按严格前日信息重建最近实际出资前驱是否结清、净损益和首次退出信号前结构进展；只影响下一准入预算。`audit_retry.py`不调用政策函数，从原始信号/成交/权益按日独立重建全部份额，并核对2,698个已结清前驱净损益。合成测试覆盖未知权益、同日结清排除、未成交不重置记忆、部分退出的新结构排除、拆股/费用/汇率、减半不复乘和审计篡改拒绝。执行/审计/绘图代码事前冻结，无账户重跑；测试证据见`validation/r16-retry/`，复盘和收据见`reviews/r16-retry/`。

R14原48账户、16前缀、105测试及348结果hash保留，不用当前代码覆盖复现。`riskspace.py`只限制结构释放后的新增整手，B0和买入成本不随净值或拆股改写；投影结构底按先前实际观察映射、以当前开盘封顶，不是实际亏损保证。收据仍在`reviews/r14-riskspace/verification.json`。

`execution.py`分派逐资产隔离到`sleeves.py`，市场隔离到`markets.py`；两者统一池交易日并集，不能平均子账户收益。`capital_ledger.py`重建母资产资金账；`market_ledger.py`按CNY/HKD归属合计，组内资产虚拟负现金允许。各轮`complete.json`核验整轮完成，`results.partial.json`只记录中间进度。便捷的“协议→freeze→run”入口和不覆盖规则见[新轮README](../research_rounds/pv-strategy-20261020/README.md)。运行前保存代码/数据/协议哈希与代码副本，每账户独立核账并拆分完整参与周期，全部252/504窗口保存。旧轮重放须在独立副本恢复该轮确切代码并另设输出目录，不用当前代码冒充旧版。R14后更新轮README不改变已冻结执行代码，其身份差异在复核收据中明确记录。R13及更早全部成功/失败证据完整保留。

**R15/R16前置只读诊断（2026-10-21）：** `code/diagnose_admission_rank.py`和`code/diagnose_retry_budget.py`结果在`diagnostics/pre-r15-rank`和`diagnostics/pre-r16-retry`。各读24旧账户、2,928次准入，诊断自身无新账户；R15排名份额否决，R16后来完成上述独立冻结检验。`verify_admission_diagnostics.py`核对各13个输出、75/76个输入hash、完整净损益/费用，及旧2,688个前驱结构观察收紧至首次退出信号前的精确一致性。两目录各有`verification.json`；16张原始量价面板均已实看。脚本和收据拒绝已有目录/文件，不直接重跑覆盖。旧诊断2,688已结清与新反馈账户2,698已结清分属不同出资路径，不能混用。

**R17只读诊断（2026-10-21）：** `diagnostics/pre-r17-participation/`保存首步协议及freeze、`outputs/v1`的8,784机会/8,215出资周期、85,050账户日核对与12原图。`diagnose_participation.py`按实际事件序重建准入现金、原股及待买承诺；`verify_participation.py`独立从日末反推8,784个快照并直接取先前原价/结构验证，23输出/301冻结输入hash通过。首步后另存风险共享协议，`diagnose_risk_sharing.py`只计算2,928次局部额度，`review_risk_sharing.py`独立公式复核并绘制3图12面板；旧路径不传播假设预算，不计算假设收益。R17最终诊断否决，新账户0，连续计数0→1。所有原输出拒绝覆盖；首步复现可使用`diagnose_participation.py run --output 新目录`且须满足原freeze身份，其余默认路径也拒绝已有目录，复现须先在独立研究副本改输出并记录代码差异，不直接重新运行。本轮未改执行器或增加策略合成测试；119测试、877账户和422前缀计数不变。

**R18只读诊断（2026-10-21）：** `diagnostics/pre-r18-first-open/`保存事前协议、freeze及代码副本、36旧账户4,392机会的原目标/实际首笔风险分解。`diagnose_first_open.py`只读R16及R17结果；`verify_first_open.py`独立按原价/前期量重建4,392执行时钟，核对12,544风险快照、局部整手上界及3,997单笔买入闭合损失恒等式。`summarize_first_open.py`为诊断后报告算术，时点已标记，不定义新策略。15完整量价面板及15首仓放大图实看，最终诊断否决、账户0，连续计数1→2。默认freeze、outputs/v1、review及report-metrics均拒绝覆盖；不直接再次运行，复现须在独立研究副本改输出常量并记录代码身份差异。R16源499hash、R17源42hash均核验；执行器、119测试、877账户和422前缀计数不变。

**R19只读诊断（2026-10-21）：** `diagnostics/pre-r19-peer-state/`保存协议、freeze及诊断/核验代码副本，36旧账户4,392机会的创建/准入两时钟同伴状态和完整结果标签。`diagnose_peer_state.py`运行前核验134冻结输入、R16的499及R17的42结果hash；`verify_peer_state.py`用CSV及二分查找独立核对8,784时钟、48,060同伴记录和全部源周期，再独立平均秩计算2,088描述关联。`summarize_peer_state.py`明确为结果后的报告算术，逐格复核7,470分组。12完整图已看，最终否决、账户0，连续计数2→3，下一步转共同算法失败复查。`run --output 新目录`与核验`--output 新目录 --receipt 新收据`支持不覆盖的重放，但须保留原freeze身份；不要再次freeze原目录。报告算术默认拒绝已有文件，若需重放须在独立副本调整输出并记录代码差异。本轮没有改动信号/执行器，没有新增策略合成测试、账户或前缀。

**最新完成：** [高参与下跌跨日收复](RESEARCH_PARTICIPATION_RESPONSE_2026_10_20.md)，目录`research_rounds/pv-participation-response-20261020/`。先读README、freeze.json及保存结果`results/v0-input-fixed`。原`inputs`不变，最终输入为`prepared/source-precision-v1`，manifest分别记录来源；不要把原v0或旧全列差异false改名为通过。761候选、103上游、98准备检查均通过，排名10组合成＋98真实通过，旧失败保留。本轮账户0次。

如确需复现，只运行该轮`code/run_study.py --output 该轮results下尚不存在的新目录`，准备器拒绝覆盖既有prepared目录，不自动重建数据或启动旧账户。代码内source_directory固定本冻结准备输入。根目录venv见下方既有说明。交付收据在`docs/reviews/2026-10-20-participation-response-delivery/receipt.json`。

## 上一阶段记录（已冻结，不自动重跑）

**最新完成：** [量条件事件记忆原型](RESEARCH_VOLUME_RESPONSE_2026_10_20.md)，目录`research_rounds/pv-volume-response-20261020/`。优先读取其README、freeze.json和保存结果。18固定窗口已实看，账户0次；真实验证239/250通过、11失败，不能因目录名v0-verified便声称全部通过。results/v0保留首次中止，v0-verified保留成功信号输出，当前入口代码的字段类型与坐标保护改动另有哈希及轨迹等价核验。复现只用该轮run_study.py的`--output 新目录`，不运行旧账户或prepare_inputs.py。交付核验见`docs/reviews/2026-10-20-volume-response-delivery/receipt.json`。

## 旧阶段复现记录（不自动重跑）

**上一轮完成：** [累计损耗归因与原版冻结](RESEARCH_TAIL_COST_2026_10_20.md)。本轮只读601个已有周期，生成归因与完整历史图，复现原27条信号以核对身份；账户调用0次。目录为`research_rounds/pv-tail-cost-20261020/`，参见其README与freeze.json。归因脚本支持`--output 新目录`并拒绝覆盖；不自动重跑原账户。交付核验见`docs/reviews/2026-10-20-tail-cost-delivery/receipt.json`。

2026-10-20最新有限研究：[固定位置量价响应](RESEARCH_BOUNDARY_RESPONSE_2026_10_20.md)。输入、代码与结果在 `research_rounds/pv-boundary-response-20261020/`，默认结果生成会拒绝覆盖 `results/v0`。优先读取报告、冻结协议及分层审阅记录，该轮历史下一动作已由当前计划替代，不自动重跑。

如确需复现观察器，使用可用Python，并为本轮 `results/` 指定一个尚不存在的直接子目录；不要重新准备输入或运行旧账户：

```sh
PYTHONDONTWRITEBYTECODE=1 MPLCONFIGDIR=/private/tmp/pv-mpl TradingAlarm/research/.venv/bin/python research_rounds/pv-boundary-response-20261020/code/boundary_study.py --output research_rounds/pv-boundary-response-20261020/results/reproduction-new
```

该命令仅生成离线事实与图片。原协议及看图顺序修正的哈希必须匹配；换路径不使开发历史成为样本外。观察器验证记录在 `validation.json`，纯数据调整验证另在 `inputs/`，两者计数不可混淆。正式仓库交付核验见 `docs/reviews/2026-10-20-boundary-response-delivery/receipt.json`。

2026-10-20新增：本机正式仓库的venv链接仍指向原机器 `/Users/sen`，目前不可直接使用。首轮量价研究复用 `/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python`；实际Python/依赖版本、输入与输出哈希见 `TradingAlarm/research/results/pv-segment-20261020/manifest.json`，新目录复现命令见该目录 `review.md`。旧原始结果不得直接重跑覆盖。

当前为本人授权的私有迁移版本，已有会话启动方式见 PRIVATE_MIGRATION.md。下文的独立副本检查是此前不含票据版本的验证记录。

## 环境

原研究环境 Python 3.13.7；应用本身只需Python标准库（建议3.13）。研究核心版本记录在 requirements-research.txt，网络采集可选依赖在 requirements-fetch.txt。并非把原虚拟环境的企业内部无关软件包整体复制过来。安装需要可用包源，完整离线新机器需另行准备这些公开依赖的wheel。

```sh
python3 -m venv TradingAlarm/research/.venv
TradingAlarm/research/.venv/bin/python -m pip install -r requirements-research.txt
python3 scripts/verify_payload.py
cd TradingAlarm
python3 -m unittest -v test_market test_sessions test_search
node --check static/app.js
TRADINGALARM_ENABLE_LIVE=0 python3 server.py --port 8765
```

Node只用于JS语法检查，运行界面不需要Node构建。

## 研究测试与快速结果审阅

研究脚本多数要求工作目录为 `TradingAlarm/research`。不要在根目录直接调用依赖相对路径的历史脚本。

```sh
cd TradingAlarm/research
.venv/bin/python -m unittest -v test_trend_engine test_campaign_claims test_monthly_claims test_trend_slot_engine test_volume_clock_strength test_sector_gate_opportunity_audit
```

优先读取 `results/broad-shared-first-cross/summary.json`、`results/sector-ranking-random-controls/review.json`、`results/ordinary-loss-attribution/review.json`；如果某个文件不在该目录，先查 catalog 的 exact paths。保留原有文件名，不为了整理重命名数据。

## 新实验与原基准重放

新实验复制协议到一个**新目录**并固定假设，避免覆盖保存的结果：

```sh
cd TradingAlarm/research
mkdir -p results/handoff-volume-clock-replay
cp results/strength-volume-clock/protocol.json results/handoff-volume-clock-replay/protocol.json
MPLCONFIGDIR=/tmp/tradingalarm-mpl XDG_CACHE_HOME=/tmp/tradingalarm-cache \
  .venv/bin/python trend_workbench.py --output handoff-volume-clock-replay
```

该命令会重跑ETF17/HK7固定协议及对照，可能耗时；原协议还可能引用已有control目录，已全部保留。

A485 `broad_shared_slot_experiment.py --first-cross` 当前会写入固定结果目录。重放请先在临时 Git clone 中运行，不能覆盖主工作区已保存证据。多数历史诊断也如此。

实际行情输入不依赖本人票据；新增数据采集才需要在线配置。仓库外my-quant源只用于部分早期重建/审计脚本。catalog 的 absolute_path_scripts 列出受影响脚本，原输出已经随仓库携带。不要把“已有特征可用”误写为“原始全库也可从本仓库重建”。

## 本次整理的验证范围

见 `verification.json`：在不带私有抓包和settings的独立副本运行应用测试、核心研究测试、HTTP离线检查和文件校验。没有重新执行几百项实验、没有再次验证远端会话，也没有在全新包源重建依赖环境。完整依赖安装与所有旧脚本的跨平台可运行性仍需按目标环境验证。


## 2026-10-20 结构语境算法阶段

`results/pv-structure-context-20261020/`保留30原始图、两版各15轨迹图、逐图判断、四个失败尝试及冻结哈希，账户调用0。优先阅读[本轮说明](../TradingAlarm/research/results/pv-structure-context-20261020/README.md)；如需明确复现，只用其`replay_context.py`指定新输出根，避免覆盖。当前阶段无账户准入，禁止把旧runner队列作为下一步。


## 2026-10-20 成果保留算法阶段

本轮保存在仓库根相对目录`research_rounds/pv-progress-retention-20261020/`，不是旧results下的同名实验。29序列、18轨迹图、90项真实序列检查、8组合成检查，无账户。见[自包含说明及新目录复现命令](../research_rounds/pv-progress-retention-20261020/README.md)。先读报告；需要复现时使用`code/replay_progress.py --repo ... --output 新目录`，原runner拒绝覆盖。`--prepare-only`可只核验哈希并准备运行，不计算任何账户。
