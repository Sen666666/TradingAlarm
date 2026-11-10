# PVS-B3：趋势状态与交易策略分层

用户授权继续优化量价趋势强度，同七资产画图，E0保留、账户0。

入口：[研究范围](SCOPE.md)、[唯一候选协议](PROTOCOL.md)、[原量价22窗审阅](reviews/raw/RAW_REVIEW.md)、[机制讨论](reviews/mechanism/SECOND_ROUND.md)、[语义审查](reviews/semantics/REVIEW.md)、[反方合同](reviews/adversarial/ADVERSARIAL_REVIEW.md)。

本轮把温度定义为月/季尺度与急性破坏共同形成的上行证据状态；五档有序，不冒充等距速度、概率或收益。交易开仓/卖出/仓位完全独立，当前未实现。旧E0/R/R1/B1/B2和旧结果不覆盖。

**本轮完成，不晋升。** [交互报告](http://127.0.0.1:8787/report/)、[完整结论](CONCLUSION.md)、[黄金概览图](figures/gold-summary.png)。2025黄金整理更稳定、2026-01-30急跌当天hot→freeze；但3月未收复到期后warm、4—6月37观察阴跌neutral，德明利负向行情却cold→warm，说明当前强度仍不合格。不能用少跳档/少hot当正确。

239正式技术检查、7资产17,605行独立复算、14真实物理前缀通过；400旧文件、E0/R/R1登记30文件不变。原22真实图和24合成图全部独立实看；另1张黄金概览。全部是已见开发历史，账户0。完整状态见[RUN_STATE.md](RUN_STATE.md)、[交付收据](complete.json)。

真实/合成逐日输出在results/与validation/；公式/输入/冻结证据在freeze.json，表格与交互数据在analysis/；五角色review全部保留。初始系统Python缺numpy未进入模型、行为计数类型错误及更正另存，不覆盖原件。真实结果后模型/参数修订0。

复现仅在新副本/新输出目录，勿覆盖本轮：code/study.py freeze → code/checks.py → code/plot.py synthetic → code/study.py real → code/plot.py real → code/analyze.py → code/report.py。报告另有输出后的结论注释、窄屏排版修正和独立复评补充，均不改变模型；最终HTML哈希见complete.json。项目Python为TradingAlarm/research/.venv/bin/python，禁止启动旧账户脚本。没有待自动执行的模型、账户、下载、RS或换仓队列。
