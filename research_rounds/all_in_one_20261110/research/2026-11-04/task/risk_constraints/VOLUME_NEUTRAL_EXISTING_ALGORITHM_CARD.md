# 唯一对照卡：现有算法的预测量因子中性

**问题**：当前量信息是否在L03/L04及2024Oct后303笔的主要试错损耗中提供实质区别，并保住已冻原PVR tail83/94的赢家？比较原真实量与同算法预测量因子=1；不是新指标、门或策略。信号改日不是成功，既有407科技CP1 PRICE小消融不能代完整1709证据。本卡只提最多3个pure-feature小验证，**当前0实现/0账户/0经济，不启动全池导出**。

| 现有入口 / 量通道 | Neutral精确含义 |
|---|---|
| 原`numeric.event_frame_numeric`→原`e0_policy`，股票及行业E0 | 现成`joint=False`令活动乘子=1；保真实价格位移/原阈值/重锚/观察钟，**不是confirmation=1**；原`decline_candidate=False`不变 |
| B4 `strength_frame`→G1 `classify`→`project(...,'G1_I')` | 现成`joint=False`令新前沿信用w=1、acute量乘子=1；**q_eff=r/s，绝不是q_eff=1**。重建I，不复用真实量grade/target |
| 原CP1 `calculate`，股票及行业 | 现成`price_only=True`令m=1、信用增量=ΔF；保价格/√5与√21尺度。股票valid/down取中性I/原中性事件，行业取中性E0，不残留真实量上游 |
| 原PVR `score` | 金额调制m=1，故e=u；原21权重/score映射/准备掩码不变，重建排序，不沿真实D算旧rank |
| `desk.refresh.compute_recovery` ACT输入 | `r*min(1,sqrt(D/B))`改为r后原EW21/行业广度；保64预热、5股/8行业、.6、price prior63高及ACT20/flat反馈逻辑。不能共同复用真实`recovery.csv`冒称全策略中性 |

**共同输入**：同1709/90、原因果信号价域/真实OHLC及权息、同source连续段与全warm、有效报价/停复牌/可交易mask；实际执行V/ADV/成本保真实共同。D与V原文件不改、不伪造成交额；只中和预测乘子，不能只把rawV设常量却残留D/PVR/ACT。真量分支必须逐值复现冻结`facts/CP1/PVR/recovery`相应字段后，才允许解释neutral差异。不得借原量版父持仓中途切换声称三年全对照。

**最小接线**：复用`refresh.prepare_facts`的B5→G1→I顺序，`numeric`/B4/CP1已有局部开关、原PVR与recovery纯函数可复用；但`build_evidence/prepare_facts`尚无整链neutral入口，原真实缓存也不能直接变neutral。只允许一个薄纯函数装配层接回原状态机，真量路径保持原函数；不import/构造Runner/Account、不复制重写状态机。若必须改大量核心或不能还原观察钟，就停止并报接线未就绪，不把它扩大为平台工程。

| 预选pure-feature小卡（不按收益选） | 固定输入与可验证问题 |
|---|---|
| F1 主板、`verified_case_reuse`字典序首只：000001.SZ＋银行URFI881155 | 股3271/行业4563全暖观察，至2026Jun30；真量能否还原旧复用facts/I/CP1，neutral信用/事件差异能否追溯到量乘子而非价格变化？ |
| F2 创业板、`new_fixed_chain`字典序首只：300001.SZ＋电网设备URFI881278 | 股3186/行业3031；不借旧G1缓存，是否仍复现真实量分支，重建I后CP1资格/候选的差异是否保持正确时钟？ |
| F3 科创板、`new_fixed_chain`字典序首只：688001.SH＋专用设备URFI881118 | 股1682/行业4563，股票从2019上市源起；不足历史/缺原观测留unknown，不能按趋势重置预热、补值或用未来量/价 |

三卡覆盖3板、2生成来源模式，非全provider/板块证明。只读同价全warm，在2021Dec31、2024Sep23与2026Jun30做固定前缀；输出`真实/neutral、sourceSHA、价域/时钟、ready、原事件/I、CP1收据/候选、PVR及变化原因`，不报虚构交易。ACT广度是真1709共同输入，**不能拿3股票toy广度冒全池**；小卡只能定其hook与缓存身份边界，完整ACT中性仍须全池feature阶段。原价格/掩码必须相同。失败段及固定赢家名单作为后续完整母体反例，不更换本三卡来追效果；共同前缀真上涨/失败反弹应在分叉前给同判断。

**数量与成本（未新跑）**：三股＋三行业约20,296行/臂，双臂约40,592行；含CP1/PVR与固定前缀的CPU估30–120秒，接线估30–60分钟，均未实测新adapter。依据旧I pilot约2.8–2.9秒/3300行raw reference；旧1799序列导出实际709.7秒且复用478股，不能当neutral全重建时间。全池至少1799序列，按原reference外推仅股票6worker约13.5分钟，再加行业/CP1/PVR/ACT/I/O，粗估15–30分钟且不确定。**目前不值得直接大导出或账户；先仅三卡判定薄接线可行性。** 小卡通过不等于量有效；若主要失败/赢家信号近乎不变也须记录，不能另调参数救结果。

原算法保持主线；量中性只作必要对照。本卡没有执行授权，也没有启动新算法、特征或经济路径。源入口、固定选择和时间依据绑定于`volume_neutral_card_v1/SOURCE_AND_SELECTION_FREEZE.json`。
