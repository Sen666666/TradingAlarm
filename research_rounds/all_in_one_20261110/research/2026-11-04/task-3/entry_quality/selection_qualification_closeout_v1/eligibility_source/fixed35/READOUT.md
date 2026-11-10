# 固定35股：裸PVR与原stock E0/G1_I信号门

2024-09-24、FULL_LOCAL原PVR前20与OLD1709_EXACT_SUBPOOL原PVR前20，40名单行、重叠5股，冻结为35唯一股票。名单源为已存`local_observable_selection_v1/ranks/ALL_TOP20_LISTS.csv`，没有按未来价格或收益选样。

已完成`FIXED35_2024_09_24.parquet/.csv`。parquet SHA256：`67ee97e29b889f14ffc3b6799501f96afdc2406b2c9cfb3d34574fe595ca71af`。2股600292/600718复用已停止批次的完整行，已核canonical及全部原代码SHA相同；剩余33股仅一次6worker补算，27.36秒。开始前曾修正名单文件的相对路径，错误发生在创建样本freeze/启动任何signal worker前，保留原日志。

| 固定样本口径 | 样本数 | E0 ready | E0/I target | 当日i_buy |
|---|---:|---:|---:|---:|
| 35股并集 | 35 | 35 | 34 | 32 |
| 原FULL_LOCAL裸PVR前20 | 20 | 20 | 20 | 19 |
| 原OLD1709裸PVR前20 | 20 | 20 | 19 | 17 |

两原榜有交集，分栏不可相加。所有目标信号与此前PVR导出的当日canonical qfq close逐bit一致。原E0/I字段、G1 grade/fresh/reasons、floor、原numeric event/leg、qfq来源元数据均在表内。

使用父目录`stock_signal.py`的原纯函数链：numeric joint事件/原participation事实→`decline_candidate=False`的当前E0 policy；独立原B5/B4 evidence→原G1 classify→`project(...,'G1_I')`。只读取截至2024-09-24的完整可得前缀，不加载账户/旧IX target，不改参数。该wrapper已执行并绑定源SHA；没有把执行成功冒充独立代码审查或经济有效性证明。

`stock_hold_signal`为E0 ready下i_target；`stock_fresh_core_signal`为E0 ready下i_target AND exact当日i_buy。按原score降序、同值sid先序，在**这35内**给出`fixed35_bare_PVR_rank/fixed35_hold_PVR_rank/fixed35_fresh_PVR_rank`。

| 未有当日新I/core事件的原例 | 裸榜位置 | 事实与原因 |
|---|---|---|
| 600550.SH | FULL #5 / OLD #1；PVR94.9394 | E0/I target仍1，G1−3、fresh=False，当日numeric event−1，i_buy=False |
| 600268.SH | OLD #15；PVR84.1279 | E0/I target1、G1=2，但fresh=False、无base新进入，i_buy=False |
| 600675.SH | OLD #18；PVR83.4866 | G1=2且fresh=True，但E0/I target0，i_buy=False |

前两股是“无当日新I/core事件”，不能据此说原策略全部新增被禁止：原MOBILE另有continuingQ+freshCP路径，本表未生成或检查新CP收据。第3股也说明warm/fresh与E0 shadow授权不是同一条件。

这不是全5,517股信号合格全集，更不是资格后全局前20：若原榜某股被信号门剔除，真实全局下一顺位未必属于这个35股并集。此处仅演示同一限定样本中裸score与信号门的差异。

完整原S0仍需要currentcap>100亿、行业/issuer、stock/sector共同ready、sector trend和市场buy_allowed等。输出`S0_eligibility_q`全部为未评估None，和由某缺因算出的q unknown/False不同；父线程另附必要cap门及行业/市场资格证据。本表不填True或借旧持仓/pending/ACT造资格；无账户、订单、资金量、收益或未来label。

父目录原全5,517批次已停止、72条partial及停止收据仍原样封存；本次没有恢复该长跑，没有新增优化管线。
