# 两股通道/ATR的原OHLC输入

本阶段只核源与导出，尚未计算通道/ATR，没有账户、新数量或收益。

|股票|源前缀至2026-06-30|2026H1|指定日|
|---|---:|---:|---|
|金海通603061|2023-03-03起805行|116行|1/16、1/19、1/20、1/28、2/12|
|捷捷微电300623|2017-03-14起2257行|116行|1/29、2/2、2/3、2/5、3/4|

10个指定日均有同源O/H/L/C、raw_O/H/L/C及adjustment_factor。全部前缀无缺失、非正OHLC、synthetic或source_invalid，H/L范围约束通过；逐列复权OHLC=raw_OHLC×factor的最大binary64差约1.1e-13。source原price_adjustment标签虽为raw，prepared数字已经乘factor；不能把该标签误当作所有prepared价格未复权。

原prepared signal.parquet由canonical STOCK_MANIFEST标识，逐文件SHA精确核同。保存完整prefix后才能在冻结公式下算此前20/55个有效H及ATR，不能只从10日开始。没有用C替H/L，也没有引用CP_input的C冒充完整OHLC。

输入可用于收盘后的指标演绎；其执行缺口是：prepared、canonical daily_bars schema与两份tail-history bar均无显式停牌、涨跌停价/状态、盘口或tick。positive volume/observed不是可成交证明。历史复权因子也不是PIT企业行动公告审计。本日H/L只在日线完成后可知。

OHLC_COVERAGE.json包含源路径、hash及source_kind范围；TEN_FIXED_ORIGINAL_ROWS.json存10日原字段；EXECUTION_DATA_GAPS.json记录实查schema；INPUT_PREPARATION_RECEIPT.json绑定输入与0指标运行。固定25/18母体引用现存索引，不按结果改选股票。
