# 多尺度推进与资源交接诊断（2026-10-25）

[完整结论](CONCLUSION.md) · [本地图表](http://127.0.0.1:8792/report/) · [公式/范围](PROTOCOL.md) · [后续恢复凭据设计](RECOVERY_EVIDENCE_DESIGN.md)。

已新增B5-M1描述原型：5/21日短推进、63/126日长推进、原始日基点、短长方向组合，与原量价结构/冲击/升温收据并列。它没有改E0、G1、IX或任何账户，没有晋升新温度。

全A原IX事件481305个完整逐字段保留；合格1709股票中1679只产生原IX事件，另外30只事件数0单列。七原标的与三赢家32图，真实前缀30。自然交接有效结果为 `handoff-v1/`，不要使用旧 `handoff/` 的全未知最小单位判断。

有效模型冻结 `freeze-v2.json`；资源解析修正 `handoff-freeze-v1.json`；图检后全池门控归因 `POST_REVIEW_SCOPE.md` / `gate-audit-freeze.json`。所有历史均为已见开发样本。新增账户0，实盘0，下载0。

复现须复制到新的独立结果目录再按新目录冻结，不直接重跑旧输出路径。顺序：模型技术检查→freeze→run_m1→handoff_v1→plot_m1_v1→gate_audit→validate_m1。`run_m1.py`的原样重跑会拒绝已有analysis目录；所有结果和失败版本都保留。旧E0/R/R1登记30文件、原48账户1898文件和上轮归因62文件核验不变。

有效结果：`analysis/`、`handoff-v1/`、`gate-audit/`、`report/`、`validation.json`。`analysis-attempt0/1`、`technical`各版、`handoff/superseded.json`与`validation-attempt0.json`保留数值/序列类型/日期解析/核验区间的技术失败。没有经济账户重跑或按收益调公式。
