# 全5517日序cache：实现前故障核对单

当前状态PENDING_RUNNER_SOURCE：本轮两个文件清单检查时，新runner尚未落盘；以下是基于已封pilot.py实际源码的待核条件，不是新runner通过或运行授权。独审零模型/账户。

- 模型调用前exclusive创建RUNNING/job身份，防双runner重复同股。DONE receipt只有在其两parquet、SHA/schema/grid、source/code/roster和旧三日19校验完整后才可skip；合法DONE与旧RUNNING并存按有效commit收口，不重新算。
- 每个parquet同盘临时名写完、关闭校验后atomic rename；receipt用temp+rename最后提交。中断在数据rename后但receipt前时，这是ORPHAN/UNKNOWN_OUTCOME，不是从未开始。不得静默删文件重算；只读恢复验证能证明完整时另立reconcile记录，否则隔离保留。
- FAILED/正在运行/结果不明不自动重跑；从未被领取的PENDING仍可执行。原始信号未知/未预热不等于执行失败，必须与UNKNOWN_OUTCOME命名空间分开，否则会把大量合法NA任务误当可重试/坏任务。
- 原20复用须核sealed source+完整组件代码、source起点/截止/mask、grid/schema和原文件SHA；引用或copy至新域并绑定provenance，不改旧文件或旧receipt。新增I_hold/fresh知识列若要对齐只能在新域派生并记版本，不能回写原20。
- 真实CP接口只含市场receipt/candidate，e0_valid为原I_target，旧floor为I_floor。不得改接stage或G1fresh，也不能把CPcandidate叫实际持仓保护P。
- 实际pilot.py124–129：若CP首个native价格行即坏amount，stop=0时q只有input_status，其余24个CP列根本不存在。全池不能假定每股79组件列。可在新wrapper统一typed NA schema并明确未计算/BLOCKED，或允许明确的component schema；不得补False/0或自动重置恢复。firstbad以后所有CP值均未知，过去合法前缀保留，不能由未来坏额删除旧值。
- 原I_hold的知识只要求exact有效价格和e0_ready；fresh/i_buy研究解释另需g_ready。combined fresh readiness不能覆盖仍有效I持有，原19本体保留原值。ST/停牌/限价/历史上市、真实available_at和执行合法性均不因此获得认证。
- 单段原stock_signal入口不支持把真正source切换拼成segment0。无有效价格、全坏量、过短warmup、CP首bad、schema不齐的任务要有明确无数据/unknown/error记录，不应令全5517完成计数偷减。
- source/code/input一旦变动，先停止其新commit并保留已生成版本；resume不得混source版本。receipt不能只核存在、mtime或最后sid，需内容hash和本股/日范围唯一性。
- 最终5517完成必须逐sid唯一覆盖roster；DONE/ERROR/UNKNOWN/未开始分开，只有全部预定DONE有效才称完整生成。每日表roundtrip、旧三日期19、有限prefix矩阵分别统计，不外推为5517×1054每日穷尽重算。

待runner可读再按实际分支审核；当前不对未见源码下PASS。旧pilot和本地20数据审计均维持原seal不变。
