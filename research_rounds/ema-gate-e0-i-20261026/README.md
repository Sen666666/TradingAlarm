# EMA前置过滤对E0/I的有限研究

本轮已完成，**不晋升为通用硬过滤**。只加EMA9>21>50且三线向上，新买受限、原持有/退出不变。I四池收益均下降；E0只有半导体同时改善收益和回撤，所有账户回撤仍超过20%。

- [完整结论](CONCLUSION.md)、[冻结协议](PROTOCOL.md)、[经济前图检](GRAPH_REVIEW.md)。
- [图表报告](review/index.html)、[全部资金结果](analysis/summary.csv)、[逐笔周期](analysis/campaigns.csv)。
- [旧I筛查归因](diagnosis/old-I-filter-attribution.csv)：仅固定旧金额/旧路径，不能当新账户收益。
- [资金核账](analysis/accounting.json)、[四I完整恒等](I-controls.json)、[真实截断](technical/prefix-identity.json)。
- [视频思路日线适配草案](DAILY_ADAPTATION_FOR_REVIEW.md)：另一支线，仅设计、待审，未运行视频资金账户。

24路径=四池E0/E0G/I/IG基础16＋过滤E0G/IG双成本8；其中四I为旧控制，20新增经济。2021-01-04—2026-10-16各100万元，原15%初仓、90%新增、六槽、行业准入、RS-H1及执行约束不变。当前存续/分类/市值快照与已看开发历史偏差保留。

有效输出`facts/`、`charts/`、`technical/short/`、`technical/short-audit-v2/`、`accounts/`、`analysis/`、`technical/prefix/`和`review/`。首版短核账仅未含退出检查，旧代码和结果仍在`technical/audit-gate-v1.py`与`technical/short-audit/`；经济前v2补齐100退出检查，短账户无需重跑。无经济失败或寻参。

代码在`code/`，前缀包装与经济后描述在`audit/`。输出排他创建，不得原地重跑覆盖；复现用新目录，旧模型/行情/金融结果只读保留。最终完整性与全部输出SHA见`complete.json`。本轮结束，不自动改成更松EMA门槛、不按股票池择优采用、不启动下一账户队列。
