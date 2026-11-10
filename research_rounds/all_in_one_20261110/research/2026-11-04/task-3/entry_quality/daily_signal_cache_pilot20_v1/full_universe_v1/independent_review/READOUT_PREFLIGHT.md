# 全本地cache：启动与渐进独审状态

修后runner静态有界PASS，无已识别剩余fatal；这不是全5517输出审结。当前cache identity `b0af9a5b8a8f6d1f8da1b56577cee3270c7ef2a20e2bd48edd435d9b38904704`，driver SHA `3549802c9da41dbd62f5b854ef1d0d1c97890234253fd26523d93e0fc879b4a2`。此前PRE_REVIEW_STATUS的源码未见是历史快照，已由本RUNNER_SOURCE_GATE闭合，原记录不回写。

独立发现并修复的实际阻断：原20有11份Arrow schema与sample不同，不能同时声称“字节复制”和“统一严格schema”。新副本显式cast，原20不变；本审20×1054×91=1,918,280个语义值/NA独立核同。它们是归一化副本，非字节相同副本。

实际源码已确认receipt-last、fsync/atomic rename、exclusive标记、错误/未知隔离与只读orphan恢复。补候选fsync和committed输出计数名称已落实。CP首bad仅前合法段计算，之后typed-null BLOCKED；I_hold/fresh知识分开，原19不改。worker信号hook的当前任务收口与生产恢复仍需按记录范围解释，未声称真实强杀等全故障测试。

隔离/tmp复制20fixture、只执行AST提取的真实文件helper，6类文件状态通过：归一化20、合法DONE+旧marker、完整pending无receipt恢复、损坏DONE、不重试明确ERROR、截断pending保UNKNOWN。没有导入/调用kernel或任何模型、没有改生产artifact/running/pending。真实进程死亡、signal、断电、ENOSPC和并发writer未测试。

截至保存快照，独立审977个有效DONE文件，旧三日期2724exact/207missing、七PVR日期6421present/418missing核同。只按atomic completed receipt读文件，未读生产pending或把孤立artifact算入覆盖。这是子集，余下待生成后继续；不能用本快照宣称全5517完成。

渐进检查state按sid、receipt SHA、artifact SHA/stat持久化，重复调用只读新增，final重核所有SHA。audit_committed.py --final还会强核5517、15278exact+1273missing、全部三个ready/hold/buy分母、20复用、15739264输入行与最终sourceSHA。该模式尚未运行。

本审新增模型/账户均0。最终GENERATION_COMPLETE、原3日全字段、全源最终身份和全池审计索引仍PENDING；不认证PIT/上市/ST/停牌/限价/真实可成交或alpha。
