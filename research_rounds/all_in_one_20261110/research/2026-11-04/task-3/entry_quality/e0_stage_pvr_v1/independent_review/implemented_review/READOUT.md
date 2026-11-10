# E0阶段PVR：实现及保存输出有界独审

PASS，当前范围无剩余阻碍；不是经济有效性或账户通过。源码/合同旧seal不变。OUTPUT_AUDIT创建时写的“numeric prefix另待审”现由NUMERIC_PREFIX_AUDIT闭合，未回写原audit。

research.py的replay/rank与最终diagnose.py已亲读：按全eligible价格CLOSE先检查旧E0 floor，不用numeric.active代替；只−event记确认峰，+event用此前已确认峰冻结H；同CLOSE可以越H，BREAKOUT锁存至新down或floor失效。峰发生日与确认行分开，保留更早源峰，不从未来较高/较低峰回填。仅改变研究排序，原I/CP/资金/退出均不运行。阶段/新排名先落盘SHA，独立diagnose命令随后才读旧标签；已修正案例成员判断为真实cohort key set。

3287保存请求（3269原i_buy股日+18预定非成员）全keys/parts/snapshot核同：3283精确行的E0 ready/target/floor/entered/exited、numeric event/leg/close共8字段与既存源结果核同；4无目标行保留未知。三日完整cohort及prior原字段不变：

|日|总N/已知PVR|BREAKOUT/START/RETRACED|top20保留/替换|top100保留/替换|
|---|---:|---|---|---|
|2022-01-24|177/175|90/86/1|17/3|89/11|
|2024-09-24|2313/2313|757/1554/2|19/1|85/15|
|2026-01-15|779/779|496/282/1|20/0|95/5|

2022两条未知PVR仍在母体和阶段分母，但无新rank；BREAKOUT90中89可排、START86中85可排。每个新旧topK保持相同数量；阶段内原PVR降序及sid升序和总优先级公式全核。所有top20均BREAKOUT；2022 top100为89BREAKOUT+11START，另两日top100全BREAKOUT。完整母体保留不等于START机会没有被有限名额排除。

保存诊断108行全部统计、396条后验尾部membership、全部topK替换key、33预定案例及其真实成员/原raw注释核同。现有各股5/20观察路径只原样join，不另算价格或改标签。组均使用1e−12算术容差；原评分/状态字段用精确比较。全阶段不会另加收益、交易费用、OPEN成交或账户因果含义。

四个固定股000620/300666/300085/002583额外只调用原numeric事件核：2024-09-24物理截断与延长到10/08两次输入，全部原事件输出列在共同前缀exact，保存峰谷/provenance与原numeric核同。合计8次numeric-only调用，未调用stock_signal、原E0/G1/I policy、research.replay或任何Account。此是四股因果测试，不是所有缺失量/无效/source分支普遍证明，更不是历史行情实际available_at证明。

已薄读根READOUT主结果及失败陈述，无关键数值/归因异议：盈新2022仍BREAKOUT，canonical C3.98/H3.78（峰1/14发生、1/17确认），原6→新6、后20观察−26.38%；不能混旧prepared的不同价格尺度。2026 top20全不变；2022 top100后20均值−2.10%→−2.91%，924/2026 top100后20最高5%覆盖11→10、7→6。支持“本固定候选不晋升”的有界选择，不能外推所有E0阶段信息无价值或账户必差。

旧CP风险集、legal/S0/H1/行业/持仓/现金/数量/真实成交不在本任务；三日已消费且相关，静态本地池与当前qfq版本非PIT。原事件确认index是观察日而非真实接收时刻。根报告的性能成本章节仅绑定来源，未由本实现审另做全源基准测量或认证其外推估计。原全信号模型/账户新调用0，停止扩展。

技术留档：首版独审对跨三日concat后bool→object列使用dtype严格断言而停；同值不变，改审计为check_dtype=False且check_exact=True，旧脚本副本保留。未改研究代码、分母、公式或数据。
