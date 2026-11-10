# 原PVR/NOACT初仓候选漏斗：只读原账诊断

## 结论

能直接研究首仓成员质量的消费者在“原角色与尺寸合格后、原PVR逐股票槽排序前”。全期行业active、空仓且正尺寸候选为PVR 116,831、NOACT 154,944个stock-day；实际首买2,693/3,131笔。它们不是独立样本，也不是已证明能够互换的成交名额。
原PVR没有Top-K删选：所有原pending都保留，只改变OPEN处理顺序。CORE与MOBILE同股耦合、CORE先行；跨行业共用现金、probe/confirmed路线共同约束。此处没有“排名淘汰了多少”的独立日志，不能把预算拒绝全部归因于排名。
同日同行至少2个合法空仓候选并存的覆盖为107,455/142,934个stock-day，约91.98%/92.25%。这支持有范围地研究同业成员质量，只是可比较覆盖；不证明每一次换序都会改变成交，也不是实际预算竞争比例。
旧PVR独立合法empty-MOBILE队列53,121条与本次精确一致；NOACT独立重建67,305条，不能拿旧E31或旧影子M3/K20结果代替。两臂empty-MOBILE按day+sid共同51,741、PVR独有1,380、NOACT独有15,564。

## 冻结与分母

原act_only_ablation_continuous_v1已完成的PVR/NOACT，2022年初120万元空仓到2026-05-15，1054共同交易日，固定1709股/90行业。唯一经济变化仍为NOACT去ACT强平/暂停；本分析account_runs=0、indicator_runs=0，不加载账户引擎，不改旧文件。原48项产物哈希与1799份出生/行业辅助源均核验。
“全市场”以下只指固定1709研究池，不冒充历史全A股。stock-day是一臂×信号收盘日×股票；role-stockday再拆CORE/MOBILE。一个stock-day可有双角色。CP1是新证事件，nativebirth是股票+原E0 segment内0→1出生，实际round为真实0→0或仍未闭回合，四者不可相加或互换。
主漏斗按信号日归窗；成交按对应实际signal_at匹配。另附实际执行日期口径，避免把12月31日信号后的1月首买放错年。完整回合结果截至2026-05-15，只归实际首买执行期，未成交不补收益。

## 全期互斥stock-day漏斗

分桶优先级为ACT→行业G资格→行业active→个股fresh Q→角色/epoch→尺寸→OPEN检查→预算→实际买。它是首个失败阶段的会计分解，原行业active事实上到OPEN route才检查；不能当成原代码先行业预筛或互相独立的因果损失。无信号绝不记为现金拒单。

| exclusive_stage | NOACT | PVR |
| --- | --- | --- |
| 01_ACT_PAUSED | 0 | 430668 |
| 02_SECTOR_SIGNAL_FAIL_OR_UNKNOWN | 343319 | 251299 |
| 03_INDUSTRY_ATTEMPT_INACTIVE | 364607 | 270865 |
| 04_NO_FRESH_SIGNAL_OR_STOCK_Q | 915151 | 712686 |
| 05_NO_ROLE_HELD_OR_CORE_EPOCH_LOCK | 6602 | 5087 |
| 07_CLOSE_SIZE_OR_UNKNOWN_NO_PLAN | 10279 | 8743 |
| 09_OPEN_PRICE_OR_FROZEN_SIZE_REJECT | 423 | 371 |
| 10_OPEN_BUDGET_OR_TOKEN_REJECT | 156544 | 117820 |
| 12_ACTUAL_FIRST_ENTRY | 3131 | 2693 |
| 13_ACTUAL_HELD_ADD | 1107 | 937 |
| 14_RIGHT_CENSORED_NO_NEXT_OPEN | 123 | 117 |

每臂各阶段合计1,801,286 stock-day，精确等于1709×1054。最后一日未执行pending保留右截尾；没有无日志的planned/no-plan残差。

## 指定五个窗口

| 窗口 | 账户 | 固定池stockday | ACT开 | 再过行业G | 再过行业active | 再有freshQ | 合法正尺寸股票日 | 其中flat | 实际首买信号归窗 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ALL | PVR | 1801286 | 1370618 | 1119319 | 848454 | 135768 | 121938 | 116831 | 2693 |
| ALL | NOACT | 1801286 | 1801286 | 1457967 | 1093360 | 178209 | 161328 | 154944 | 3131 |
| 2022 | PVR | 413578 | 350345 | 269107 | 201365 | 26959 | 24079 | 23003 | 762 |
| 2022 | NOACT | 413578 | 413578 | 323232 | 243680 | 35525 | 31698 | 30419 | 784 |
| 2024 | PVR | 413578 | 280276 | 223452 | 153404 | 25344 | 23465 | 22535 | 558 |
| 2024 | NOACT | 413578 | 413578 | 323661 | 230002 | 42042 | 38964 | 37585 | 703 |
| 2024_0920_1015 | PVR | 22217 | 22217 | 20407 | 11050 | 7127 | 6838 | 6636 | 56 |
| 2024_0920_1015 | NOACT | 22217 | 22217 | 20407 | 11050 | 7127 | 6840 | 6641 | 51 |
| 2026Jan | PVR | 34180 | 34180 | 31543 | 28629 | 7134 | 6325 | 6093 | 57 |
| 2026Jan | NOACT | 34180 | 34180 | 31543 | 28629 | 7134 | 6362 | 6104 | 58 |

上表“合法正尺寸”含已有持仓MOBILE；其中flat单独作为首仓消费者。ACT暂停外的原Q可以仍true，但不能形成该臂的待买。原stock Q独立于ACT，全期两臂均214,286个fresh-signal-Q股票日。

## CORE、空仓MOBILE、已有持仓ADD

| account | role | held_at_signal | stage | role_stockdays | native_birth_events |
| --- | --- | --- | --- | --- | --- |
| NOACT | core | False | ROLE_OBSERVED | 186794 | 28036 |
| NOACT | core | False | POSITIVE_SIZE_RANKED | 142252 | 23404 |
| NOACT | core | False | ACTUAL_BUY | 1075 | 1075 |
| NOACT | mobile | False | ROLE_OBSERVED | 82734 | 20999 |
| NOACT | mobile | False | POSITIVE_SIZE_RANKED | 67305 | 18604 |
| NOACT | mobile | False | ACTUAL_BUY | 2056 | 1966 |
| NOACT | mobile | True | ROLE_OBSERVED | 7063 | 2099 |
| NOACT | mobile | True | POSITIVE_SIZE_RANKED | 6384 | 2021 |
| NOACT | mobile | True | ACTUAL_BUY | 1107 | 737 |
| PVR | core | False | ROLE_OBSERVED | 189482 | 28036 |
| PVR | core | False | POSITIVE_SIZE_RANKED | 106618 | 18721 |
| PVR | core | False | ACTUAL_BUY | 879 | 879 |
| PVR | mobile | False | ROLE_OBSERVED | 84208 | 21027 |
| PVR | mobile | False | POSITIVE_SIZE_RANKED | 53121 | 15059 |
| PVR | mobile | False | ACTUAL_BUY | 1814 | 1732 |
| PVR | mobile | True | ROLE_OBSERVED | 5589 | 1767 |
| PVR | mobile | True | POSITIVE_SIZE_RANKED | 5107 | 1705 |
| PVR | mobile | True | ACTUAL_BUY | 937 | 623 |

全期实际初买PVR CORE879+空仓MOBILE1814=2693；NOACT CORE1075+空仓MOBILE2056=3131。另有已有持仓MOBILE ADD937/1107，不能加进初仓数。闭合初买回合只有2626/3064，另各67仍未闭，因此不能把首买2693/3131写成完整回合数。
同股双角色flat stock-day42,908/54,613，故CORE106,618+MOBILE53,121不能直接相加作PVR股票数。CORE没有CP1角色事件要求，表中的偶遇CP1只作观察；MOBILE独立CP1事件数与其role-stockday相同。

## 可精确核的排序后OPEN路径

| account | role | held_at_signal | native_pending | logged_open_attempts | entered_original_route | industry_invalidated | budget_rejected | positive_reserve | actual_first_entry_orders | same_stock_other_role_reserved |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NOACT | core | False | 172171 | 172060 | 171291 | 29785 | 140431 | 1075 | 1075 | 0 |
| NOACT | mobile | False | 79109 | 78466 | 78268 | 11767 | 64445 | 2056 | 2056 | 588 |
| NOACT | mobile | True | 6998 | 6992 | 6937 | 607 | 5223 | 1107 | 0 | 0 |
| PVR | core | False | 126994 | 126893 | 126248 | 20277 | 105092 | 879 | 879 | 0 |
| PVR | mobile | False | 61431 | 60885 | 60718 | 8279 | 50625 | 1814 | 1814 | 493 |
| PVR | mobile | True | 5505 | 5498 | 5445 | 394 | 4114 | 937 | 0 | 0 |

原全部pending unique-stock日数PVR144,926/NOACT194,978，包含当时行业inactive、到OPEN才被route拒绝的股票。只研究合法active子集时相应121,938/161,328；不能把子集误称原完整排序队列。两臂452,208条pending角色均精确对应原rank-policy，排名自身删减0条。
entered_original_route从OPEN原日志及preview顺序核定，不把missing_open或开盘价格/尺寸preview拒绝算已过route。positive_reserve与实际BUY全期均7,868笔；一股同日CORE先保留时MOBILE被跳过另列，不能叫资金拒绝。OVERLAPPING_OPEN_REASONS_BY_ROLE.csv分别列现金、probe风险、行业资本/风险等可同时出现的原拒因，不把原因行数相加当拒单笔数。
CLOSE_TO_OPEN_PENDING_COUNTS.csv给每个信号日的原完整pending股票数/角色数、实际route进入、reserve、初买与拒绝数。可核的是这些原账事实。换序是否可行、是否改成交量或未来状态均UNKNOWN，需另做固定动态反事实，本任务未执行。

## 同一nativebirth的覆盖

| period | stage | PVR | NOACT | common | PVR_only | NOACT_only |
| --- | --- | --- | --- | --- | --- | --- |
| 2022 | ACTUAL_FIRST_ENTRY | 742 | 770 | 615 | 127 | 155 |
| 2022 | POSITIVE_SIZE_RANKED | 5192 | 5357 | 5192 | 0 | 165 |
| 2024 | ACTUAL_FIRST_ENTRY | 537 | 670 | 415 | 122 | 255 |
| 2024 | POSITIVE_SIZE_RANKED | 3893 | 5655 | 3888 | 5 | 1767 |
| 2024_0920_1015 | ACTUAL_FIRST_ENTRY | 56 | 50 | 39 | 17 | 11 |
| 2024_0920_1015 | POSITIVE_SIZE_RANKED | 1545 | 1546 | 1540 | 5 | 6 |
| 2026Jan | ACTUAL_FIRST_ENTRY | 57 | 57 | 41 | 16 | 16 |
| 2026Jan | POSITIVE_SIZE_RANKED | 1389 | 1397 | 1367 | 22 | 30 |
| ALL | ACTUAL_FIRST_ENTRY | 2575 | 2999 | 2038 | 537 | 961 |
| ALL | POSITIVE_SIZE_RANKED | 19225 | 23824 | 19224 | 1 | 4600 |

全期原有flat角色的nativebirth两臂均28,229；行业active及尺寸后的可排序事件19,225/23,824，实际首买事件2,575/2,999。共同实际首买事件2038，PVR独有537、NOACT独有961。一出生可多次重入，故事件数小于初买笔数。局部窗口只表示该窗口有相应候选/首买，不按birth年份归窗。
NATIVE_BIRTH_CROSS_ARM_ROSTER.parquet提供每个出生、阶段及单臂/共同成员清单。不是原I big60事件；没有重用4359 big60分母，也不跨臂按round_id匹配。

## 实际后来赢家与30%完整净回合，只作事后描述

| account | initial_role | first_entries | complete_rounds | open_rounds | complete_winners | complete_win_rate | complete_30pct_rounds | complete_round_net |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| PVR | mobile | 1814 | 1773 | 41 | 465 | 26.23% | 52 | -234675.33 |
| PVR | core | 879 | 853 | 26 | 210 | 24.62% | 21 | 82333.08 |
| NOACT | mobile | 2056 | 2022 | 34 | 554 | 27.40% | 76 | 42656.09 |
| NOACT | core | 1075 | 1042 | 33 | 244 | 23.42% | 28 | -35508.47 |

PVR 73、NOACT104个≥30%实际完整回合来自所有实际BUY含费本金分母，包含ADD。初买MOBILE分别贡献52/76个，CORE21/28个。它们不能转成未入选候选的获利标签，不能以“后来赢过”反选当时候选。
POSTHOC_ACTUAL_WINNER_COVERAGE.csv列各层nativebirth后来在同臂是否确有闭合总净赢家/≥30%实际回合，以及该臂完全无实际回合的数量。无回合只写缺失、不标输也不标赢；某个birth另日后来成交获利只说明事件覆盖，不意味着此前任一未成交stock-day按当时买入也获利。
ACTUAL_FIRST_ENTRY_COHORT_OUTCOMES.csv给五窗口按实际首买执行日归组的闭合/未闭/胜率/右尾。2024实际首买553/698与信号归窗558/703不同；2026Jan为执行51/59、信号57/58。不得混用。这是同开发样本已见历史，不是新成员质量alpha检验。

## 下一层可改什么，不能据此声称什么

1. 市场层ACT只控制能否继续候选/持有；取消ACT扩大合法首仓覆盖，但全账户与CORE胜率并未普遍提升。本漏斗不另建议新的全市场硬门。
2. 行业层有原G资格与active授权两道不同约束；行业公共特征可改变行业间优先级，却不能自行区分同业个股成员。
3. 个股层最直接的首仓质量消费者，是合法空仓CORE/MOBILE的逐股票优先级；同业并存覆盖大，值得在同一原合法域内比较事前个股推进/风险，而非扩张资格后把新增交易视为提升。
4. 收盘资格、角色和尺寸先于预算实现；真正改排序会改变同股CORE/MOBILE竞争、现金/池分配及后续空仓状态，所以旧独立MOBILE K20只能作诊断，不可直接当作只改一个键的账户因果证明。
5. 此处只定位消费者和覆盖，不新增评分、不扫描参数、不做新账户大回测。固定未来池/当前行业NON-PIT、外部历史可交易性UNKNOWN等限制保持。

## 文件与复验

analyze_readonly.py重建原trace及主表；finish_readout.py只读新trace生成route补充与本报告。QA.json和INPUT_SHA256.json保存检验与原源hash。旧数据未改、经济账户运行0。
- STOCKDAY_FUNNEL.csv / EXCLUSIVE_STOCKDAY_STAGES.csv：股票日累计与互斥漏斗。
- ROLE_FUNNEL.csv / EXCLUSIVE_ROLE_STAGES.csv / ROLE_CANDIDATE_TRACE.parquet：角色、空仓/持仓、nativebirth及逐条原结果。
- EXACT_ROUTE_AND_ORDER_COUNTS.csv / OVERLAPPING_OPEN_REASONS_BY_ROLE.csv / CLOSE_TO_OPEN_PENDING_COUNTS.csv：原route、订单与重叠拒因。
- CONSUMER_COVERAGE.csv / FIRST_ENTRY_TWO_CLOCKS.csv：首仓研究域、同业并存和双日期口径。
- NATIVE_BIRTH_CROSS_ARM_OVERLAP.csv / NATIVE_BIRTH_CROSS_ARM_ROSTER.parquet：统一出生事件两臂共同/单臂。
- ACTUAL_NATIVE_BIRTH_OUTCOMES.csv / POSTHOC_ACTUAL_WINNER_COVERAGE.csv / ACTUAL_FIRST_ENTRY_COHORT_OUTCOMES.csv：仅实际交易的事后结果。
- OLD_EMPTY_MOBILE_QUEUE_IDENTITY.json：旧PVR空仓MOBILE的精确同源验证。
- STAGE_DEFINITIONS_AND_UNKNOWNS.json：定义、优先级、字段边界与UNKNOWN。

## 合并失败/UNKNOWN桶的最终细分

主漏斗不改。补表 MERGED_STAGE_KNOWN_UNKNOWN_SPLIT.csv 对五窗口、两臂逐项拆分：

- 02_SECTOR_SIGNAL_FAIL_OR_UNKNOWN：全期PVR251,299、NOACT343,319个stock-day全部来自原日志明确的 sector_up:false；两个账户原机会拒因全量计数中均无 sector_up:unknown，故该桶UNKNOWN为0。不是把缺失值填成false。
- 07_CLOSE_SIZE_OR_UNKNOWN_NO_PLAN：全期PVR8,743、NOACT10,279个stock-day，全部角色均有明确原CLOSE拒因 minimum_unit_exceeds_risk_or_nominal_cap 或 no_nominal_gap；缺失/不可识别为0。同股双角色原因可能不同，互斥组合另存 CLOSE_SIZE_STOCKDAY_REASON_COMBINATIONS.csv，不重复加总为股票日。
- 额外只核已冻结90份行业state的有效列：94,860个sector-day全部存在，E0_valid/stage无缺失，正stage没有缺attempt_id。attempt_id为空是原状态机明确的无活动attempt，不冒充资料缺失。
- 以上“UNKNOWN=0”只适用于这两桶及所核字段，不代表所有历史状态或实盘执行均已知；原资料中其他个股/common-ready UNKNOWN、NON-PIT、真实可交易性及动态换序结果的UNKNOWN边界保持。合并阶段名称只是通用分类保留，未更改任何主计数。
