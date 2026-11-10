# 2024-09-24信号资格接口与停止收据

全5,517股的6worker纯信号批次已按父线程即时指令停止。session57026退出130；6片各保留12条完整append-only结果，共72条唯一股票、无截断行。没有生成全量parquet或FULL_SIGNAL_RECEIPT，不把该最长历史优先处理的72股当完整母体。只读进程核验未发现本任务export进程或spawn worker；唯一残留resource_tracker的父进程为8天前长期server.py，非本任务，未停止。此后没有重启、参数优化或新增scope。

这次耗时是现有原纯函数实现的CPU代价，**不是数据/源码不足**。3股pilot的14,188个历史观察计算耗时11.65秒；截至2024-09-24的canonical源前缀为13,618,181行，线性6worker估计约31分钟，实际并发早期吞吐又投影约50分钟，因此按父线程停止，未继续长跑。

## 原stock E0/I实际可运行链

已亲读原No60`native-I-cache-interface/cache.py:16—34`，没有导入这个带原manifest/TradingAlarm入口的cache模块，也没有导入账户。新`stock_signal.py`只导入以下原纯函数，并严格以canonical截至共同日的OHLCV前缀计算：

1. [eligible_prices](</Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/data_utils.py:25>)保原价格有效观察；每股canonical单一source显式segment0，不补bar。
2. [event_frame_numeric](</Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/numeric.py:58>)固定joint=True、event_exit=False；[participation_frame](</Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-participation-response-20261020/code/participation.py:11>)仅供原ready/量比/effort/declined等市场事实。
3. 按[真实cache](</Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/native-I-cache-interface-20261031/cache.py:23>)组装e，显式decline_candidate=False、两个candidate价NaN；[e0_policy](</Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/policy.py:43>)构当前base，assert pending全无。没有把旧participation.target当当前E0。
4. 原[build_evidence](</Users/bytedance/Documents/ChatGPT/money/research_rounds/pv-strength-b5-20261025/code/evidence.py:160>)→SHA固定原B4 strength→[classify](</Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py:10>)→[project(G1_I)](</Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:6>)，没有用旧IX_target。

这些模块只有纯数学、源代码SHA读取和状态数组；没有账户、订单、现金、执行回放、联网或源文件写入。wrapper本身的输出是新canonical价格历史下的原公式结果，**未声称其与不同历史源/暖期的旧1709缓存数值一致，也未给独立经济/代码正确性PASS**。

G1_I的旧线优先：active时not shadow或C<=旧floor先退出，否则才ratchet当前base.floor。warm=G1 ready且grade>=2；opportunity=shadow且warm且(base.entered或fresh_up)，not active且not exited才进入；i_buy=active且opportunity。因而i_target持续True不等于新i_buy；负原E0 event本身也不等于当前E0_target已False。三股pilot已实际执行：

| 2024-09-24，canonical | e0_ready/target | i_target | i_buy | G1 | 原numeric leg |
|---|---|---|---|---:|---:|
| 000620.SZ | 1/1 | 1 | False | −3 | −1 |
| 000004.SZ | 1/1 | 1 | True | 4 | +1 |
| 002583.SZ | 1/1 | 1 | True | 4 | +1 |

000004是旧固定池之外的stock-only信号例；i_buy=True本身不证明满足100亿cap、THS行业、市场可买或S0资格。`PILOT.json`保留真实输入行数、时间及目标字段；无新资金数量或收益。

## S0与信号集必须分开

[原S0.eligibility](</Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/sector_stock_admission.py:185>)要求common_ready、buy_allowed、**company_cap_cny>10,000,000,000**、stock_up、issuer_known、sector_known和sector_up。unknown优先：有未知即q=None，不能因为另一项已False就把未知抹掉。不能撤cap门以制造池外完整资格。

[Facts.packet](</Users/bytedance/Documents/ChatGPT/money/research_rounds/actual-risk-recovery-20261027/code/engine.py:31>)对I模式以i_target替stock trend，再把buy_allowed AND exact当日i_buy；[原bridge](</Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/code/current_pool_bridge.py:323>)的common_ready还结合stock/sector各自ready，行业trend使用对应行业状态。No60 planning随后区分eventQ和把buy_allowed替成market_buyable的continuingQ；它们都不等于旧账有无仓位/pending/ACT。这里不借旧账户状态生成新资格。

本地5,517股与原固定1,709池交集为1,681，池外3,836；原metadata1,711键中本地覆盖1,683，和固定池不是同一口径。这里检查的local membership实际为SW 12,780条/5,862股/553类；taxonomy有90个THS行业名称和375概念名称，但名称表不等于股票成员关系。旧90行业source存在，不能直接借来给新全池股票声称同canonical、同源且完整S0。此处只报告该核查范围，不据旧metadata缺失推断所有本地股票THS映射或currentcap都不存在；完整THS/cap disposition由父线程另一条专门核查汇总。

保存的72条partial记录全部标`S0_eligibility_q=None/NOT_EVALUATED_STOCK_ONLY...`，不是已经算出的完整S0 unknown/False。exact目标日信号与`last_observed_*`诊断分开，缺目标日不把历史last signal倒填成当日i_buy。不存在此批次的“全池合格股票数量”。

全部源/代码SHA保留在`FULL_SIGNAL_RUN_STARTED.json`。`STOPPED.json`与`PROCESS_STOP_CHECK.json`绑定部分输出和取消结果。0账户、0订单、0收益/未来label、0下载/刷新，未改原算法或参数。后续限定计算范围等待父线程明确，不自动恢复此批次。
