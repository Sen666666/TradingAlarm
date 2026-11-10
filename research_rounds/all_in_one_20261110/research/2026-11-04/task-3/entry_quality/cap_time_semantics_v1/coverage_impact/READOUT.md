# 市值筛选影响与历史cap可用性

本次只检查给定current roster/selection资料和my-quant已存daily_basic/raw/meta，未运行账户或新市场模型，也未下载。**可以量化当前静态名单的排除，也有2026-05-15一个有日期的市值截面；不能据这些资料重建2024或2026年1月当日cap，更不能先认定原运行使用了哪一个快照。**运行时实际绑定由父线程runtime/cp及独审另核。

## 当前静态筛选：能证到哪一层

`a-share-selection-e0-20261024/inputs-v2/roster-dispositions.json`共5,576行：1,709 selected，3,865条已知cap不高于100亿元，2条未知cap保留。canonical 5,517中对应1,681当前过门、3,817当前未过、2未知、17不在该roster。上述是已存静态资料事实，不等于对应历史日期的筛选结果或原账户的买入次数。

selection明确记录：roster_asof=2026-10-22，cap_observed_date=2026-10-24，selection observed_at=2026-10-24T21:56:29+08:00；**market_timestamp_unknown=true**。各股cap_observed_at为该次取值时刻，不是经确认的市值行情有效时刻。不能把“10月24日取到”再升级为“10月24日某交易瞬间的真实cap”。

14个预先指定讨论股票如下。金额均为亿元；当前值为THS company-total-CNY快照，May15值来自TuShare daily_basic的total_mv字段（原单位万元，显式×10,000换CNY；本地normalizer保留原值，未自带field-unit metadata）。名称仅用于固定代码识别，未用未来收益选择。

| 股票 | 当前cap | 当前selected | 本地2026-05-15 total_mv |
|---|---:|---|---:|
| 300085 银之杰 | 195.24 | 是 | 278.20 |
| 002583 海能达 | 146.94 | 是 | 174.04 |
| 300666 江丰电子 | 461.87 | 是 | 503.74 |
| 603061 金海通 | 232.94 | 是 | 269.52 |
| 301611 珂玛科技 | 294.17 | 是 | 545.87 |
| 300604 长川科技 | 1310.85 | 是 | 1329.11 |
| 301308 江波龙 | 1124.69 | 是 | 2475.14 |
| 002371 北方华创 | 3912.68 | 是 | 4291.01 |
| 688012 中微公司 | 2554.57 | 是 | 2713.93 |
| 688498 源杰科技 | 1151.82 | 是 | 1339.93 |
| 301348 蓝箭电子 | 46.34 | 否 | 65.21 |
| 600198 大唐电信 | 90.86 | 否 | 121.37 |
| 300925 法本信息 | 59.80 | 否 | 77.77 |
| 688479 友车科技 | 61.16 | 否 | 58.75 |

这14股当前10 selected、4未过cap门。每股完整原值、实际cap_observed_at、名单disposition、历史cap行数/日期及May15 close/share/mv在`FOURTEEN_PRE_FIXED_NAMES_CURRENT_AND_DATED_CAP.csv`。大唐两记录的严格100亿门结果不同，是可证数值事实；不证明它在2024年应当被纳入，也不证明原策略曾因此漏买。

## 本地historical daily_basic实际只有一天

实际文件`/Users/bytedance/repos/my-quant/data/processed/factors/daily_basic/daily_basic.parquet`：5,495行、5,495股、唯一trade_date=2026-05-15；total_mv、circ_mv、total_share、float_share、free_share、close均无null、非有限或非正值。raw目录也仅该日一个文件，相关6字段与processed逐bit一致。`daily_basic_20260515_smoke`的complete=true只说明该单日批次完成。

raw pull时间为2026-06-04T17:15:36Z，publish为2026-06-04T17:15:48Z。表没有announcement/received/known/available时刻，故“记录标注May15”不等于已证“May15原决策前可用”。[builder字段](</Users/bytedance/repos/my-quant/src/my_quant/data/builders/daily_basic_factors.py:43>)包含total/circ市值及股本；[normalizer395—427](</Users/bytedance/repos/my-quant/src/my_quant/data/builders/daily_basic_factors.py:395>)只是改列名、转numeric和版本，不对单位做倍率归一，也没有生成PIT known时钟。

原7个固定日的coverage：2022-01-10/24、2024-09-24/10-08、2026-01-15/20各为0行；2026-05-15为5,495行。14股×7日=98个请求保留：14个May15有原始dated记录，84个缺当日cap，不填False或外推值。详见`FIXED_DATE_CAP_COVERAGE.csv`、`FOURTEEN_NAMES_SEVEN_DATE_CAP_AVAILABILITY.csv`。

## 两个现存cap截面：阈值不一致但原因未隔离

在canonical中，5,491股同时有当前已知cap及May15 dated total_mv，严格cap>100亿的交叉为：

| 当前THS记录 | May15 TuShare记录 | 数量 |
|---|---|---:|
| 过门 | 过门 | 1646 |
| 过门 | 未过 | 35 |
| 未过 | 过门 | 447 |
| 未过 | 未过 | 3363 |

这482个门结果不一致不能叫482次历史错筛：日期、供应商、company-total与股本/证券单位范围及历史修订可能不同；这里没有做同定义的纯时间干预，也没证明这些值被原run读取。全行对照保存在`CANONICAL_CURRENT_VS_SINGLE_DATED_CAP.csv`。

## 为何shares/close不足以补回缺失年份

这里只存一个May15股本截面；OHLC历史表没有随日total_share/circ_share历史，现有累计复权因子也不能唯一还原现金分红、送转、增发、回购及股本变动。因此不能把当前cap乘历史/当前价比，或把May15股本反向填2024/Jan2026，冒充当日总市值。

即便同日price×share也要证券单位合同：这份daily_basic中5,494股的reported total_mv与close×total_share差在native单位0.000051以内；689009.SH一股reported=乘积的10倍（41.58×7226.5705=300480.80139，而reported total_mv=3004808.0139）。此为字段口径/交易单位待核例，不擅称vendor错误或猜修正倍率；不能把同一公式未经核对推广所有证券。5个最大原始差值见`FIVE_DATED_PRICE_SHARE_RECONSTRUCTION_GAPS.csv`。

**可证边界**：当前静态排除3,865/5,576，canonical中3,817；14预固定股票中当前排除4；May15存在实际dated cap可作独立截面对照。**不可判定边界**：2024/Jan2026各股历史cap应否过门、原run是否用该当前快照、是否存在时点泄漏、哪些排除造成错失，以及经济收益影响。这里均不以UNKNOWN替False、不用currentcap×历史价补造结论。

输入源SHA、实际schema/缺失计数、原字段与raw比对见`DAILY_BASIC_COVERAGE.json`、`CURRENT_STATIC_FILTER_COUNTS.json`、`COMPLETION.json`与`SEAL.json`。本审计范围不是对整个用户磁盘全部潜在数据库“绝无历史cap”的证明。
