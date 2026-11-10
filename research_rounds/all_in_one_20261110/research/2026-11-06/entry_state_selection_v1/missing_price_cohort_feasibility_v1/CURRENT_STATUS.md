# 2023和2024前八月扩窗执行与审计结果

**当前状态：两个新出生窗均已完成全1709池的AB与PRICE联合现金回放，独立账本和标签审计通过。** 2023新增严格ordinary PRICE标签2139条，2024JanAug新增1080条；另有10条已许可且实际结清的权益场景标签单列。没有真实订单，没有模型拟合，没有改写旧窗。

旧 `distribution_objective_feasibility_v1/MARKED_RETURN_DESIGN.md`、`LABEL_MATURITY_READOUT.md`、`BASELINE_READOUT.md` 是补窗前支持快照。其中“2023/2024前八月缺出生标签”已不是当前事实；原文件、原审计数与旧经济账全部保留。最新按cut、P/D/C可用性和模板分层的支持解读见 [EXTENDED_CURRENT_STATUS.md](../distribution_objective_feasibility_v1/EXTENDED_CURRENT_STATUS.md)，数表以同目录 `EXTENDED_` 文件为准。本目录早期 `READOUT.md` 是可行验证与执行前边界记录，以本文件更新其执行状态。

## 固定合同和运行范围

- 两窗统一使用原2024消费者及原165条NET80权益许可；模板为 `ORIGINAL_2024_AB_PRICE_165_NET80_STRICT_UNKNOWN_V1`。原NAV=1,200,000、INIT=24,000、SLOT=48,000、RISK=3,000和dated费用保留，AB/PRICE所有权、行业两槽竞争、PVR排序、ADD、退出和责任冻结均沿原实现。
- 旧2022另有不同责任门和权益集合，不能默认为同合同样本。没有合并436条旧许可，没有补新权益证据，没有把UNKNOWN记零。
- 2023出生边界为2023全年；2024JanAug为2024年1–8月。两窗独立执行FLAT，市场历史完整暖启，管理到2026-06-30。它们不是跨年连续账户，未接续旧2022持仓，也不把2024JanAug状态写入旧SepDec。
- 每窗独立新run-once记录。新输入、协议、代码经独审与父任务授权后顺序执行，各只运行一次，无经济重试。冻结的协议和代码没有事后修改。

## 保存标签和未解决覆盖

| PRICE登记域 | 2023 | 2024JanAug |
|---|---:|---:|
| 登记回合 | 2481 | 1460 |
| 严格ordinary完整标签 | 2139 | 1080 |
| ordinary占登记回合 | 86.2% | 74.0% |
| ordinary覆盖股票 | 1201 | 815 |
| 已结清非ordinary权益场景 | 0 | 10 |
| 路径或入场UNKNOWN | 294 | 341 |
| 已闭合但完整财务覆盖未知 | 43 | 27 |
| q0未提交 | 5 | 2 |
| 终点已知权益pending | 0 | 0 |

UNKNOWN细分：2023为未准入行动路径274、缺OPEN路径10、入场未准入行动10；2024JanAug分别323、15、3。UNKNOWN责任并未结清，已成交部分算术可核不代表总净额已知。终点pending为0也不代表未知权益已解决。

严格ordinary要求无任何claim/bridge/claim-ledger/owned-registration触碰，财务原因为LOCAL_NO_ACTION_EVIDENCE，库存和权益余额为0，数量、现金、费用、首末动作均与保存账对齐。10条非ordinary单列为financial-settled，结清时间来自实际PAY_CLOSE_TRANSFER记录核验，不使用名义pay_date冒充已知时间。

全联合域分别4528/3075回合、10699/6806个动作。1709固定池内，全lane登记股票1560/1566；149/143股从未登记，不能替它们生成普通净回合零标签。全部标签和资格缺失都保留状态，不做最终共同可比筛选。

## 标签成熟而非事后倒填

下表为不要求P/D/C已知的严格ordinary回合；右尾固定为净额大于3×3000，不因结果改阈值。

| cohort和历史cut | 已成熟ordinary | 大于3R |
|---|---:|---:|
| 2023，2023-12-31 | 1979 | 45 |
| 2023，2024-08-31及以后 | 2139 | 46 |
| 2024JanAug，2024-08-31 | 979 | 13 |
| 2024JanAug，2024-12-31 | 1061 | 25 |
| 2024JanAug，2025-12-31及2026-06-30 | 1080 | 32 |

进入原P/D/C研究域后，同2024模板在2024-09-02开盘前成熟支持为2736条、>3R 57条；到2024-12-02为3178条、>3R 84条。它们是按各cut严格已成熟、504共同日信号窗、模板分层的反事实cohort统计并集，不是连续账户或独立样本量。旧2022模板独立计数，不混入上述数字。详见EXTENDED汇总的五桶、年龄、尾部金额与UNKNOWN支持。

新增标签补充后来的2024研究支持，不能增加2022当时已知历史。artifact生成时间、假设历史完成proxy、历史source_available_at三者分开；后者无历史版本证据，仍为NON-PIT代理。没有把标签统一推迟至研究运行日，也没有宣称exit-day真实PIT。

## 依赖和选择偏差

四窗按(sid, signal_close, template_id)核对，精确决策重复0；存储身份仍含cohort_id和round_id。精确去重并不消除同股票、同root或责任区间重叠。

- 两新窗PRICE已入场共享903股、38个root；持仓或UNKNOWN责任区间重叠304对，其中双方均严格ordinary的重叠32对。PRICE口径见 `execution_v1/COHORT_COVERAGE_AND_DEPENDENCE.json`。
- 独审全AB+PRICE口径两新窗责任区间重叠1154对；2024JanAug与旧SepDec重叠964对、共享15个权益经济事件。全lane和PRICE口径不可混用。UNKNOWN保守保留至共同终点，已知claim责任保留至实际PAY。
- 四窗共享PRICE root组175、共享sid组1584。以后拆分或权重必须处理这些依赖，不能将独立FLAT账户的持仓、收益或claim相加。
- 原权益许可缺口更容易冻结持有较久、遇年度分红的路径。成熟ordinary偏向可闭合、无权益接触的路径；新增数量不保证右尾模型足够，更不代表策略改进。新2023普通标签中1573/2139为非正净额，新JanAug最终817/1080为非正；这里只是已成熟子集描述，不能推广成未成熟/UNKNOWN的期望。

## 实测资源和验收

两窗按顺序运行，无并发大现金进程。2023现金循环含原始账保存394.12秒，整个运行506.12秒，峰值6660.20MiB；2024JanAug分别295.49秒、361.46秒、7183.16MiB。两个退出码均0，最后SOURCE_VERIFIED和COMPLETE均存在。ECONOMIC_LOOP_COMPLETE中的source pending字段是落原账时的中间状态，不是末端验证失败。

- 2023独立保存账与标签核验：359071项，0失败。
- 2024JanAug独立核验：237668项，0失败；含16个全lane claims及10个PRICE非ordinary的实际PAY时钟。
- 最终独立完整重hash：24213输入、20代码/协议项、204旧文件均无变化；跨窗身份审查通过。
- 已验证dated费用、手数、初仓风险、ADD双正NET80、T+1、全现金与库存、权益归属/结算、PRICE book、冻结责任、strict ordinary与cut计数。
- 早期失败原样保留：fixture segment显示类型人工UNKNOWN已在同样本V2修正；旧测试75项中74通过、1项在旧run-once门前失败，未进入旧cash；旧index ns/us表示差异经精确无损标准化后对照通过；首次输入阶段会话中断原因未证实，不能称OOM。没有删除旧marker或偷偷重跑旧经济。

## 交付入口

- `execution_v1/economic_2023/`、`economic_2024JanAug/`：原始joint账、PRICE_LABELS、ALL_LANE_LABELS、PRICE_MATURITY_BY_CUT、SUMMARY、SOURCE_VERIFIED、COMPLETE。
- `execution_v1/post_audit/INDEPENDENT_POST_2023_FULL.json`、`INDEPENDENT_POST_2024JanAug_FULL.json`、`INDEPENDENT_CROSS_COHORT_REVIEW.json`：独立账本、标签与最终源闭环。
- `execution_v1/post_audit/INDEPENDENT_PRICE_DEPENDENCE_AND_RIGHTS.json`：独立复现PRICE重叠计数和10条实际PAY证据。
- `../distribution_objective_feasibility_v1/EXTENDED_FINAL_VERIFY.json`：逐cut稀疏as-of行、五桶、尾金额和平均盈亏重建通过；未新增经济或拟合。
- `execution_v1/COHORT_STOCK_COVERAGE.csv`、`COHORT_OVERLAPPING_PATHS.csv`：保存账上的固定池覆盖和PRICE依赖说明。
- `execution_v1/PROTOCOL.md`、`ROOT_EXTENSION_AUTHORIZATION.json`、`INDEPENDENT_EXTENSION_REVIEW.json`、两份FROZEN哈希map：执行前冻结证据。
- `../distribution_objective_feasibility_v1/EXTENDED_CURRENT_STATUS.md`及EXTENDED数表：最新支持与可建模边界，优先于补窗前“缺标签”的描述。

**结论仅为扩窗生成与审计完成。** 本轮没有训练新模型、改入场/ADD/退出、扩权益许可或证明原策略改善；对模型可行性应继续使用按cut、模板、缺失和相关性分层后的支持判断。
