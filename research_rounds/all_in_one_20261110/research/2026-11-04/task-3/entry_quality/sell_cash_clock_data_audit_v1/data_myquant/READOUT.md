# my-quant 本地数据盘点

只读仓库：`/Users/bytedance/repos/my-quant`。扫描 `data/raw / processed / meta / external` 共 **24,985** 个文件；实际元数据目录是 **data/meta**。未联网、未补数、未调用行情provider、未跑模型/账户、未读取凭证值。大Parquet只读footer；只对停复牌、涨跌停和行业归属小表读取必要列。

| 数据类别 | 本地已核覆盖 | 质量、时钟与缺口 |
|---|---|---|
| 原始日线 OHLCV | canonical **15,739,264行**；全局日期 **1995-04-06—2026-05-15**；raw 5,517份/成功计划5,517项 | 仅日期标签，无逐笔/盘口/公告时间。**831**项artifact恰6,000行；000001请求从1991起但产物6,000行，早史截断风险未排除。全股票×交易日完整性、退市母体、全表重复键未重新扫描，均UNKNOWN；“任务成功”不等于历史完整。 |
| 分钟、tick、quote、trade、盘口 | 四数据根文件名及已审canonical schema中**未识别到** | 无可核年份/覆盖；不代表全电脑从未存在。日线OHLC/成交量不能证明某时刻可成交、排队次序或成交现金到账。 |
| 涨跌停价格 | **2026-05-15单日7,599行**；`stk_limit`；key无重复 | 5,517行symbol匹配当前证券表，另2,082行在表外，不能称7,599只原A股。`pre_close`空2,104行；920178.BJ上下界为99999.99/0，可能是无涨跌幅限制哨兵，语义UNKNOWN。无2022—26连续历史、无发布时分。 |
| 停复牌事件 | **2020-03-12单日22行**；21条S、1条R；`suspend_d`；key无重复 | 稀疏事件，非全日可交易状态表。缺行仅表示未观察到事件，不是供应商确认可售；不能把样本扩写成历史停牌覆盖。`suspend_timing`是事件字段，非本地已证的发布/可知时间。 |
| 每日ST/证券状态/上市退市 | securities **5,519行**，schema无daily-ST；`list_date/delist_date`全部空 | 不能用当前名称回填历史ST、限价档或退市/停牌状态。其他状态源未识别，历史覆盖UNKNOWN。 |
| 复权/公司行动 | factors **16,214,935行**，同1995-04-06—2026-05-15；adjusted bars 15,739,264行 | 只有symbol/date/factor，不是公告、除权、登记、支付、送股可售时钟。QFQ以输入中每股最新factor为锚（源代码`adjustments.py:37`），产物reference_date在2026-04-13—05-15；不能当历史原价或CA执行事实。 |
| 行业/归属 | taxonomy 465行（2026-05-16快照）；membership 12,780行（snapshot 2015-10-26—2026-05-15）；board daily 599,118行（2020-01-02—2026-05-15） | membership标记`effective_dated`、`lookahead_risk=false`，但12,777行`known_from`早于统一`observed_at=2026-05-15`。这是已保存的effective-date语义，**不是**独立核实的历史发布时间；board资金流数值完整性未核。 |
| 其他因子/技术特征 | daily_basic/moneyflow/margin_detail均仅2026-05-15样本；hk_hold 2019-06-25、index_daily_basic 2020-03-12、top_list 2018-09-28各单日；28个技术特征分区 | 技术特征为日线派生，并非新执行数据。index_daily_bars计划pending、两次失败且无canonical产物；hk_hold还有1 pending。不能将代码支持的lane当已落全史。 |
| 真实发布时间、撮合与结算 | manifests有`pulled_at`、`created_at`；例如停牌2020-03-12样本于**2026-06-04**拉取 | 这是采集/处理时钟，不是2020年原发布时钟；所有所需quote/trade/经纪商成交/可用现金实际到账时钟均无本地证据。 |
| 行情许可 | **UNKNOWN** | README“仅授权元数据”一句不构成行情使用或转授权条款。所读manifests仅来源、接口、拉取/保留信息；根目录无LICENSE/COPYING/NOTICE。代码许可即使存在也不能替代行情许可；未外连核验账户权限/条款。 |

这批本地日线可供受限的日级研究输入核对，但**不足以认证历史卖出可执行性和真实现金可用时钟**。没有用缺失状态推定可售，也没有把复权factor当公司行动支付事实。

证据：`PARQUET_FOOTER_EVIDENCE.json`记录schema/行数/日期与null footer统计；`SQLITE_READONLY_EVIDENCE.json`记录12个checkpoint的只读schema/状态；`METADATA_AND_RIGHTS_EVIDENCE.json`记录21个选定源SHA、采集时钟、有限小表质量与许可边界；`EVIDENCE.json`为汇总入口，`DELIVERABLE_SHA256.json`绑定本目录最终产物。SQLite采用`mode=ro&immutable=1 + query_only`，核查时均无WAL/SHM。

可复核源码/文档：README第34—69行说明四数据根和meta权威性；`src/my_quant/data/sources/__init__.py:560`仅日线请求接口；`src/my_quant/data/adjustments.py:37`说明QFQ最新锚；`docs/external-factor-data-catalog.md:629`明确停牌稀疏事件缺行不等于显式0。代码检查与数据事实分别保留，未以当前代码证明旧采集端完整性。
