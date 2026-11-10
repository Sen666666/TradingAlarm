# 审计后费用字段更正视图

原封存结果未改，也未重新选股或运行策略。

原CSV的4567个闭合行中，`fees_to_date`还是最终卖出之前的累计费用；`all_fees`、`net_pnl`、收益率和交易流水本已正确。此视图只把闭合行`fees_to_date`改为`all_fees`，原值另存于`fees_to_date_original_reported`，并新增费用时钟和逐笔费用校验字段。非闭合行该字段保持不变。

`conditional_liquidation_net_pnl`及其比例仍是`last_known_mark_day`收盘的历史条件清算估值，不是闭合实现盈亏。闭合盈亏请用`net_pnl`，完整闭合费用请用`all_fees`；更正视图中的`fees_to_date`也已完整。

所有其他原始字段逐字符一致，5454个条件入场轮次按初仓费加actions费用核验；最终卖费漏记金额逐行与最后sell_all费相等（仅浮点呈现差异容差1e-8）。没有改变任何绩效汇总或已冻结经济结果。
