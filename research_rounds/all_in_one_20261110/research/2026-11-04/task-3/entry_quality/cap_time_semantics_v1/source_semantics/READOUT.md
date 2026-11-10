# 当前市值读取的时间语义

已核源码与一个真实纯SelectionFact的read调用；未调用bundle/Account/Runner/模型/资格函数。状态PASS_BOUNDED；没有扩为所有封版账户的运行时身份认证。

核心：当前研究适配器**明确允许固定名单字段越过历史知识时钟**，并保留其真实快照日期。这不是普通Fact悄然忽略known_at；也不能据此称这些cap在2024已可观察。源码自己声明`current_pool_historical_development`，非PIT或未见样本。

- [current_fixed_pool.py:89](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/current_fixed_pool.py:89)：SelectionFact仅允许issuer/sector/cap，99–101的read直接`return self.value`，clock和for_execution均不改变结果。SelectionEvidence41–54是身份与aware时间校验，没有read方法；不是历史Fact。
- [build_security:147](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/current_fixed_pool.py:147)：issuer、sector、company_cap分别装入SelectionFact；common_ready/trend保持普通Fact，buy_allowed另把current selected_market与历史market_buyable三值相与。
- [Fact.read:49](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py:49)：known_at始终对decision_at；valid_from/to对decision或earliest_execution；snapshot还核observed_at。known_at晚于decision，即便for_execution=True也不放行。
- [Rank.read:76](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py:76)：known与observation不可晚于决策、观察日期必须等于session，结果round12；没有for_execution参数。
- [active S0:185](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_stock_admission.py:185)：cap用`.read(clock)`，非execution读；203行未知cap记None，否则严格>100亿元。issuer/sector与buy_allowed有execution读，stock/sector rank及共同ready等仍独立。219行任何unknown使q=None，已知false不会抹unknown。

字段链：current_pool_bridge.py416–421按manifest selection引用核文件SHA、从selection.observed_at构SelectionEvidence并载PoolLine常数；343–363为市场ready/trend构普通Fact。actual-risk engine.py35–45把Clock交给bundle，42调用同一build_security，并只另外改I trend/当日buy事件。该静态链已亲读；没有创建实际运行器来证明任意旧run确实绑定这些文件。

## 原数据与生成时钟

selection文件：[inputs-v2/selection.json](/Users/bytedance/Documents/ChatGPT/money/research_rounds/a-share-selection-e0-20261024/inputs-v2/selection.json)，snapshot id为`A-roster22-resolved-nonempty-industry-tree22-cap24`：roster_asof2026-10-22，cap_observed_date2026-10-24，observed_at2026-10-24T21:56:29+08，market_timestamp_unknown=True。其中000620的cap为16,617,237,000元；000016与002731的cap=None，仍作为unknown保留。

build_inputs.py23–33从原snapshot.raw_fields3541450取正数cap，其它情况转None；29–35按当前cap>100亿元或unknown保留。65–69以snapshot.updated_at作selection.observed_at。repair_classification.py32–49继承cap与时间，只修行业并保留construction.created_at。该生成时间是2026-10-24T22:50:11.376302+08；不是cap在历史生效时间。所核selection与000620原快照行均无`createdAt`字段，不能补造同名时间。

原000620数据packet202的receipt.received_at=2026-10-24T21:55:54+08，snapshot.raw_fields3541450同值；market_timestamp=None、historical_point_in_time=False。snapshot_batch.py151把receipt.received_at写入各symbol observations.observed_at；128的updated_at则是本地export时刻。2026-10-22 as_of标签有`label_is_not_observed_timestamp=True`，不能代替真实收到时间，更不能回填2024。

## 单字段实际调用

同一个SelectionFact，evidence仍为2026-10-24观察时刻，没有回拨：

|决策clock（+08）|SelectionFact.read / for_execution|同值同时间普通snapshot Fact.read / for_execution|
|---|---:|---:|
|2024-09-24 15:10|16,617,237,000 / 同值|None / None|
|2026-01-15 15:10|16,617,237,000 / 同值|None / None|
|2026-10-26 15:10|16,617,237,000 / 同值|16,617,237,000 / 同值|

只执行两个原纯字段模块、一份SelectionFact及对照Fact。完整原文行号/SHA在SOURCE_EXCERPTS.json；实际调用与原data绑定在ONE_FIELD_READ_EVIDENCE.json。首版验证脚本有一个else空格语法错误，在任何import/调用前停止，修正后运行一次；未执行失败的账户或模型。

这证明的是显式研究快照覆盖的代码语义与所引用输入值。它既不提供历史cap，也不证明历史publication/PIT，更不因本轮展示快照门就新增诊断为原普通Fact的意外穿钟。所有旧run的具体source binding由单独运行时lineage审查负责；本收据没有全账认证。
