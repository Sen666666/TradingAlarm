# 20股每日缓存：执行输出独立有界审查

PASS，当前范围无剩余阻碍；独审未调用任何stock_signal、numeric、CP/PVR模型、Account或Runner。已封静态审查及矩阵不修改。本审只读取20股原source、保存baseline/日表、旧输出和测试收据。

## 已独立重核的保存值

20股固定源前缀均止2026-05-15，20×1054源日期并集=21080格；不是官方日历，不是每股每格都有行情，也不是完整2026H1。保存baseline共5,129,470单元；其原内存→parquet roundtrip由producer断言。本审另将全部保存baseline按冻结日期并集reindex，与每日cache的1,665,320个原bundle值/NA逐行核同，并逐源核price字段、source-present、原有效OHLC mask、知识标签及PVRvalid/block。

- 同源旧三日：53个存在有效目标的原19字段精确核同；7个缺行保留缺失，没有以末次信号充当当日。
- 同源七PVR日期：126个存在源行的8字段精确核同，包含原warmup/NA；14个源缺行没有伪造值。不是126个都已有已知score。
- 已保存E0阶段交集：36个目标与旧stage的阶段、峰价、发生/确认日期及启动/突破日期核同。
- 本20股全源实际volume均finite正值，所有第65个eligible PRICE观察均已同时E0/G1ready，因此本试点暖机截点实际达到strength65；不能泛化到缺量输入。单段、坏价/坏量等更广输入域并未由此认证。

stock_signal_knowledge是E0+G1合并fresh readiness标签，不能拿它抹除原native19中可能独立已知的I持有状态。无source行/无效价格/未预热分别保留；无ffill。完整原I/CP保护层、持仓数量、资金、交易资格均不在cache，不能从市场CPcandidate推导实际层保护或下单许可。

## 物理前缀测试的两种证据

producer正式调用20次baseline，加40次两固定截点/股、5次真实分支、1次首次PVRknown，共66次完整原kernel/stock_signal调用；本独审0次。spy只捕获原numeric返回对象后立即恢复原函数，未改原19算式；原源码哈希与freeze一致。

40个常规截点和5个分支只保存JSON收据、没有重算prefix帧。本审核了源截点、行/列/单元数、branch机械首选、时钟以及绑定compare_frames源码与实际PASS收据；不声称独立重算或重新比较这些45次全部prefix值。执行代码实际比较的是所有共同前缀，不只是截点末行。

第6个补点301308在2022-12-09的第85个观察首次PVRknown，是固定20中2022以后最早的首次就绪事件。该重算帧确已保存，85×79=6715单元；本审全部值/NA与baseline同前缀逐bit核同，前84个score未知、第85个finite。没有重跑模型。

5个真实分支分别为I在非新E0入场时恢复、I退出、CP receipt、原down但I仍有效、G1未暖到暖。原G1命名cold_to_warm代码是前级别<2→当前>=2，通用含义应称未达暖→暖；本次真实000001例确为−3→2。旧floor退出+原up同日、坏量、坏额未找到真实20股fixture，明确NOT_EXERCISED。price-invalid/多source分支亦不据此宣称已覆盖。

CP first-bad额的防护按源码只在坏额前合法前缀调用原CP，坏点起全NA并永久BLOCKED，不drop/fill/resume，也不让future坏额抹掉过去可计算值。本20没有坏额，因此这个分支仍仅静态审查。原CP市场算法及I-derived输入语义另有cp_source_review来源说明，不能冒成历史daily CP独立缓存核同。

## 限制与闭环

SAVED_OUTPUT_AUDIT中的edge pending是当时快照，现由EDGE_AND_SAVED_PREFIX_AUDIT闭合，原audit不回写。20全日导出保存值、旧三日原状态、有限物理截点是三种不同核同；没有穷举每股1054天各自截断重算。

当前是固定复权版本batch once→lookup试点，不是增量恢复引擎。source/mask/起点/代码或历史复权因子修改应作废相关cache；数值因果性不证明历史publication/PIT、ST/停牌/限价/上市身份或可成交性。终端attrs/ledger不能回填旧行。没有账户、价格收益策略比较、参数择优或全5517运行。性能外推/部署与下一轮工程不在此PASS范围。
