# 原stock函数与因果前缀：有限放行

原实现/所测因果性无阻断。只对固定盈新000620、海能达002583、银之杰300085，各算截至2024-09-24和追加5个真实后续观察截至2024-10-08两份独立物理输入，共6次原calculate，墙钟9.60秒。正式目标只使用前者，后者文件名明确FUTURE_APPEND_TEST_ONLY。

全部共同prefix原信号19列、有限数值bit及原numeric事件全表（含confirmed_pivot_date）精确一致。源事件返回只作只读观察，未另算事件、未修改原公式；没有发现未来事件回填。confirmed_pivot_date是发生日，event行才是确认已知日，不能把确认回填到历史极值日。

原cache.py16–35是现行E0(decline_candidate=False)→G1_I，非直接复制IX_target。其原事件/participation与本wrapper调用flags同；原G1 grade由prepare_ix→B5 evidence→classify。源码/行号及SHA在SOURCE_AND_READY_EXCERPTS.json，当前wrapper与原11算法代码冻结SHA均一致。

E0 ready与G1 ready不同：前者从numeric leg已知后延续；后者取决于当下强度观察和mu21就绪。最终研究hold仅exact+e0_ready时报告I_target Bool；研究fresh还须g_ready，否则NA。原始i_target/i_buy/grade不改。i_buy不等首次成交或独立新结构，继续MOBILE另有原资格和CP路径。

这里只是三股一时点的有限因果审查，不是全5517未知/换源/所有边界证明。canonical qfq vintage和历史publication/receive仍非PIT认证；无账户/收益/订单资格结论。全池正式结果及排名尚未产出供本审计检查，未借本gate冒全池PASS；待其完成后另存输出收据。
