**本轮已完成：9路径全部核账通过，经济一次、重跑0、结果后规则修订0。** [完整结论](CONCLUSION.md)、[全9路径表](RESULTS.md)、[资金与收益曲线](curves.png)。E0/I/IX基础净利润13.73/10.50/3.29亿元，最高市值19.17/18.18/16.83亿元；按该最高市值归一化71.65%/57.76%/19.57%。下方“正在运行”为历史阶段记录，已由本结项覆盖。

# 无限总资金、单股100万元上限

用户2026-10-26明确授权的资金与容量诊断，原趋势算法不改。当前状态见RUN_STATE.json，运行日志economic-v1.log。不得重新启动已存在accounts-v1的进程或覆盖失败结果。

- [固定协议](PROTOCOL.md)
- [短期独立核账](technical/short-v2-analysis/accounting.json)
- [峰值资金独立重建](technical/short-funding-validation.json)
- [结果前技术失败](TECHNICAL_FAILURES.md)
- 完整经济回放正在运行；结果预计保存RESULTS.md、analysis-v1和curves.png。

去掉全账户资金/股数/行业名额限制，保留原S0行业准入。各股每个持有周期最多100万元成交本金，费用另计、上涨不压回100万元。E0/I/IX各三执行情景，共9条路径。最高持仓市值与峰值固定资金需求分列，记账现金垫不进入收益或回撤分母。
