# RC1 渐进恢复原型（独立保留，不晋升）

2026-10-25用户授权实施并图检，旧算法/结果不改，账户0。RC1不是既有R1。

完整事前规则：[PROTOCOL.md](../research_rounds/gradual-recovery-rc1-20261025/PROTOCOL.md)；结果与反例：[CONCLUSION.md](../research_rounds/gradual-recovery-rc1-20261025/CONCLUSION.md)。

事实接口`evidence_rc1.recover(evidence, pace, original_grade, joint=True)`：从初始化/负向风险/新局部低点建立观察段，冻结s0/V0；新前沿dF按量权clip(sqrt(V/V0),.5,2)累计Q。净位移和信用均达sqrt(5)*s0/sqrt(21)*s0时产生局部/较大尺度收据，必须有当日新前沿、消费增量检查点。输出anchor/date、s0/v0、delta5/21、x/frontier/credit、当日增量、receipt5/21、背景与前高以下标志。不读取账户；前高不是门槛。

等级消费者`grade_rc1.classify_with_recovery`保持原G1候选/降温，新增凭据按下降背景修复上限、混合背景暖上限、上行背景局部暖/较大尺度热上限消费；原通道保持，故并非统一新的全局温度。关闭新增规则后10源逐字段复现原G1。IX-RC1是原IX函数消费新等级的资格投影，不是资金账户。

10源32原图窗＋4详图，旧资格保留。2023+新增31资格事件、30在前高以下；189个旧慢推进冷态日恢复25个。沪金2026-04-08/06-15原通道仍在down背景升暖，寒武纪/茅台新增恢复有后续破锚，故不称已经解决跌势反弹。下一有限问题是快启/恢复/长背景的统一状态语义，不自动加过滤、改仓位或启账户。
