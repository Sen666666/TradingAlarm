# SEC-EXIT-I：四个固定股票池，原IX与I退出对照

用户2026-10-26授权，已完成同入场配对＋8个各100万元有效账户。连续区间2021-01-04—2026-10-16，半导体126/通信43/创新药48/银行39股；原RS-H1/六槽/15%/90%不变。

I收益+205.89%/+492.84%/+25.55%/+8.28%；IX+2.14%/+306.24%/−13.00%/−10.50%。I四池收益更高，但半导体/创新药回撤更大，均未达20%回撤目标；尾部保留有得有失，不统一晋升。

[完整结论](CONCLUSION.md) · [协议](PROTOCOL.md) · [图表报告](http://127.0.0.1:8797/report/) · [股票池](scope.csv) · [有效账户汇总](analysis-v2/summary.csv) · [配对](pairs/summary.csv) · [核账](analysis-v2/accounting.json)。

有效路径`accounts-v2/`、`analysis-v2/`；`accounts/`为每行业2股误限导致的8无效实现路径，保留不用；[修复说明](IMPLEMENTATION_CORRECTION.md)。经济重跑一次仅修约定容量，不改策略。`analysis-v2.log`为导入重名失败，`audit-results.log`为有效分析。禁止覆盖重跑、按收益改名单或自动追加矩阵。
