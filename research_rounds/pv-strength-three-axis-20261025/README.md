# PVS-B2：推进、结构保留和反向冲击

用户对B1黄金两窗的指正已完成归因与新一轮原型研究。[交互报告](http://127.0.0.1:8786/report/)，本地静态文件 [report/index.html](report/index.html)。

本文P/R/D是B2内部维度符号，R_ret为保留比例，不是已冻结R敏感退出政策；E0/R/R1名称原义不变。

**裁决：三轴描述有增量，尚未解决统一判强。** 黄金整理可以同时显示弱推进/结构保留，部分下降反弹可同时显示正局部推进/下降结构，急跌冲击当天显露。但窄箱体仍频繁切小结构，真V和转弱的R确认慢，反弹可有新R=1，旧D可能长期陈旧。不能把任一轴或任意加权当成熟强度/买入门槛。E0、B1保留，账户0。

阅读顺序：[完整结论](CONCLUSION.md) → [冻结协议](PROTOCOL.md) → [唯一数值修复](NUMERICAL_V1.md) → [有效冻结](freeze-v1.json) → [22真实图独立复评](reviews/output/OUTPUT_REVIEW.md) → [17合成复评](reviews/adversarial/SYNTHETIC_OUTPUT_REVIEW.md)。

- 同7本地资产：AU0、518880、512480、德明利、中芯国际、招商银行、贵州茅台；旧20固定真实窗＋2用户精确主窗，17有限合成。
- 五位空白agent、设计/协议讨论/实现/原图与输出多轮审查。完整源历史预热，主2021起，全部已见开发材料。
- P实际5/21观察速度；R固定起点的结构成果保留与支持；D即时价格冲击＋有量资格位移的实际收复账本。不合成总分、不发买卖指令。
- 88技术检查、14真实物理前缀、独立7×49字段复算、17单位变换完成。旧B1144文件及原登记30文件不变。
- v0浮点包容等号失败保留在code/freeze.json/validation；有效为code-v1/freeze-v1.json/validation-v1。数值修复1，真实结果后机制/参数修订0。

`results/`保存7逐日CSV/Parquet及事件日志；`figures/real/`22图、`figures/synthetic/`17图；`analysis/`为输出后事实，不反馈模型。`reviews/rootcause/`B1精确归因、`reviews/mechanism/`两轮建议、`reviews/adversarial/`合同及合成输出、`reviews/output/`先原图后22图复评、`reviews/implementation/`独立数值与版本收据。

复算必须用独立结果副本，代码默认拒绝覆盖。有效链为code-v1/study.py freeze → code-v1/checks.py → code-v1/study.py real，随后只读code/plot.py、analyze.py、report.py。原v0身份仍独立保留，不把v1通过改写成v0通过。详见[完成状态](RUN_STATE.md)及[收据](complete.json)。

本轮账户/下载/RS/换仓/E0改动均0；不自动启动下一模型、过滤器、参数矩阵、合成总分或账户。
