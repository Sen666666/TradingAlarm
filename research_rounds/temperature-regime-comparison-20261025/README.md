# 温度及拟合算法固定场景补测

已完成，结果后规则修订0，无算法晋升。旧E0/R及历史证据保留。

- [打开交互报告](http://127.0.0.1:8784/report/) / [本地HTML](report/index.html)
- [完整结论](CONCLUSION.md)、[事前协议](PROTOCOL.md)、[冻结记录](freeze.json)
- [全部972账户指标](results/v0/summary.csv)、[逐笔交易](analysis/all-trades.csv)、[跳级及7级事件](analysis/grade-events.csv)、[窗口承接明细](analysis/initialization.csv)
- [独立核账](results/v0/audit.json)、[账户前缀](audit/account-prefixes.json)、[原型复现/信号前缀](audit/preflight.json)、[最终来源核验](complete.json)

原11固定场景＋7连续检查，14新政策×18×3=756新增经济账户；旧E0/R/F/HOLD的216账户只读复用。温度四入口×三出口12组，另列原温度T_ORIG与三层L3。旧温度代码0—6只平移显示成1—7，公式不变。原港股单资产代理仍在复用场景中，没有做港股全市场。12组温度未在这些场景均值上超过E0/R，但黄金/恒科存在局部长处。

规则测试、108旧E0/R恒等、21真实输入前缀、14旧原型逐日复现、432账户前缀和972账户独立会计核验通过。默认CSV浮点读取造成的首次控制技术失败及修正前冻结已保留；修正时经济账户0，未改信号或执行规则。见audit/control-parser-amendment.json。

这是指定资产历史择时补测，开发/已见且有重叠；不代表全市场选股、未来胜率或实盘撮合。此次有限授权已收口，不自动继续调参、RS、换仓或账户扩展。
