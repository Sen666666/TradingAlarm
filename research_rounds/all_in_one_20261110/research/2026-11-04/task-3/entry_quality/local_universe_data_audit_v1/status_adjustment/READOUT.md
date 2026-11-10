# 本地停牌、ST与复权可用性：只读审计

结论：当前my-quant本地文件不能支持2022—2026逐日历史ST/停牌已知状态，也不能提供公司行为公告、现金/股份到账的PIT事件账。OHLC与复权因子可读且数值完整，但尾部仅到2026-05-15；当前qfq使用2026年末端参考锚，不能把该列直接称作历史当时已知的逐事件PIT价格/成交坐标。

| 实际文件（均在`/Users/bytedance/repos/my-quant/data/`） | 行/股票 | 实际日期 | 物理缺失 |
|---|---:|---|---|
| `processed/factors/suspend_status/suspend_status.parquet` | 22/22 | 2020-03-12单日 | 现存列null为0；原20个timing缺失被变为空串 |
| `processed/daily_bars_history/daily_bars.parquet` | 15,739,264/5,517 | 1995-04-06—2026-05-15 | 全部现存列null为0，OHLCVA非有限/非正为0 |
| `processed/adjusted_daily_bars/adjusted_daily_bars.parquet` | 15,739,264/5,517 | 同上 | 全部现存列null为0，价格/因子非有限/非正为0 |
| `processed/adjustment_factors/adjustment_factors.parquet` | 16,214,935/5,517 | 同上 | 全部现存列null为0，factor非有限/非正为0 |
| `processed/securities/securities.parquet` | 5,519/5,519 | 无历史生效日期 | list_date、delist_date各5,519个全空；name均有值 |

以上null计数只针对真实存储行，不是预期全市场×交易日缺行计数。没有历史上市/退市区间，无法由本审计识别完整历史应有母体，也不能用无零成交行推断所有停牌已经覆盖。详细逐列schema、计数、年份分布、文件SHA见`DATA_AUDIT.json`。

## 停牌flag实际含义与缺口

源码[定义](</Users/bytedance/repos/my-quant/src/my_quant/data/builders/suspend_status_factors.py:1>)明确为每日停/复牌**事件稀疏表**；[399—458行](</Users/bytedance/repos/my-quant/src/my_quant/data/builders/suspend_status_factors.py:399>)按symbol/date聚合，`is_suspended=int("S" in types)`、`is_resumed=int("R" in types)`，不是覆盖所有股票日期的状态矩阵。现存21个S、1个R，各事件数1；原22行中20个`suspend_timing`为null，归一后成为空串，不代表timing已知。[空源处理](</Users/bytedance/repos/my-quant/src/my_quant/data/builders/suspend_status_factors.py:487>)只把该日job记skipped，不生成全市场False。

原raw只有1个20200312文件，原pull于2026-06-04T19:12:03Z，单日publish名为`suspend_status_20200312_sample`，其`complete=true/blocking_jobs=0`仅说明这一批job完成。2022—2026没有本表事件行，更没有连续状态覆盖。没有公告/接收时间列；`pulled_at`只是2026年本地采集时间。无事件不等于没有停牌；未知或缺行不能填False。S/R事件和部分intraday timing也不能直接等同“次日OPEN一定可以买卖”。

## ST与公司行为

实际证券表`source=manual_a_share_code_names_xlsx`，来自`data/external/security_master/a股股票代码大全.xlsx`，manifest生成于2026-05-18T06:58:20Z。名称中262个含ST，但没有名称生效起止、ST生效区间、公告日或received/known时刻。[实际builder](</Users/bytedance/repos/my-quant/src/my_quant/data/builders/a_share_securities.py:95>)只读股票代码/名称并把list_date、delist_date显式置NaT。不能据2026年名称向2022年倒填ST状态；当前000620名称“盈新发展”也不证明历史各日名称/风险警示状态。

raw/meta/processed目录名和文件名有限盘点，未找到`namechange/name_change/corporate_actions/stock_basic/dividend/st_status`数据表；相应已检查的显式路径不存在。`adj_factors`别名目录不存在，实际是`adjustment_factors`。源码虽[支持stock_basic](</Users/bytedance/repos/my-quant/src/my_quant/data/sources/__init__.py:503>)，请求为list_status=L且仅名称/上市字段；“支持API”不是已有本地历史数据。盘点范围及样本schema见`BOUNDED_INVENTORY_SUMMARY.json`和`RAW_META_INVENTORY.json`；不据此声称其他未检查目录或外部服务永远不存在资料。

因子raw只有`ts_code/trade_date/adj_factor`，processed增加类型/source/version；缺cash dividend、送转股、配股、除权/股权登记/支付日及公告/known时间。累计因子可用于价格坐标调整，不能单独推导真实现金与股份到账、执行规则或可用现金。

## 复权坐标、未来锚点与量额

[真实调整函数](</Users/bytedance/repos/my-quant/src/my_quant/data/adjustments.py:25>)：qfq OHLC = raw OHLC ×`raw_adjustment_factor/reference_adjustment_factor`；[reference选择](</Users/bytedance/repos/my-quant/src/my_quant/data/adjustments.py:111>)为本次输入每股最新有因子的行情日。[88—101行](</Users/bytedance/repos/my-quant/src/my_quant/data/adjustments.py:88>)把此归一乘数存入adjusted表`adjustment_factor`，原累计值另存`raw_adjustment_factor`。反之独立factor表的`adjustment_factor`是原累计因子，虽然[normalizer写入类型qfq](</Users/bytedance/repos/my-quant/src/my_quant/data/builders/adjustment_factors.py:418>)，它不是已经归一的qfq乘数。两表同名列不可混用。

现存reference日期2026-04-13—2026-05-15；15,733,747行的reference晚于该行行情日，只有每股末行例外。原factor raw/meta是2026年抓取的历史重述，未有历史vintage/announcement记录。本文件因此有未来归一锚，不是历史当时快照。**固定每股常数缩放会在收益比、纯相对价格指标中抵消，所以单有未来reference并不能证明这些指标泄漏未来收益**；但绝对价、raw价换算、股份数量、跨段坐标和执行仍必须有明确因子与事件合同，不能把qfq当raw成交价。现在缺公告/接收vintage，不能据trade_date宣称当时可用。

volume、amount在[调整源码16、42—44行](</Users/bytedance/repos/my-quant/src/my_quant/data/adjustments.py:14>)明确原样pass-through，不做除权调整；[source标准化](</Users/bytedance/repos/my-quant/src/my_quant/data/sources/__init__.py:979>)只重命名vol→volume和amount，不乘100/1000；[daily cleaning](</Users/bytedance/repos/my-quant/src/my_quant/data/cleaning.py:219>)也只转数值。表内没有单位列。因此不可默认volume已经是股、amount已经是元，更不能与复权价直接做价×量=额恒等式。此次未联网验证股票vendor单位合同；本地文档“手/千元”明确段落针对index_daily，不能冒充本次股票表独立验证。固定原行对照见`FIXED_EXISTING_ROWS.json`，可见raw与qfq的volume/amount相同。

两个固定例000620/002583的2022-01-04—06日raw factor分别2.284/5.633，2026-05-15 reference相等，归一乘数1，故这些例qfq价格等于raw价格；不能由此推断其他股票/其他时期无需复权。此为现有数据行展示，不是重建价格或账户路径。

## 实际可用与阻塞

本次只扫描5个现存processed表，读3个raw表小样本、相应metadata及相关源码，约5.86秒。全部扫描文件大小/mtime前后不变并记录SHA；0下载、0刷新、0API、0回测、0上传、0原文件写入。现有OHLC/因子能支持明确坐标的本地价格研究；要宣称历史可交易/ST过滤和公司行为现金股数真实执行，目前缺上述状态/事件及known时钟，不能用False、今天的名称或当前qfq补成已知。2026-05-15之后也不能由这批文件补成2026年6月价格。
