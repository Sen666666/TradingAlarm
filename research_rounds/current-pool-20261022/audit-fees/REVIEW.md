# A/H 交易费用：有限证据收口（2026-10-23）

本轮得到 25 个费率区间、18 个来源条目，足以替换旧的统一 15bps 成本描述，但**还不是完整南向零售账户的真实费用历史表**。`fees.json` 分开保存官方费率、证据边界和未冻结的研究假设。账户运行 0 次，算法修改 0 次。研究范围截至 2026-10-22；本轮查询已结束，不继续扩展搜证。

研究使用当前存续股票及当前市值、行业、南向资格快照的安排不变。本表不能恢复历史可交易资格；费率区间也不授予某证券在该日上市或可交易的身份。

## 可直接采用的费率事实

下表百分数均为单边费率；“双边”表示买入和卖出各收一次，不能先乘二后又逐边计费。

| 项目 | 研究期内变化 | 来源与边界 |
|---|---|---|
| A 股印花税 | 卖出 0.1%；2023-08-28 起 0.05% | [SSE 原费率说明](https://www.sse.com.cn/services/investors/questions/pay/c/c_20220421_5701222.shtml)、[减半公告](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20230827_5725662.shtml)。两项由主 agent 读取；本子任务的减半公告直读失败也保留。 |
| 沪深经手费 | 双边 0.00696%；2015-08-01 起 0.00487%；2023-08-28 起 0.00341% | [2015 调整答问](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988866.shtml)、[2023 公告](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20230818_5725378.shtml)。2015 页面实际发布日期为 7 月 1 日，URL 不是发布日期。 |
| 沪深监管费 | 双边 0.002% | [2012 调整公告](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988604.shtml)，结合深交所 2019 官方索引文字交叉确认。2015 是本研究截取起点。 |
| 沪深过户费 | 2015-08-01 起双边 0.002%；2022-04-29 起 0.001% | [2015 答问](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988866.shtml)、[HKEX 转述中国结算的正式通告](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/SEHK/2022/CT03722B.pdf)。通告明确沪深 A 股，不能直接扩为北交所证明。 |
| 沪深更早过户费 | 沪：成交面值的 0.03%；深：成交金额的 0.00255% | 同一 [2015 答问](https://www.sse.com.cn/aboutus/mediacenter/hotandd/c/c_20150912_3988866.shtml)。沪市不是成交金额的 0.03%；实际面值和旧最低收费仍未核实。 |
| 北交所经手费 | 2023-08-28 起双边 0.0125%；8 月 18 日公告时原值 0.025% | [SSE 转载证监会公告](https://www.sse.com.cn/home/component/news/c/c_20230818_5725376.shtml)，主 agent 核验。2022 年 12 月另有一次减半，但未核实具体日；不倒推成已证实的完整费表。 |
| 港股印花税 | 双边 0.1%；2021-08-01 起 0.13%；2023-11-17 起恢复 0.1% | [2021 通告](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/SEHK/2021/ce_SEHK_CT_080_2021.pdf)、[2023 通告](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/SEHK/2023/ce_SEHK_CT_158_2023.pdf)。每张成交单据向上取整至 HKD 1。 |
| 港股交易费及交易系统使用费 | 交易费双边 0.005%；2023-01-01 起 0.00565%，同时取消每笔 HKD 0.50 的交易系统使用费 | [HKEX 2022-11-01 公告](https://www.hkex.com.hk/News/Market-Communications/2022/221101news?sc_lang=en)。日线模拟的一笔成交不能冒称真实交易所逐笔笔数。 |
| 港股 SFC / AFRC 征费 | SFC 双边 0.0027%（2014-11-01 起）；AFRC 2022-01-01 起双边 0.00015% | [HKEX 费表](https://www.hkex.com.hk/Services/Rules-and-Forms-and-Fees/Fees/Securities-%28Hong-Kong%29/Trading/Transaction?sc_lang=en)、[SSE 港股通税费](https://www.sse.com.cn/services/hkexsc/tax/)。两项及交易费四舍五入至港仙；投资者赔偿征费在研究期暂停。 |
| 香港结算股份交收费 | 原双边 0.002%，每笔最低 HKD 2、最高 100；2025-06-30 起双边 0.0042%，取消上下限 | [正式费用通告](https://www.hkex.com.hk/-/media/HKEX-Market/Services/Circulars-and-Notices/Participant-and-Members-Circulars/HKSCC/2025/HKSCC-Circular_Stock-Settlement-Fee-Restructure_20250220_f_clean.pdf)；确切实施日来自主 agent 已读的 [2025 中期业绩](https://www.hkex.com.hk/News/News-Release/2025/250820news?sc_lang=en)与[年度业绩第 20 页](https://www.hkex.com.hk/-/media/HKEX-Market/News/News-Release/2026/260226news/260226news_eng.pdf)。这是参与者层面的交易所成交收费；南向客户分摊方式尚未独立证实，旧结构回接 2015 也不是逐版历史档案证明。 |

## 尚不能称为真实执行费用的部分

1. **南向证券组合费仍未知。** 已读 HKEX 的 0.008% 页面明确属于北向，已否决移植；`holding_fee_periods` 留空表示未定，不表示零费率。若需要推进有限经济检验，应由主协议明确一个有名有据的代理或保留费用不完整标签，不能在转换器里默认归零。
2. 北交所更早经手费、监管费和过户费链不足。2023 已确认的部分保留；更早费用只能使用显式经济假设，不能当作官方全链。沪市 2015-08-01 之前还需每股实际面值及旧最低收费。
3. 日线没有真实成交拆单、合同单据合并方式及经纪商转嫁明细。建议明示每证券、每方向、每日一个模拟成交，经纪费最低额按模拟订单日计；这是研究映射。
4. 本表不解决股息税、外币股息兑汇、权益服务费、支付日或南向结算汇率。也没有完成每只海外注册发行人的其他司法辖区税费核验。

这些缺口不再触发本轮无限补证。原始股票池不能因费用缺口被静默删减。主 agent 可以冻结有限、可披露的经济代理；若代理被采用，结果须写“声明假设下的历史经济检验”，不得称完整实盘复刻。

## 交给主协议裁决的成本提案

佣金、滑点和汇兑点差均为研究假设：A 股**净经纪服务费** 2bps、每订单日最低 CNY 5；南向净经纪服务费 5bps、最低 HKD 15；A/H 滑点分别 5/10bps；实际货币兑换点差 5bps。使用“净经纪服务费”是为了与另列的经手费、监管费相加；常见全包佣金已经含部分费用，不能重复计。

沪市早期优先用已有证券面值证据，确实缺失时可提案每股 CNY 1 的未核实面值假设，并报告受影响成交、费用金额及更大费用压力情景。北交所未核实阶段可提案经手费 5bps、监管费 0.2bps、过户费 0.25bps 的经济预留；这些不是已证实的历史上界，也不允许在北交所成立前将三板行情当作北交所可成交股票。主 agent 尚未冻结这些选择。

成本加倍建议对可变交易费、滑点和汇兑点差在最低/最高额和取整前加倍，固定每笔费、最低/最高额及持有费用保持不变。加倍后的法定税率只是压力情景，不是历史事实。最终应以账户协议的具体冻结为准。

## 文件及适配

- `fees.json`：费率事实、区间、来源、缺口、未冻结提案。`from_inclusive` / `to_exclusive` 按市场本地执行交易日；`rate_decimal` 是金额比例，0.0005 = 0.05% = 5bps。
- `source-read-01.txt` 至 `05.txt`：此次读取工具返回的文本与失败；并非原始网页字节或 PDF 文件。`source-manifest.json` 对这 5 份读取记录校验。部分来源由主 agent 取得，`sources.evidence` 明确区分；搜索摘要证据不冒称已取得正文。
- `SEARCH_LOG.md`：12 次搜索及后续官方结果读取的事后审计记录，不伪称事前冻结。
- `verify_fees.py` / `verification.json`：离线检查区间、单位、来源、边界费用和记录哈希。验证通过只证明表内结构及已写公式一致，不证明证据完整、客户分摊或所有证券真实可执行。

薄账本已支持最高费、向上/四舍五入及单独持有费用记账。仍需转换器按日期拆分费表、保留未知项，处理沪市面值计费；不能直接把本 JSON 当作一套无缺口的 `FeeSchedule`。源证据、建表代码和本次检查不更改下载器、算法及既有结果。
