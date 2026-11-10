# M12 后审准备结果

- 已仅从原 M7 保存输出独立复算通过：93 个交易日、3,596 笔真实模拟订单、1,677 个固定轮身份，终值 NAV 1,275,326.0427500672225。
- 59 个输出文件与 9,081 个来源文件的 hash 均通过。未 import 候选策略或 Data，未执行历史。
- 旧 V11 v2 仅提取纯账务/cohort 函数。原文件完全未改，G/F∨CP entry 判断与全部 V11 结果均未引入。
- 审计器自身 16 组检查通过，包含独立 capped-water/reference 算术及篡改 D/X 拒绝。不是候选策略合成 PASS。
- 已固定原启动窗口 71 轮 MATURE 健康供资同日交集，原净利 36,641.986218763929；明确不是定向供资或候选因果归因。
- 主账户经济检验固定为 11/6 后实际 PnL，另列全期 NAV、fees、exposure、max-close drawdown、固定 222/19、PV34、晚期954 和实际未平轮。
- 候选 JSON 接口已适配完整分支簿、共同 OPEN 条件 prefix/H、q/y、WAIT、preflight、actual/no_fill 诊断。独立接口审查已按 engine 2e37d2a20e33760ffdb1b1b9ba84f8edce7492a3162880ba800759d8773cdd72 通过，后审继续与其分层绑定。
- 人工保存 fixture 的 16 组独立接口核验通过：full ADD=200、shadow ADD=300，选 shadow、真实 ADD=300、新 SEED WAIT。只读 JSON，未调用候选。

## 当前缺口
候选实现已静止，父线程已启动唯一真实实验；尚未明确通知完成或阻断，本审计器未读取实际运行输出。因此本目录没有 M12 账户或策略语义通过结论。
须收到父线程明确“实验完成”后再审输出。保存 q/y/H 本身不能证明无未来读取，最终报告将与静态源码/poison 测试分别列证。

## 文件
- audit_saved_outputs.py：账户、源封存与固定身份入口。
- accounting_core.py：经 provenance 记录的纯复算函数。
- verify_saved_funding_semantics.py：独立 saved 分支语义。
- analyze_actual_paths.py：真实资金、534 账户现金事项复核、分段与机会成本。
- write_readout.py：结果存在后生成主报告。
- AUDIT_CONTRACT.md、CORE_PROVENANCE.json、PREPARATION_BASELINE_CHECK.json、AUDITOR_SELF_CHECK.json：边界和准备证据。
