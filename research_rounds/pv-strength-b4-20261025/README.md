# PVS-B4 方向—推进—新量价确认

独立研究，保留E0/B1/B2/B3，账户0；同7标的22真实窗，24合成＋1固定派生，冻结候选1/参数1/正式输出后机制修订0。

- [交互报告](http://127.0.0.1:8788/report/)
- [结论及反例](CONCLUSION.md)
- [冻结公式](PROTOCOL.md) / [范围](SCOPE.md) / [核心身份](freeze.json)
- 真实逐日表 results/；确认完整收据 results/*-events.json；固定图 figures/real/。
- 窗口统计 analysis/window-statistics.csv；旧结构与当前推进冲突 analysis/structure-pace-conflicts.json。
- 独立技术审查 reviews/audit/POST_RESULTS_AUDIT.md；行为反方 reviews/adversarial/OUTPUT_REVIEW.md；真实图检 reviews/output/。

复现使用项目Python TradingAlarm/research/.venv/bin/python，设置PYTHONDONTWRITEBYTECODE=1。请先复制本轮代码到新的结果目录再重跑；study.py/checks.py主动拒绝覆盖已有核心产物。顺序为冻结→固定合成检查→真实输出→analyze→plot→report→独立审查。绘图MPLCONFIGDIR=/private/tmp/pvs-b4-mpl。报告服务仅127.0.0.1，端口8788。

方向/大小是EW净log收益的正负/绝对值，事件结构不是当前速度，急跌标记消失不是修复。绝不将结构同上直接命名hot。研究来源口径和已见历史偏差沿用旧输入，AU0主连换月口径并未彻底核实。
