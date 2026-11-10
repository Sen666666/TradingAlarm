**提案：VOLUME_NEUTRAL_FULL_FEATURE_AND_FIXED_MOTHERS_V1。仅设计，未获全池导出/新计算/账户授权。**

唯一问题是：在当前完整实际买入/重入母体及固定原赢家中，去掉预测量乘子会保留/撤回哪些原决策信息，又会产生哪些此前没有的机会。不是再证明信号会改变，不根据删单或比例PnL生成NAV，不设计新指标、阈值或执行政策。先以以下有限纯feature范围交root与独审，另grant后才实现/执行。

| 项目 | 冻结范围 |
|---|---|
| 输入母体 | 原1709股＋90行业，A-only/HK0，原signal/source段、价域/动作因子、实际V/ADV/报价mask保持；至2026Jun30完整warm |
| 真量控制 | 原缓存facts、CP1_input同名全部字段、CP1整表逐值核；股票全部已有PVR八字段点及现成968策略日score逐值核。其余warm八字段无旧输出，不伪造参考。只保核验收据和旧hash/ref，不复制一套真量全数据 |
| 中性 | 只复用risk已审assemble，原E0/B4 joint=False、CP1 price_only=True、PVR有效信号D归一；原m保observed diagnostic、effective_multiplier=1。输出新目录，旧数据/模型/fixture不动 |
| 时间/角色 | 2022→24自身No60实际2265层＋strong Jul2025→Jun2026实际1171层，准确budget_order决策CLOSE，signal_at另列；first/add/reentry、core/mobile、probe/confirmed、固定年/季/L03/L04/2024pre924/六收盘/Oct8后303保完整分母 |
| 原赢家 | 已冻原PVR tail83/94**全名单**，在每个原actual decision时点取neutral特征；不能只留No60匹配45/67或用同股别单补匹配 |
| 非本阶段 | 无Account/Runner/新订单/金融stage/ACT_on重放，无共享真量父持仓中途换信号；不重排资金、不重复用释放现金、不报新费/PnL/NAV |

**最小装配与源入口**

已独审源 `risk_constraints/run_volume_fixture_verification_fix_v2.py` SHA `c3dbee1b5347f02ec8074c5bd47059ccd83bcd5dc6fce9d0edfb77ab6836a087`，复用 `assemble(signal,stock,neutral)`，不调用其固定3卡main/one-run guard。将原依赖初始化绑定到同一源码/真实module.__file__（eligible_prices/evidence/policy/grade/policies/NUM/B4/CP/SCORE），至多一个薄读取/并行/核验/写入控制器，不复制状态机或重写中性公式。可AST提取原函数保持语义，所有writer只指新目录。至多6独立worker，每任务一个series，由worker读源；不能按完成顺序影响ACT聚合顺序。

现有 `universe-cp1-inputs-20261031/{STOCK_MANIFEST,INDUSTRY_MANIFEST,FREEZE}.json` 提供全部1799 source signal/events/states/facts/q/CP1及output SHA。无需补数或新造raw/canonical数据源。现存三卡6条已冻REAL/NEUTRAL可在新manifest按全部source/model/hash/全warm范围核同后引用，不重跑作“新样本”；没有独立旧REAL完整表的其余序列按原assemble冷算、核验后丢真量临时frame，只落中性表。

元数据总量：股票4,049,565＋行业364,796＝4,414,361合法warm观察；1687股complete、22股`not_applicable_no_local_observation_by_end`，90行业完整。空序列不能直接调用未验assemble(empty)，在loader按原manifest保空/NA及原因、原schema，不能造零价/零信号、删成分或补后来IPO。原source段和缺观察处理保留，不把趋势段当来源段。

每个非空item只读SHA→真量原assemble→完整cached parity→中性同assemble→原价/源/掩码恒等→原子保存item结果/收据。任一真量parity失败停受影响路径并停止全局完成发布；已落中性仅PARTIAL_NOT_DIAGNOSTIC_READY，不能替该股沿用旧real I或删股凑齐。无自动模型/容差修复。主控制器只收摘要/路径，不在进程间传整套全warmframe。

**现存canonical/行业状态缺口，采用最低成本解决**

股票母体本阶段只比较原日与neutral `I_target/I_buy`、fresh CP1 boolean/candidate及PVR，按`arm+sid+source+day`保完整日期流；不为1799批量新建金融授权/股票canonical证书。旧stock CP1 receipt不能冒充neutral收据。存储原真实receipt只作对照标签，neutral不声称已进入原生资金调度。

90行业背景如报告stage，必须从各自全warm E0/CP1重建原纯market `industry-mobile-stage/stage.py::run`，不拷旧金融level/容量/ACT。必要receipt轨迹只对90行业复用原 `cp1-evidence-trace/trace.py::trace`：真量先按其既有industry episode来源接口核旧state/receipt；neutral给trace薄输入copy `m=effective_amount_multiplier=1`，原观测m另存。不能直接读原CP1.m当neutral credit。namespace/source manifest明确real/neutral臂，避免相同旧SCALE和sid/day把不同方法receipt错误合并。episode输入沿已验证industry原E0接口，不能把不同旧stock export lineage擅自统一。本阶段不做全部股票canonical平台。需要的trace/Stage仅提取原纯函数/market类并绑定原CP1算术，避免其顶层COM/common导入账户引擎；不为取两个纯函数加载旧金融Runner。

若该90行业薄复用不能精确还原旧state/身份，停stage段；只允许交“E0/CP1 raw背景未含stage”的受限表，不能宣称完整去量的行业许可诊断。

**ACT独立共享层：全1709必须通过的门**

三fixture只验证hook，尚无完整中性ACT。最省成本是先做此共享纯函数门，再花全1799冷算时间。真量复用原 `TradingAlarm/desk/refresh.py::compute_recovery` 及 Q4/experiment.py::prepare 的原caller：原固定1709顺序、原metadata行业映射，原signal close/amount/price_eligible/observed/synthetic/source；22无观察原样记录，调用roster只含按原条件有观察者。必须保固定合并顺序，不按worker完成顺序/新排序汇总。

真量全窗M/prior_high63/breadth/fast_on/breakout对原Q4/recovery.csv核同（含原2022→24及strong共968策略日，及其可比warm时点）。原csv默认解析/round-trip及重算浮点差如有，要逐列列首差/最大差/输入顺序/原文件hash，停止待独审/root定界；不得悄设tolerance、用旧M/breadth替新cold、只看flags相同就称完整exact。

中性仅令**已知可计算**的原 `min(1,sqrt(amount/prior21median))` 乘子为1，再走原EW21/64预热/每行业5股/总8组/.6、原prior63MAX；原乘子未知行仍未知，不因直接u=r放松准备mask。不通过改raw D/V或全填1来改变缺amount/multiplier的可计算日期。中性M作为同价return合成应与真量M相同；只允许breadth/fast/breakout因已知量权变化。保原MAX，不混已关闭A priorMEAN。

这一步需要一个单表达式的共享纯函数wrapper/AST绑定，尚未实现/计时/全域验证，是当前明确接口缺口。必须保存逐股准备/未知mask一致证据，不能把“同factor”当volume可计算证明。若不能保持该边界，停ACT段，不称完整去量。

本阶段只导出ACT**输入**，不运行20%账户DD/flat反馈，不导出`neutral_ACT_on`；旧ACT_on只历史context单列，不作为中性可买日历。原peak/NAV/现金/持仓均不得冻结成neutral策略状态。

**只需三张完整诊断表**

1. `ACTUAL_DECISION_3436`：2265＋1171原买入层/实际买入记录，不称3436个独立orders；budget_order/原订单ID另列去重，不挑亏损或大gap；原budget_order决策、signal_at、原角色/池/first-add-reentry/原买款/原lifetime钱账只作associated列。分别列真实/neutral I有效与fresh I、stock CP1 fresh/candidate、行业各臂E0/CP1/market-stage、PVR值/NA、同日ACT输入/旧ACT历史context。旧实际core_epoch、资金、仓位或已消耗receipt不代入新许可；不能将任一flag合成“neutral一定成交/完整Q”。mobile原continue-Q与core freshI区分，不以I_buy false误判所有mobile都无入口。
2. `ALL_SIGNAL_DATE_STREAMS`：全1709（22保NA）在968策略日及完整warm保存两臂I/CP1日期并集、true-only/neutral-only/both/NA，新增/撤回日期不能因原账户未买过而删；另90行业两臂纯market状态和全ACT输入。前移只用完整 dated stream作事后配对描述，原/中性episode变化须分列，禁止最近邻强当同一机会、未来盈利标签或未来信号倒填当日。若用compact事件并集，还必须保存完整stock-day known/NA/双方均无事件分母（968策略日全1709格及实际观察域分别列），由全neutral原表＋real旧refs逐观察可复核，不能只从changed/union行数谈覆盖。保潜在新增机会完整分母，不能拿固定3436母体代表全部中性机会。
3. `FIXED_ORIGINAL_TAIL_83_94`：固定原名单全部原decision+neutral状态/NA、原signal/fill身份；No60 exact match、同股其它fill、未匹配分开；完整保83/94，而非只45/67。原赢家收益不输入信号，不计算删单或缩量后的模拟NAV。

主输出是许可覆盖、改变作用规模、普通试错/重入与固定赢家的对称归属；当前不新造“质量分数”。L03/L04/303原钱账标签可关联，未知/未匹配不得填0。任何关联原亏损不直接称可避免损失，新增机会也不以事后收益冒充可买回报。

**预算与输出体量（卡估计，未新执行）**

原实测REAL六序列20,296有效行14.406193秒；按4,414,361行线性外推，真量serial约3133秒/52.2分钟，6worker理想约522秒/8.7分钟。neutralfull6单独未记录，v2的51.876927秒含6neutral＋18物理前缀，不能伪拆成neutralfull耗时。仅作双臂等单位成本假设，理想6worker双臂17.4分钟，加35%即23.5分钟；考虑neutral额外B4调用、进程/I/O/ACT/90stage，保守规划25—40分钟，建议未来总墙钟硬预算60分钟、worker<=6。首次原授权批实际吞吐/剩余估算若显著超预算，只报告已落item/瓶颈，不抬时限或调模型。此数不是已测新全导出承诺。

本6序列NEUTRAL features实存约4.79MB，按warm行外推约1.04GB，另compact日期流/90stage/ACT/3436+177表、manifest/check约0.1—0.5GB；预算1—2GB，避免写重复REAL/全量JSONevidence。当前df剩余约122GiB，只作卡时观察，执行前再核。普通item parquet+JSON摘要原子落盘，manifest带源hash/arm/schema/window/状态；可按原freeze核已完成item继续，无金融状态恢复或另一调度平台。

不做1799×18物理重复：直接引用已审三fixture18个NEUTRAL物理前缀（REAL未重算physical），新增reader只核prefix截取/源日期上界/无future关联、ACT共享层最少必要边界检查；不新开参数或“再多几只”样本。任何边界检查需要新增模型运行都必须列在未来明确grant，不能由本卡自动执行。

提案输出根（未创建数据）：`ar6_native_feasibility/VOLUME_FULL_FEATURES_V1/`，中性item及ACT/stage/三表全新；真量只旧ref/hash/parity收据。现卡只写设计、source/metadata清单与估算，不创建worker或导出任何新feature。root另批前保持0 full执行/0账户/0金融事件。
