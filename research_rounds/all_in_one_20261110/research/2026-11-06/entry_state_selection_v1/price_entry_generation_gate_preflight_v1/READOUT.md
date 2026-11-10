# PRICE 初仓结构：事件层预检

## 当前结论

本次没有找到可以解释全部 PRICE 亏损的新指标。outside 双向区间扩张在两窗共同 BUY 中仅占 9.05% / 9.42%，尺度分布接近，且同时存在于 2025 江丰第一次量确认；不能把它预认成坏信号，也没有据此形成新消费者。

唯一继续检查的候选是**原 PRICE root 内的 entry-generation gate**。它继承旧 E1/E3 的假突破语义及 11/04 资格/持仓分离理论，不是新理论。只给尚无 probe parent 的初仓增加一项市场资格，保留原 root、receipt、Q、S、ADD、余量、排序与退出。

已封存事件身份显示，它只改变原共同 BUY 的 117/1779（2022）及 50/1083（2024），不能声称解决大部分 PRICE 损失。没有读取未来结果来定式，没有执行经济或计算删单后的收益。后续原账结果关联另有独立协议与全分母，不把原路径标签当反事实。

## 一、来源排重

- R/independent_channel_probe_preflight_v1/core.py::simulate：原 birth 就是 prior20 High Donchian 上破；Q 是 DAP 式新 logClose 前沿乘 min(1,sqrt(A/B))，CONFIRMED 只支持后续 ADD，不是初仓门。
- R/check_frozen_cases.py:33–57（旧 E1）：C<B−ATR、连续两收盘<B、或放量阴跌<B 可杀机会，5条冷却后重生；candidate 另需 i_buy、C>B、Pcap；同一失败还用于影子退出。因此已研究假突破，但不是这里保持持仓 S 不变的独立 PRICE 初仓分流。
- R/local_v2/run_local_events.py:42–69、R/epoch_v3/rolling_prebreak_v31/check_epoch_semantics.py:38–70：LOCAL_FAIL、REPAIR_WAIT、RECLAIM/NEW_BASE 及旧 I 内重建已经存在。不能换名再称新指标。
- 2026-11-04/task-3/entry_quality/e0_i_structure_redesign_v1/SIGNAL_FREEZE_V2.md:31–50：跌回 K_A/H12 撤新增资格而 P 未破继续持有；后来站回同门恢复。资格不等于保护的理论已存在。这里是原 PRICE 内不可恢复旧 entry-generation、只由新 prior20 High 重生的具体应用。
- money/research_rounds/continuous-protection-lines-20261028/code/model.py::calculate：CP 依 I/e0_down/source 重置，UP 中普通回撤不清信用；没有独立出生 U 的本门。
- R/donchian_keltner_component_v1/REPORT.md：旧冻结1ATR推进成熟、3ATR/L20及2S后4ATR保护已做，不重做；本候选不以 ATR 要求额外上涨，也不改保护。
- R/price_dmi_priority_dynamic_v1/READOUT.md：DMI 已有完整动态槽内排序，增益有限；本次不换 DMI 参数或再造排序。EMA/RSI已有 close 推进或强弱重合，不能额外投票叫独立证据。

## 二、唯一冻结定义

主 PROTOCOL.md / diagnose.py / FREEZE.json 在事件计算前落盘。公式、阈值、病例不根据结果更改。

每个原 PRICE 父 root：
1. 原 birth 建第1代，冻结 Ue=原 birth prior20 High。
2. 后续父 FAIL/UNKNOWN/source 不可比优先终止其机会代。
3. 活代首次收盘 C<=Ue 即退役；同日不再生。
4. 只有在此前已退役且本日 C>连续同源 prior20 High 时建新代，冻结新的 Ue。
5. 活代内另一次20High不换代。旧代不可恢复，无固定冷却、量门、ATR门或年龄门。
6. 初仓资格必须仍有**原严格新 close-frontier receipt**且当前代活跃。新代 birth 本身不产生额外原 PRICE 票，不声称增加较低价机会。
7. 原 probe parent 已存在时，包括真实0-fill/partial及其固定Q余量，本门均不读取；ADD与退出不变。generation 只作资格来源注释，不能换 root_id/parent_id或多建probe。

原 REGISTERED 表是已登记 round/SELECTED_PENDING，不等于 execution target_registered。3621轮中28未BUY不能当作真实zero-fill；真实订单/ACK/fill均未提供。本文 BUY 一律是条件 next-common OPEN 全填代理。

## 三、可事前证明的作用域

在原 receipt 日，C 是原 root 全历史新 close 高点。所有此前代的 Ue 都严格小于该代出生 Close，因此本日不会穿破任何活代 Ue。
若此前无活代而当日真破 current20High，必新生并通过。

所以本门 DENY 只能来自「旧 root 续票且当前不是20High突破」。
2022共同 BUY 的理论上限231/1779，2024上限183/1083；实际更小。它严格弱于直接20High总门，不可与该总门混称。

| 范围 | 2022 ALLOW / DENY / 总数 | 2024 ALLOW / DENY / 总数 |
|---|---:|---:|
|全部原 receipts|21547 / 3186 / 24733|12143 / 580 / 12723|
|原登记轮|2257 / 154 / 2411|1154 / 56 / 1210|
|原实际代理 BUY|2241 / 154 / 2395|1142 / 56 / 1198|
|正式共同 BUY|1662 / 117 / 1779|1033 / 50 / 1083|

所有原 born 4057 / 1790 张票全部保留；共同 born 1288 / 500也全部保留。
共同 non-current20High 231 / 183 = DENY 117 / 50 + ALLOW 114 / 133。
共同 BUY 曾回出生 U 的281 / 155条中，164 / 105已合法再生后通过；不能用 ever-returned 永久一刀切。

共同首次全策略 BUY 被影响70/636、47/883；先AB后首次PRICE为9/249、2/62；重复PRICE为38/894、1/138。
主要已知 cell「首次全策略BUY+续票+E0/I on+CONFIRMED」只影响63/287、45/549，不是该cell全部被阻断。此前窗口内是否已有实际参与，以及窗口前root左边界另由原账关联明确分列，不外推连续账户。

## 四、固定病例，盈亏身份不参与定义

- 浪潮000977 2022-01-05：原root10/26；第3代12/09生、12/17退役，本日仍非current20High，DENY。
- 力鼎605118 08/22：原新birth，第1代ALLOW。这项门不修复该新birth失败。
- 永和605020 07/15及巨轮002031 06/13：原新birth，第1代ALLOW，不禁止洗出后更高重入。
- 游族002174 11/08：第1代11/02生、11/03回U退役，11/08非current20High，DENY。已知大赢家反例必须保留，不能事后豁免。
- 电气风电688660 2024-09-25：原root7/24，曾回箱但9/25第3代真20High重生，ALLOW。
- 华电600396 10/28为第1代ALLOW；歌尔002241 9/30、共创605099 12/11新birth都ALLOW，不抹去失败反例。
- 福莱605488 9/30、杭钢600126 12/11、银轮002126 12/25全保留原born。
- 海能达002583 9/20/23/24/25：第1代均存续且原receipt真。这里只看信号gate，行业false/AB优先和交易执行没有重审或改写。
- 江丰300666 2025-12-15/17：第1代通过。2026-01-05已第3代真20High重生、1/15仍第3代通过。1/30、2/2、2/5缺源维持UNKNOWN。
- 金海通603061 2026-01-05第2代重生，1/15仍通过；1/15 current20High=false、原receipt=true，是本门不等于直接20High门的具体证据。

追加2026/924病例在主v1封存后由父任务指定，另存 supplement_v1/v2 协议；没有偷偷加入主锁或据其结果改式。

## 五、outside及S/ATR诊断结果

详见相邻 price_outside_range_diagnostic_v1。定义先在协作消息冻结、两个只读计算后才保存磁盘文件；不能称磁盘预注册。

outside=(H_t>H_prev 且 L_t<L_prev)，a=H_t−H_prev、b=L_prev−L_t，B2=min(max(a,0),max(b,0))；以严格此前 Wilder ATR14及TR作尺度，不设新门。DMI在outside只保留较大一侧是信息折叠，不等于已证缺陷。

共同 BUY：
- outside 161/1779（9.05%）与102/1083（9.42%）；其中现有d>0为158/161、102/102。
- B2/ATR中位0.144 / 0.141，B2/TR两窗约0.071；不能以一窗叙事认定它是失败特征。
- outside / 非outside 的TR/ATR中位2022为2.017 / 1.625，2024为1.861 / 2.044，outside不等价单纯高振幅。
- 有既有 S_old 的共同续票491 / 583条，当日Low<=S_old均为0。Low<=S_new有10 / 7条，全部是当日E0抬线，不能说入场前已有支持被盘中击穿。
- outside内Low<=S_new的5 / 3条也全是新提线，旧S触及0。
- 力鼎8/22是outside；浪潮、华电、歌尔、共创不是。江丰12/17首次量确认也是outside。未形成outside消费者或经济测试。

## 六、验证边界与文件

- 主事件预检：37456 receipts、3621原登记轮、6494原root递推前缀exact，1632源文件哈希不变，无PnL/未来结果列、无经济循环。
- 主脚本只到原root最后一张已知合法receipt；源不连续时assert，不实现所有父FAIL/UNKNOWN三值输出或消费者pending分流。该接口仍未验证，不称可直接上线的完整consumer。
- supplement_v2：1628股物理raw截断后重算rolling prior20High、validity及source字段mask/known值exact；8追加病例。
- supplement_v1停止于同NaN identity被np.array_equal当不同，未产出病例。定位两缺源日；v2只修检查器三字段比较，主gate和原keys未改。
- 原静态1709名单/行业及历史资料NON-PIT；两窗独立FLAT，不是连续账户；UNKNOWN与代理可成交性限制不变。
- 主事实：RECEIPT_GATE_FACTS.parquet、REGISTERED_ENTRY_GATE_FACTS.csv、SUMMARY.json、INTERSECTIONS.json、FIXED_CASES.csv。
- 冻结：PROTOCOL.md、diagnose.py、FREEZE.json；来源：SOURCE_HASHES.json；主输出：OUTPUT_HASHES.json。
- 补充：supplement_v2/{QA.json,PHYSICAL_PREFIX_CHECKS.csv,SUPPLEMENTAL_CASES.csv,HYTERA_GATE_CHAIN.csv,OUTPUT_HASHES.json}。
- 原账结果关联如完成后在 old_result_association_v1 单列。它不是新策略胜率、避免损失或可交易收益。
