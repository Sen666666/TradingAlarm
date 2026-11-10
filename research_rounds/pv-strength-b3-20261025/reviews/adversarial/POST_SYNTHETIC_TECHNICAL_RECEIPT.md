# B3 正式合成执行收据与统计更正

2026-10-25。冻结后使用 `PYTHONDONTWRITEBYTECODE=1 TradingAlarm/research/.venv/bin/python research_rounds/pv-strength-b3-20261025/code/checks.py` 执行一次。系统 Python 缺 numpy 的前一次导入失败另见 `FORMAL_LAUNCH_FAILURE.md`，没有模型运行或生成验证目录。

正式执行：239 项技术检查全部通过；24 条基础路径、32 个固定变换、4 个真实落盘再读取的前缀完成。原冻结与旧文件身份检查前后通过。所有路径及事件、去量字段、失败容器、技术/行为结果均独立保存在 `validation/`。没有真实资产执行、账户、参数修订或旧文件修改。

## 原行为汇总的统计缺陷

`checks.py` 的 `observed()` 使用 `passed is True/False` 分类；三个条件返回 `numpy.bool_`，因此虽然随后 JSON 清洗保存的 `passed` 正确为 `true`，此前的 `assessment` 被分类为 `descriptive`。原汇总为 supported=8、violated=0、descriptive=15。

逐项重读已保存 `passed` 字段后，正确统计为 **supported=11、violated=0、descriptive=12**。三个误标项为急跌 hot→freeze、micro_box 末63观察中性、constant 零当前推进。`BEHAVIOR_COUNT_SUPPLEMENT.json` 保存源哈希、原统计、正确统计与逐项差异。没有修改冻结代码、原结果或重跑模型；这是报告计数更正，不是市场机制修订。

“11项有限行为条件满足”不代表24条路径整体语义全通过，更不代表市场准确率或经济价值。12项纯描述仍需逐图审查。

## 已保存数字的初步读数

- 新阴跌路径第18次下降才 cold；前21次下降中有13次 hot、4次 warm、4次 cold。满足最迟21次合同，但不能称阴跌首日即识别。
- 上行后静止在第63次后全部 neutral。严重低量急跌当日 hot→freeze；不修复路径5观察后由下降接管，随后不再 hot，事件明确 `price_recovered=false`。
- 四根普通量 +0.03 的实际收复，在第4根记 `price_recovered`，当时 warm；没有把收复直接当成熟 hot。
- 同价−1.5σ中等冲击：普通量仍 hot，4倍量 freeze；取消量参与后仍 hot。此例证明量改变证据创建，不证明更多成交代表未来必跌。
- micro_rise 与 ordinary_rise 同温，63观察拟合幅度约0.063和6.3 log百分点，100倍关系保留；当前温度是相对上行证据类别。
- 旧 V 延续到第29个反弹观察才 hot；失败分支反弹后没有 hot。共同前缀完全相同，不能把后者记为提前识别失败。
- 旧 flat_box 全路径仍有11观察 freeze；one_pulse 有21观察 freeze，事件最终因离开当前尺度释放。两项仍需在24图中评估，不能用“无布尔行为失败”隐藏。

下一步只读查看全部24合成图与已存数值，另写输出审查；不改模型、不追加路径、不运行账户。
