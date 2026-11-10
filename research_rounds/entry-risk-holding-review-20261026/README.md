# 入场风险与趋势持有：2026-10-26深入复查

- [完整结论](CONCLUSION.md)：近支持不是统一好买点，连亏硬暂停会覆盖大量旧尾部；优先研究首次金额风险合同。
- [唯一设计候选I-RB1](CANDIDATE_I_RB1.md)：保留原I信号/排序/E0退出，首次名义风险预算1%；尚未实现或回测。
- [事前诊断协议](PROTOCOL.md)、[先看原始量价记录](RAW_REVIEW.md)。
- 有效数据：prepared-v2/funded.csv（3646真实周期）、prepared-v2/opportunities.parquet（11670资格事件）、results-v1/first-e0-opportunities.parquet（4895来源安全E0段）。
- 分组结果：results-v1/funded-groups.csv、results-v1/opportunity-groups.csv、results-v1/decision-overlap.csv。
- [独立核验](verification-v1/receipt.json)：506文件、3646风险/时钟、3646反馈、16真实特征文件前缀；[原账户净损益恒等](results-v1/verification.json)。
- 图：charts-raw与charts-overlay各8张。选择不按后续收益；已见开发历史，不是样本外。
- 失败保留：technical-attempt0.json/code-v0/prepared；technical-attempt1.json/code-v1/prepared-v1；系统Python无pandas后复用既有venv，未安装新依赖。

复现只能复制本轮到新目录并修改输出身份，或将所有输出指向新路径重新冻结；不要覆盖当前freeze/prepared/results/verification。原诊断入口依次prepare→raw（人工阅读并记录）→summarize→overlay→verify。prepare/summarize/raw/overlay和verify的输出均拒绝覆盖。本轮经济账户0、下载0、生产算法改动0。
