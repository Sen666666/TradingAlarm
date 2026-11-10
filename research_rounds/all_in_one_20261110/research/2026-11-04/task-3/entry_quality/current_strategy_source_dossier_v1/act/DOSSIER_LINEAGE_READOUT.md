# 当前 No60 源码 lineage 独立复核

状态：`PASS_CURRENT_NO60_STATIC_SOURCE_LINEAGE_ONLY`，没有未解决的调用链阻碍。

本次独立确认194项文件身份，覆盖102个唯一来源；E0/I的40段带行号原文、CP/PVR的26段和入口说明的11段均逐字对应源文件。仅用AST读取P组件的字符串常量，独立还原No60的effective request/model与route文本，和position_execution交付完全一致。没有执行这些模型或断言函数。

当前入口选原`A.Runner`；收盘先调用`J.planning`，然后N只改pending股票排序，开盘仍为J原执行。实际No60的request、migrate、route使用P的覆盖版本，不能用J未覆盖的3%/60%检查描述当前规则；P的snapshot/plan研究辅助函数也不能冒充原账户路径。

ACT的当前调用明确是`step(..., 'ACT20_BREAK')`。运行入口在事件循环前把RECOVERY替换为`mainline-absolute-Q4-20261031/recovery.csv`，两窗口原BASELINE元数据绑定同一SHA。on时更新episode peak；pause后须真实flat且当日breakout恢复；恢复重设peak并递增episode。它不是保持全期初始峰值的永久20%权益底线。代码原文、BREAK63生成来源与行号见同目录EVIDENCE.md。

E0/I、CP和PVR公式文件在这里是缓存生成来源，实际账户读取既有facts、CP、canonical receipts和对应窗口的scores缓存。原CORE通过上游G1_I旧floor失败使I_target=False，再由J发出I退出，不能因CORE没有第二次直接比线就称其没有价格退出。

盈新链的交易来源是原BASELINE book。其旧v2文件只作为原字段载体，抽取白名单不采用paper quantity/B/grant。此处只确认引用链与文件身份，不重复核算六层金额。trade.pvr的原H1别名与真实priority字段也分开。

限制：这是一份静态源码/存档身份收据，不是新的运行时instrumentation、全缓存数值复算、历史PIT认证或经济有效性结论。策略import、模型调用、指标重算、新账户、回测与价格路径模拟均为0。v4设计和故障理论追加保持停止。
