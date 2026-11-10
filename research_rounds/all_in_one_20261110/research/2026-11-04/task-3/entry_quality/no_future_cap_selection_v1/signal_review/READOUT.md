# 已保存同源选股信号：可用范围与缺口

本次只读封存结果、核哈希与字段，不调用信号模型、账户或运行器，不重算全池，不使用市值输入。

**能立即复用的是2024-09-24固定35股的stock-only E0/G1_I结果。其余六个固定日期没有找到该统一源上已保存的E0/I输出，均记UNKNOWN。七日期有PVR/价格特征，不等于有E0/I信号。**

## 可复用文件与实数

原文件：`entry_quality/selection_qualification_closeout_v1/eligibility_source/fixed35/FIXED35_2024_09_24.parquet`，SHA256 `67ee97e29b889f14ffc3b6799501f96afdc2406b2c9cfb3d34574fe595ca71af`。35条均为exact当日信号；本次核原封存哈希、原算法代码哈希，且35条close与已封存canonical特征的qfq close逐bit相同。

| 限定样本 | 行数 | E0 ready | I target | 当日i_buy |
|---|---:|---:|---:|---:|
| 固定35股并集 | 35 | 35 | 34 | 32 |
| 其中原FULL_LOCAL裸PVR前20 | 20 | 20 | 20 | 19 |
| 其中原OLD1709子池裸PVR前20 | 20 | 20 | 19 | 17 |

两组重叠5股，不可相加。这是两榜名单并集中的35股，不能替代资格后全市场前20；名单的一部分来自旧current-cap子池，也不能充当无未来市值研究的无偏全池。重排时只许沿用其限定样本解释，不能把被剔除者的下一全局顺位猜成35中下一名。

## 信号字段的原义

`stock_signal.py:29–46`使用原numeric joint事件、participation、`decline_candidate=False`的E0及原B5/B4→G1→`project(...,'G1_I')`；没有移植旧native cache的状态。输入为同一canonical qfq OHLCV、截至目标日的完整可得价格前缀。

`policies_g1.py:16–34`的精确关系：

- `warm = g_ready AND grade>=2`。
- `opportunity = E0.target AND warm AND (E0.entered OR g_fresh_up)`。
- 已有I先检查`NOT E0.target OR close<=旧I.floor`退出；否则保护线只取`max(旧I.floor,E0.floor)`。G1_I不因当日转冷自动撤销已有I。
- 若未active、当日未退出且有opportunity，I进入；`i_buy = I.active AND opportunity`，**不是**`i_entered`的别名，可在已有I期间再次为True。
- producer的`stock_hold_signal = e0_ready AND i_target`；`stock_fresh_core_signal = e0_ready AND i_target AND i_buy`。`e0_ready`是原E0准备状态，不能当成G1 ready、PVR ready、市场准买或全S0资格。

反例：600550在9/24的I仍1，但G1−3、i_buy=False；600268的G1=2、I1，但无fresh/entered，i_buy=False；600675的G1=2且fresh，却E0/I为0。**持有授权、暖度、新事件是不同量。** `i_buy=False`也不能推断原MOBILE全被禁止：原continuing+freshCP还有独立路径，此批没有同源CP收据。

## 六目标股×七日期

42个固定单元中，1个有完整数据/代码哈希绑定的exact信号，2个有同源pilot信号但输入哈希证据较弱，39个无已存同源信号。明细为 `TARGET6_SEVEN_DATE_SIGNAL_AVAILABILITY.csv/.json`，UNKNOWN值保留空值，不写False。

| 2024-09-24 | qfq close | ready / I target / i_buy | 来源与限制 |
|---|---:|---|---|
| 银之杰300085 | 15.82 | 1 / 1 / True，G1=4 | 固定35完整封存 |
| 盈新000620 | 1.45 | 1 / 1 / False，G1=−3 | PILOT.json；producer明确同canonical路径，目标close逐bit相同；pilot收据只存代码哈希，未单独存输入文件哈希 |
| 海能达002583 | 5.24 | 1 / 1 / True，G1=4 | 同上pilot证据限制 |
| 江丰300666、金海通603061、珂玛301611 | 有价格 | UNKNOWN | 无已保存同源E0/I；不借旧复权/native路径补值 |

其余六日期为2022-01-10/24、2024-10-08、2026-01-15/20/05-15：六目标股E0/I全部UNKNOWN。42格中38格有canonical当日价格；4格无价格为金海通/珂玛的两个2022日期。这只证明源无当日行，未据此认定上市/退市或停牌。

`LOCAL_FIXED_DATE_FEATURES.parquet`共38,619行=5,517股×7日，schema没有ready/i_target/i_buy；其`E/E_fast/E_slow`为PVR证据，不能替代原E0/I。已停止的72条partial既非全池，亦没有六目标股的新补充。本次没有恢复该长跑。

## 保留的口径限制

35股的`S0_eligibility_q`全部原样未评估None。市值门、历史证券范围、行业/市场资格、H1新鲜度、停牌/ST、CP、持仓/订单/ACT没有由此批信号认证。当前市值和旧订单不用于补资格。

35股qfq参考日均晚于2024-09-24。这里的“仅用截至t的价格行”不等于已认证历史时点复权因子或available_at；原封存的canonical输入SHA为`11e7f9e38798e6e411f33b3250c564bcd5fcfbe34af2bda74e04c02cf8d08d9b`。本次核保存结果和引用哈希，没有重新扫大源或把收盘逐bit相同扩成整段前缀独立认证。两条pilot证据更弱，须单列，不能冒充完整输入哈希绑定。

已输出35股原信号行、七日覆盖表、42格目标明细、字段原码与核验收据。要扩大同源信号覆盖仍需另行授权有界计算；本任务未执行，也没有用不同复权信号填空。
