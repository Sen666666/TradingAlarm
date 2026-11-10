# 奇数分片：原源库存

仅只读原source库存，尚未运行候选FSM、账户、新数量或收益。按原manifest的symbol排序、index为奇数分配，共854股：841 complete，13无本地观察。manifest声明cache截至2026-06-30；不据此补缺失或推断停牌。

|期间|有原价格观察股票|原价格行|明确质量flags有效|原CP收据|
|---|---:|---:|---:|---:|
|2022—2023|805|373182|373181|17901|
|2024-09—12|816|64826|64826|6073|

841个complete均找到原signal/events/CP1/CP1_input路径和所需字段。一个未知质量行为600345.SH的2022-08-05：raw_close缺失，observed_bar=False，synthetic_event_bar=True，price_eligible/source_invalid=None，不能当可交易bar。严格FSM应断暖/无新推进，不应用bool(NaN)。

统计为原源观察和原CP母体，**不是新事件、成交或收益**。完全缺失的市场交易日未由本次库存发现；缺真实停牌、涨跌停、ST、盘口、接收时钟不能自行补成这些状态。

[逐股库存](ORIGINAL_SOURCE_INVENTORY.json)、[汇总](INVENTORY_SUMMARY.json)、[固定股票分片](SHARD_SYMBOLS.json)和[提取脚本](prepare_inventory.py)已保存。等待共享engine/runner的smoke与不可变SHA后，按冻结参数一次批跑。
