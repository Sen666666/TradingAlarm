# 2022-01-24 同scope全本地原信号

已完成5517个唯一请求。状态为{'EXACT_TARGET_STOCK_SIGNAL': 4518, 'MISSING_TARGET_BAR': 999}，full批次墙钟22.587分钟。复用当日target42 exact 4股；三只控制的19个原字段全部精确相同。12worker按约24股块运行，每股完成即JSONL flush+fsync，missing不调用模型，error不写False，已完成ID不自动重跑。

正式入口ALL_SIGNALS.parquet和COMPLETION.json未被后处理改写。全4518条exact收盘与冻结同源特征逐bit一致；missing证券集合与源观察元数据精确一致；每个前缀不晚于本日期，每条exact前缀正好止于本日期。原算法源码SHA未变。

原E0/I/G/numeric的19字段和来源原样保留。仅作知识状态解释：hold在exact且E0 ready后读I，fresh另要求G ready后读I且i_buy；本日hold为{'true': 2117, 'false': 2276, 'unknown': 1124}，fresh为{'true': 177, 'false': 4216, 'unknown': 1124}。未成熟/缺行情保UNKNOWN，不能把初始状态0当已知不合格；raw helper只是便利列，正式根合并独立生成三态解释。没有修改raw i_buy或保护线。

本wrapper只把immutable旧worker代码的DAY/HERE参数化；未执行924日期，未修改原stock_signal或原公式。全价源实际SHA仍11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b。5517是现存canonical本地母体，不是认证历史全证券池；qfq参考/历史available_at、ST停牌和可成交性未认证。缺行不推断上市退市。这里只是stock-only E0/G1_I，不含CP、行业/市场/资金资格、订单、成本或账户收益。
