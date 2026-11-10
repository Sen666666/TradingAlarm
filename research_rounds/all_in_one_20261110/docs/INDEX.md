# 成果导航

## 先读结论

- [原主工程最新交接](../project/docs/handoff_2026-11-10/README.md)：研究目标、交易哲学、失败与重大行情。它是历史快照；最新终态以本项目 CURRENT_STATUS 为准。
- [已核实结果](../project/docs/handoff_2026-11-10/VERIFIED_RESULTS.md)
- [51分类与M1—M12公式](../project/docs/handoff_2026-11-10/FORMULAS_AND_SCOPE.md)
- [全部早期算法文档](../project/docs/)

## 按阶段

| 阶段 | 目录 | 内容 |
|---|---|---|
| 早期主工程 | [project/research_rounds](../project/research_rounds/) | E0/R/R1、量价、板块选股、CP与费用核账；失败版本保留 |
| 10/29 | [task](../research/2026-10-29/task/) | 全池CP1事实、原始及衍生数据、后续研究 |
| 11/01 | [task](../research/2026-11-01/task/) | 账户、权益、状态研究 |
| 11/04 | [四条任务](../research/2026-11-04/) | 账户/市场、轻量流程、entry_quality、原生算法 |
| 11/06 | [entry_state_selection_v1](../research/2026-11-06/entry_state_selection_v1/) | 入场、广度、量价、执行与资本；同日CP/H1目录并列保留 |
| 11/09—11/10 | [sector51_924_entry_review_v1](../research/2026-11-09/sector51_924_entry_review_v1/READOUT.md) | 51分类与M1—M12主线研究 |

## 当前主线

- [M12赢家供资设计](../research/2026-11-09/sector51_924_entry_review_v1/mainline_winner_funding_design_v1/DESIGN.md)
- [M12 v2原始终态](../research/2026-11-09/sector51_924_entry_review_v1/mainline_candidate_v12_winner_funding_cash_688200_v2/RUN_STATUS.json)
- [M12冻结输入](../research/2026-11-09/sector51_924_entry_review_v1/mainline_candidate_v12_winner_funding_cash_688200_v2/FROZEN_INPUTS.json)
- [最后认证检查点](../research/2026-11-09/sector51_924_entry_review_v1/mainline_candidate_v12_winner_funding_cash_688200_v2/runtime_checkpoint/LATEST.json)
- [前缀差异说明](../project/docs/handoff_2026-11-10/PREFIX_DIAGNOSTIC_UPDATE.md)

跨文件检索可在本目录使用编辑器全文搜索，或 `rg '关键词' research project/docs -g '*.md'`。原报告里的绝对路径请用 `python3 tools/research.py resolve '旧路径'` 转换。原有localhost链接不是本归档自动启动的服务。
