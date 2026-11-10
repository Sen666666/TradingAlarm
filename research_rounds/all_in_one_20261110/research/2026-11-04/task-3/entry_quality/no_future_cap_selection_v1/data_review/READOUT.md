# 最小无未来市值候选：数据/流动性约束复核

本件只复用已封资料和当前schema/文件指纹，未重扫全部行情、未运行新指标/市场模型/账户，未编辑主实现。结论是**现存字段足以计算固定5517×7的原量价特征和此前20有效观察成交额中位数**；它们不认证历史全A母体、身份、ST/停牌、PIT价格vintage或可成交资格。

## 主实现应使用的实际来源

- canonical：`/Users/bytedance/repos/my-quant/data/processed/adjusted_daily_bars/adjusted_daily_bars.parquet`，键`symbol/trade_date`，价格`close`，量额`volume/amount`，复权`adjustment_factor/raw_adjustment_factor/reference_adjustment_factor/reference_trade_date`，以及source/version字段。没有historical ST、halt、listing/identity版本或received/available时间字段。
- 现成7日特征：`entry_quality/local_observable_selection_v1/features/LOCAL_FIXED_DATE_FEATURES.parquet`，38619=5517×7，`sid/day`、`target_row_present/target_status`、`current_close_qfq/current_amount_passthrough`、`pvr_valid_observation/pvr_clock_block`、原PVR/e及独立fast/slow状态。这里的`amount_ref`是**此前21**观察的中位数，不能直接改名充当此前20。
- 原有效观察契约：`entry_quality/pvr_information_v1/feature_design/features.py::original_observation_clock`。正有限close+amount；若有原optional正向mask则要求真，若有source_invalid/synthetic则要求假；invalid或segment变化重启block。当前canonical没有这些optional源flag，每股单一tushare源段。字段缺失只表示没这项信息，不能扩张成“已知未停牌/非ST/合法上市”。

canonical原扫描为15739264行/5517股，1995-04-06—2026-05-15；现存OHLCVA均finite positive、无null。这个结论只覆盖真实存储行，不覆盖应有而缺失的股票交易日。此次检查其size/mtime仍与既有源SHA`11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b`绑定相同；未再次全表读取或重新声称完整交易日覆盖。

7固定日当日确有源行数量依次为4503、4518、5309、5306、5451、5461、5495；缺行1014、999、208、211、66、56、22必须保留`MISSING_TARGET_BAR`。在已存38619目标行中，present行amount没有非有限/非正值。来源物理首日不是已证上市日，缺当日行也不等于停牌或尚未上市。

## 新prior20 median amount的准确窗口

设当前原block中有效观察序号为j，A为canonical `amount`原值：

`median20_prior(j)=median(A[j-20],...,A[j-1])`。

每个block内独立`amount.shift(1).rolling(20,min_periods=20).median()`；严格不含当日A[j]，不跨invalid/source重置，20个量额必须已知有限正数。不用rolling(min_periods=1)缩窗，不在原block外搜20个较旧有效值补足。current exact row缺失/无效与preparation不足分别留状态，不填0。可同时输出known_count、window_start_day/window_end_day，窗口结束是当前之前最后一个有效个股观察。

这是**20个有效个股观察**，不是20个共同市场session，也不是20自然日；缺市场bar没有自动插入，所以窗口可跨停牌/源缺行。不能因为20个量额完整就说最近20市场交易日都可交易。当前row存在且原block连续时，最早第21个有效价格/amount观察可有此中位数；其ready独立于PVR的85观察、FAST的69观察、SLOW的127观察，不能借这些较晚ready替代liquidity warmup。

此量仅作流动性特征，**无数值阈值、无cash/参与率/仓位含义**；不要顺手添加“低于X排除”、当前cap、未知cap=0或ST字符串过滤。PVR/FAST/CONT仍各自独立readiness；本审计没有另发完整S0许可。

## 原raw单位、复权与可比性

`adjustments.py:14—16,37—44,94—101`仅调整OHLC，volume/amount原样pass-through；`sources/__init__.py:979—1001`仅vol→volume及amount改列名，`cleaning.py:219—236`仅转numeric，没有倍率归一或单位列。已封导出确认所有目标行amount与原daily_bars_history raw_amount逐bit相同。主输出宜标`amount_native/median20_amount_native`或注明vendor原单位；不能默认为元/股，也不能用qfq close×raw volume造原成交额。固定同源amount倍率在PVR的amount/历史median比率中抵消；**原中位数本身不抵消单位**，日后若用绝对资金或参与率阈值，必须另有单位合同。本轮不需要为了没有的人民币阈值临时换算。

qfq为rawprice×raw_factor/reference_factor，reference采用每股文件末端，日期范围2026-04-13—05-15。固定每股reference常数在价格比/原e中可代数抵消，不能据此断言PVR必有未来信号；但rawfactor历史修订/known时刻未PIT认证。amount不复权，prior20成交额不应乘价格复权因子。reference元数据与raw换算仍应留存，不把qfq价当真实raw成交价。

## 无未来cap不等于未知状态已解决

- cap：本地daily_basic只有2026-05-15的5495股dated截面，2024/Jan2026无行，不能按当前cap或单日股本乘历史价倒推。本候选若不用cap，应保持“不使用”，而非把未知cap当0后过滤。
- ST/停牌：证券名来自当前xlsx快照，历史ST区间/公告known时钟没有；停牌表只是2020-03-12的22个S/R事件，非研究期连续状态。无记录不填False，当前name含ST只可注释、不当历史过滤。
- 身份/母体：5517是当前本地series集合，securities的list_date/delist_date全空；无历史代码/改名/退市版本认证。不能把“去掉未来市值门”改称已还原历史全A，或把缺价归因成未来上市。旧池membership、当前行业、当前名字只能按各自来源标注，不默认为PIT。
- 可用时间：trade_date与名义收盘索引不是历史published/received；本件支持完成观察下的因果计算契约，不证明原15:10一定取得供应商数据，更不保证次OPEN成交。

主实现可据此算**固定本地集合上的无cap量价参考候选**，保留数据未知与排序readiness；不能据这些特征声称完整交易资格或收益优势。本件是数据/时钟约束审查，尚未审任何新主实现输出，也没有新threshold建议。
