# 成熟趋势理论的跨研究证据盘点

## 给当前问题的直接回答

不能说“所有尝试都不如 PVR”，也不能说“成熟指标已经公平比过、PVR 获胜”。目前查到的是三类不同证据混在一起：早期确实重构过 E0/G/I 并做经济比较；近期大量实验仅在原许可集合内小幅融合或折减 PVR；还有不少仅做病例、数学或保护影子，尚无新经济结果。

保留 PVR 作为固定对照本身合理，但把新理论长期限制为它的附加项，使研究目标从“发现更好的底层入口”收窄为“有没有更好的原队列排序”。后者未成功，不等于前者已被否定。不能用“不晋升”的共同标签隐藏这些差别，也不能把大量数据审计、权益修复和解释性诊断算成同等数量的新策略测试。

本盘点只读源码、报告和已保存结果，不重跑任何资金、逐股生命周期、指标扫描或新经济。范围为 10/20–11/06 可定位的指定研究树，不能声称穷尽所有会话。

## 比较证据应分层

- A：同一合同下实际重新运行经济路径，包含自身交易、费用、资金或逐股净额。仍须保留原执行代理、非 PIT 和开发历史限制。
- B：原许可/原状态条件下的同日 TopK、固定期限价格路径。不是费后完整回合胜率；没有重新生成全部入口、状态与资金。
- C：病例、旧回合关联、公式检查或保护影子。可以证明差异或否决具体接法，不足以判定整套理论的收益优劣。
- D：只有说明或纸面设计，未实施对应消费者。

本报告的A/B/C/D仅为本次证据层级说明，与用户原A+B入口类别无关。

## 1. ADX / DMI：确实实施，主要仍是 PVR 融合；独立 ADX 策略未获同合同经济验证

标准竞争方向量：up=H−Hprev，down=Lprev−L；+DM 只保留 up>down 且 up>0，−DM 对称。A/B 为 RMA14 的正负 DM，d=(A−B)/(A+B)，ADX=RMA14(100|d|)。TR在d中相消，ADX强不等于上涨强。

实施式：E=atanh((PVR−50)/50)/2；E*=E+0.25*d*max(E,0)，再映回PVR。对照用相同平滑的收盘方向比例 dclose=RSI14/50−1。不是“ADX取代G”，也未设ADX>25硬门。

- MOBILE（B）：2022至2026-05-15开发历史，53121个原合法空仓候选、14185入选槽，固定同行业名额；DMI仅换49槽。共同完整日期等权20/60日价格增量 +0.004289/+0.007523个百分点，描述区间跨0。成熟大行情根早捕708→707。
- CORE（B）：106618合法股票日、800日、1651股；15185槽，同行业×是否同时有MOBILE资格固定名额，仅换58槽。20/60日增量 +0.00213/−0.02956个百分点。原Top20覆盖的786个真实CORE首仓三臂相同。
- 结论：没有足以晋升的该融合增量；不是DMI全策略收益低于PVR的证明。

证据：dmi_boundary_migration_v1/REPORT.md、experiment.py；core_stock_selection_dmi_v1/REPORT.md。源码experiment.py第55–59行可核融合，第100行可核两对照。标准机制来源：[StockCharts ADX](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-indicators/average-directional-index-adx)。

## 2. 唐奇安 / ATR：有真正不同的事件源实现，但仍未做新经济

此前通道 U20=max(H[t−20:t−1])，首次收盘越轨冻结 A=C、S=前日ATR14；此后新收盘前沿F每跨一个未消费的 floor((F−A)/S) 格，才发推进事件。保留E0初期试探，重复E0不重置已消费格。保护为旧线优先，其后 max(Pold,硬结构线,此前持有峰−3*ATRprev)。

这不需要原CP收据，确实是不同于PVR和CP的推进状态机；但不是从头独立替换E0/G，START仍来自原E0。先前纸面20/55通道不能误算成两套已完成经济。

- 已实施（C）：五股真实完整状态轨迹；2022–23原母体35713原CP锚、2024年9–12月12412锚、2025–2026H1半导体2901锚，共51026原锚。
- 同锚ATR3与CP保护影子：前三组已知双方退出时，ATR较早/同日/较晚分别12126/19906/3620、3877/7169/1335、662/1475/361，删失和无报价另列。
- 新FSM成熟也可能晚，如金海通2025-11-06 START、12-22通道、2026-01-05首成熟推进。
- 未建立账户、数量、费用或新净收益。影子较早退出及条件回撤不等于入场胜率更好或更差，不能列作“经济败给PVR”。

证据：2026-11-04/task-3/entry_quality/channel_atr_fsm_v1/RESULTS_READOUT.md、FREEZE.md、engine.py。此前纸面：channel_atr_v1/PAPER_SPEC.md。标准通道来源：[Price Channels](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/price-channels)。

## 3. Keltner / Chandelier / Supertrend：保护用途和理论说明，不是新的选股胜率试验

- Keltner已实施（C）：EMA20±2ATR10，原初仓P0不动；仅当当前C高于本层入口参考且fresh CP时，用前日KC下轨上限限制本次CP提线。10个固定CP锚、9股、20条条件影子；6锚延后、4同日，延后仅银之杰早锚下一OPEN参考更高，其余更低。没有净收益或新首仓。
- Chandelier式ATR3：上一项已有实施，但不是经典22期高点减3ATR22逐点复刻。
- Supertrend：正式公式和状态语义已写，未找到本范围内对应独立消费者/经济运行。不得把介绍公式计成策略验证。
- 这些用途多数改变保护，不直接回答“初仓买谁、何时买”。

证据：donchian_keltner_component_v1/REPORT.md、replay_keltner_cap.py。公式：[Keltner](https://chartschool.stockcharts.com/table-of-contents/technical-indicators-and-overlays/technical-overlays/keltner-channels)、[TradingView Supertrend](https://www.tradingview.com/support/solutions/43000634738-supertrend/)。

## 4. MACD：只证明当前融合在固定域不动，不是独立MACD败了

固定log-MACD：DIF=EMA12(logC)−EMA26(logC)，DEA=EMA9(DIF)，hist=DIF−DEA。DIF/7为两层平滑速度，hist/28为三层平滑加速度；原G已有EMA5/21收益速度差，不能把MACD当独立新信息投票。

实际消费者只在负收益负荷增加、MACD加速度负、原G快加速度负同时成立时折减正PVR：E*=E−min(max(E,0),L/s)。

- 实施（C）：19股22固定点、613原CP前缀；367合法空仓MOBILE中改变0条。
- 没有全机会新排序，更没有新经济。旧“正DIF乘CP信用”仅有上级传来的内存结果，报告明确没有持久原结果，不能给它同等级证据。
- 原版价格MACD亦只作单位/符号核查，不是第二策略。

证据：macd_acceleration_attribution_v1/REPORT.md、fusion_readonly.py、LEGAL367_CP_STATES.csv。

## 5. RSI：既有替换排名，也有PVR融合；不是标准RSI14独立入场系统

项目Q为量价加权log收益RMA21：U=RMA21(m*max(r,0))，D=RMA21(m*max(−r,0))，Q=100U/(U+D)。它不是原版价格差Wilder RSI14。

- Q直接替换PVR（B）：103766双账户合法MOBILE候选。主PVR域20日等日增量，2022–26分别 −0.188/+0.025/+0.584/−0.036/−0.480个百分点；各年MAE更差、大行情净捕获下降。
- Q折PVR正信用（B）：E*=E−(1−Q/100)max(E,0)。53121主PVR合法候选、796日队列、14185槽。代码为全日Top20，不是DMI的固定行业K合同，不能混作同组公平总榜。
- 后者20日增量 −0.1734/+0.0826/+0.3310/+0.0315/−0.0284个百分点；924局部+2.0488个百分点，但各年MAE恶化，2022–25大行情早捕均少2–3根。
- 标准RSI14只做固定案例解释。没有新费后完整账户胜率，不能说“RSI比PVR差”而不限定消费者。

证据：rsi_pvr_credit_fusion_v1/READOUT.md、reproduce_readonly.py第15–28行；原替换报告位于selection_entry_diagnosis_v1/cp1_signal_mechanism_v1/soft_cp1_quality_v1/candidate_test/REPORT.md。

## 6. OBV：本轮只到旧回合关联，没做完整候选重排

标准OBV累计 sign(ΔC)*V；实际试验是q21=Σ21(sign(r)*V)/Σ21V，再 E*=E−max(E,0)*max(0,−q21)。不是完整OBV趋势或背离系统。

- 实施（C）：原共同已知闭合MOBILE1749局，仅46局被折减，其中14局原盈利，30.43%高于全体26.19%。4个年份q与胜负方向不利，融合AUC变化极小且不一致。
- 29固定日期前缀和数学边界通过；未做全机会重排、TopK新路径、大行情新覆盖或经济。
- 对旧已买回合的关联不能成为未买候选的反事实胜率。

证据：obv_pvr_mechanism_v1/REPORT.md、reproduce_readonly.py。标准定义：[Fidelity OBV](https://www.fidelity.com/learning-center/trading-investing/technical-analysis/technical-indicator-guide/obv)。

## 7. EMA / 布林：确有同合同经济，但并非全都更差

### EMA严格排列入口（A）
EMA9>EMA21>EMA50且三线各向上，只增加原E0/I新买门，持有退出仍原规则。2021-01-04至2026-10-16，半导体126、通信43、创新药48、银行39四固定池，各100万，15%初仓、六槽及原费用执行不变。

半导体E0净收益/回撤 −15.95%/76.21% → +18.10%/71.92%，这是明确的局部改善，不是PVR对照。但I四池收益均下降；半导体I胜率30.38%→33.55%，收益205.89%→144.20%。不能只用胜率或只用一个池晋升。

证据：money/research_rounds/ema-gate-e0-i-20261026/CONCLUSION.md。

### EMA/布林提前退出（A）
原No60框架，保留E0/I/PVR，另加C<EMA20、C<EMA60、C<SMA20或C<SMA20−2std20退出。2022–24连续三年和2025-07至2026-06两个固定账户窗，100万起。

EMA20三年末63.799→63.974万元，回撤38.088%→37.456%；上涨窗226.328→244.736万元，回撤11.660%→13.195%。布林中轨上涨窗末257.827万元优于原，但三年末61.875万元劣于原。存在局部增益和风险代价，不是全部失败，更不是入口质量已解决。

证据：2026-11-04/task-3/entry_quality/trend_exit_controls_v1/REPORT.txt。

### 布林入口/CP信用的新接法（C）
另一个20固定日、17股的两时钟修复，使价格先越前日上轨、后续CP可恢复信用；固定域分数变化0。它没有经济，不可与上面的10账混称同一次验证。
证据：bollinger_cp_formula_comparison_v1/REPORT.md。

## 8. 早期并非从未改底层，不能把整段工作改写成PVR冠军赛

2026-10-26综合复核的I=G1入场+E0持有，四同合同股票池较原E0三池收益更好、银行更差：
- 半导体E0 −15.95% → I +205.89%；
- 通信 +231.31% → +492.84%；
- 创新药 −1.69% → +25.55%；
- 银行 +31.51% → +8.28%。

这是旧固定池下的E0/G/I政策比较，不是当前初仓A+B合同，不可移植为当前胜率。回撤仍为48%–69%等高水平，非通用成功。

10/20事件结构版在ETF17/HK7也真实做过量价、去量和事件退出经济对照。量价净收益3.75%/9.17%，去量7.39%/17.48%；旧同池SMA63约1.12%/−7.46%。这些不是A股1709池、不是现PVR体系，也不是应直接采用的结果。它们说明早期有底层研究及正反证，后来不能全部压缩成“PVR仍最强”。

证据：money/research_rounds/strategy-performance-review-20261026/ASSESSMENT.md；pv-event-structure-20261020/results/review.md。本轮只复核存档，未重新审计其全部原账户。

## 9. 原始文献也不支持把成熟指标排成确定冠军

- Jiang、Tong、Song，2019，Technical Analysis Profitability Without Data Snooping Bias（DOI 10.1111/irfi.12161）。作者学校说明其1997–2015中国市场研究包含近3万规则，多重检验后约170条保留，并报告交易成本敏感性。这是指数择时证据，不是当前股票入口净胜率。[作者学校原介绍](https://sf.cufe.edu.cn/info/1157/5209.htm)
- Zhu、Jiang、Li、Zhou，2015，Physica A 439，75–84。上证1992–2013、深证1991–2013，MA与TRB控制数据挖掘后无成本有优势，计交易成本后消失。[作者预印本](https://arxiv.org/abs/1504.04254)，[正式DOI](https://doi.org/10.1016/j.physa.2015.07.032)
- Chuang等，2024，Pacific-Basin Finance Journal 84，102278。2010–2021上证与创业板、38456规则；多重检验后仅少数复杂规则赢上证，无规则赢创业板，样本外计费后多数优胜规则转负。[作者大学记录](https://scholar.ntpu.edu.tw/en/publications/profitability-of-technical-trading-rules-in-the-chinese-stock-mar/)，[DOI](https://doi.org/10.1016/j.pacfin.2024.102278)

三文方法、样本、费用、指数和规则集合不同，不能用新论文简单覆盖旧论文，也不能把任何一条指数结果当作全A股逐股T+1入场效果。2024全文访问403，本轮核实作者大学摘要，不捏造其具体最优参数或成本值。

## 10. 本轮研究优先项：不提名新的指标消费者

本轮符合“已有实证支撑、非PVR重命名、有明确增量机制”的可晋升新入口候选为0。通道状态机虽确实不同，但已有反例且尚无经济优势；DMI等小幅融合不能靠换成硬门获得正当性；外部论文没有提供足以直接落地到本用户合同的唯一胜者。

纠偏应先承认研究对象错位：若下一任务决定重做底层入口，应允许候选产生自己完整、因果的新机会及失效时钟，以共同可交易股票日和相同执行/初仓/退出合同对照，而不是只在原PVR已筛选机会里动分数。否则新入口在母体之外的能力永远测不到。这是一条比较设计要求，不是新策略，也不在本轮启动大测。

不能继续用“先随意选一个软融合，固定病例没好就否定成熟理论”的循环消耗时间。也不能为了回应用户的失望强推没有支持的新指标。
