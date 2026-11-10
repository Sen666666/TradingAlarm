# 方向成交金额研究：DAP1 / DAP2 / DAP3

已完成，三版均未达到目标，不替换E0-NR1/I-NR1。

- [完整公式](ALGORITHM.md)
- [完整结论和30路径结果](CONCLUSION.md)
- [交互全池量价/温度/实际成交图](http://127.0.0.1:8803/report/)
- [初始协议](DESIGN.md)、[事前修订](REVISION_PLAN.md)、[保留失败](FAILURES.md)
- 数值：all-summary.csv、periods.csv、h2-attribution.csv、winner-participation.csv。
- 核验：signal-prefix.json、account-verification.json、complete.json。

407股，2024-01-02—2026-10-26；当前快照开发研究，日线执行代理。每条路径是同一100万元资金池的替代模拟，不是同时持有30个账户。H结构持有；C冷退出。内部R1/2/3目录对应DAP1/2/3，不是此前冻结R1。
