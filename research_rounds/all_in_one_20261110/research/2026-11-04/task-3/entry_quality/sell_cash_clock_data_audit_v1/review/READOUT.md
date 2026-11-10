# 卖款时钟、数据与最小修复：独立复核

本件只读当前No60源码和本轮本地盘点证据；不联网、补数、运行模型、账户或新回测。

## 1. 账内资金顺序与执行代理须分别表述

[J.opening:304–318](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:304)先对已有退出请求取得sell window并fill，再settle/sync，随后决定新买的数量与reserve。[SectorAccount:746–797](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:746)在生成模拟卖出fill后建立Settlement；[799–808](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:799)只在due_at到达后增加available。当前A协议settlement_lag_sessions=0，[FastMarket.lag:17–21](/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py:17)据此把due_at设为同一OPEN事件。No60覆盖后的route仍检查available及现金留存，不因sale receivable计入NAV就把它直接当现金。

因此，源码支持两项不同结论：

- **账务顺序：** 没有在这条路径中直接把未成交卖单的预计金额加进available；先有研究账生成的sell fill，再有到期回款和买单reserve。局部原事件桥也不能自动证明“没有该卖款，这笔买单就不可能成交”。
- **时间可实现性：** [FastMarket:53–63](/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py:53)用当天有效性、全日volume及high/low平盘条件生成OPEN成交窗口，卖量也受全日volume容量约束。日终才完整的条件在模拟中决定OPEN sell fill和回款，再资助新买。这是执行代理提前确认可用的时钟问题。生成的FillReceipt是本地ledger记录，不是交易所或券商实收回报。

买入自身的window在全轮fund之后查询，不能据此泛称全日HLV不影响资金选择：卖出窗口已在资金选择前使用。已有完整账户结果是在该日线代理约定下生成的，真实可实现收益尚未由本代码证明。

## 2. 最小修复是事件和资金来源闭合

保留前CLOSE的信号与额度记录；真实执行另记行情的exchange_time与received_at、决策时间、send、ACK、partial fill、cancel request/ACK及余额确认。只用实际已收到且当时已可用于交易的资金资助新买；卖单已发送或仅ACK不增加可用金额，未成交余股继续占库存/退出责任，partial只按已确认部分更新。买单reserve要原子扣占可用余额；成交/取消回报须按order/fill标识去重和对账，避免乱序、重复或陈旧余额重复释放资金。这里不假设券商条件单。

新买必须使用其决策时已收到的报价，并由更晚的有效执行事件确认价格/数量；不能在收到最终OPEN后重算数量，再追记参加已经完成的同价撮合。只改成“延后一个event”不会解决：若该event仍读取完整当日HLV或回填同OPEN成交价，因果缺口仍在；event序号也不证明真实传输、排队与余额可用时间。本轮仅列接口修复范围，不编写适配器或运行新账户。

## 3. 本轮有限本地数据的实际覆盖

以下只对应owners本轮盘点目录、样本/footer与元数据，不代表扫描全机或所有外部供应商。

| 本地来源 | 已发现证据 | 对执行研究的边界 |
|---|---|---|
| my-quant/data | canonical daily 15,739,264行，1995-04-06至2026-05-15；复权因子表16,214,935行，仅symbol/date/factor等因子字段；四数据根及已审schema中未识别到分钟/tick/盘口 | 日线/因子可供原频率研究；不是分钟、逐笔、盘口或真实权息现金到账事件。不能从因子推导publication/到账/新增股可卖时刻；831项raw artifact恰6,000行，完整早史未证明 |
| my-quant限价/停牌样本 | 本轮见到的limit样本为2026-05-15，suspend样本为2020-03-12 | 单日/局部样本不能替代2022–24及强窗全段逐时可交易性历史；未检范围保持未知 |
| TradingAlarm/data | 2026-10-16单日17标的、3,205点局部分时价格采样；1143标的单时点raw numeric quote | 分时数据确实存在，但不完整且非tick。quote的bid/ask字段映射及exchange/receive clock未核，不能自动当可执行双边盘口，更不能覆盖早年历史窗口 |
| TradingAlarm/runtime | 8批、9标的paper-quotes的history实际为id210、period16384的daily snapshots；另有1799条series的最新market bars | 早盘取到的当日bar可能仍在形成。名称中的quotes/history/paper不自动等于逐笔行情或自有订单回报；最新日线/采集时间也不证明历史盘中可得性 |
| TradingAlarm权息 | 最新prepared有16,720条declared_research_proxy事件，paid_at与新增股可卖时间已知数均0；另有蓝旗科技8条权益的announcement_date/record_date/ex_date | 八条公告日期是有限正面证据，不能外推全池或原始发布时间；支付/可卖时钟仍未知。精确现金/可卖时钟不能凭现有proxy认证 |

两个库不能仅因symbol/date相同就拼成相同source与历史时钟；价域、复权、停牌/限价、字段含义和采集时间须保留来源。代码LICENSE即使存在，也不自动赋予所附行情的使用或再分发许可。TradingAlarm README/docs已记录原用户对本人客户端指定行情服务的只读研究授权；该证据与第三方许可、一般商用/再分发范围分开。my-quant所审本地文档未给出明确行情许可。第三方具体范围保持UNKNOWN，本轮没有据条款缺失推断违法，也没有停止已授权的本地只读审查。

TradingAlarm也有正面的收包时钟证据：paper-quotes的attempt receipt保存received_at，history_batch在receive返回并保存response后记录它；恢复缺receipt的路径则明确received_at=None、另记recovered_at。这个received_at是整包日线响应的本地接收记录，不能升级为各历史bar的exchange time、历史首次发布时间或逐笔可执行quote。refresh的observed_at和本地published_at还须分别保留采集/处理/本机发布含义，不能混用。

## 4. 分阶段STOP，保留可继续的工作

| 阶段 | 具体停止条件 | 仍可继续 |
|---|---|---|
| 当前源码/来源审计 | 不需以分钟数据或供应商合同未齐为由停掉本轮审计 | 读取已有源、metadata、schema/footer和许可文本，报告found/未在本次范围发现/未检查三态 |
| 原日线研究 | 可保留原执行proxy；停止把它包装为已验证的实盘收益或组合收益下界 | 原结果解释、输入/费用/现金恒等核对；本轮不启动新的金融路径 |
| 更细时钟的历史重放 | 目标证券/日期缺相应频率行情，或bar时间标签、exchange/receive clock/可用时点未明确 | 先完成字段映射、覆盖和异步接口设计。分钟整根OHLC不能在该分钟开始时视为已知 |
| 成交量/盘口/队列论证 | 只有成交价/打印序列或单时点quote，缺支持所主张规模的双边报价/数量、深度或队列及其时钟 | 明确保留价格/成交假设的研究proxy；不能据单侧成交记录认证买卖双边可成交量 |
| 卖款回用或真实执行认证 | 缺可追溯的自有sell fill及当时可交易余额/确认时间，或订单/回报时钟未闭合 | 只审账务和接口；tick或depth本身也不证明自己的订单已成交、余额已增加 |
| 新增数据取得/用途扩张 | 拟取得或新用途超出已明确的原用户只读授权，且本地证据尚不能确认对应数据、账号权益、用途或再分发范围 | 本轮按指令不外连/补数；不对未确认的新取得/用途作已授权承诺，先识别具体边界。不宣称无权或违法，不停止现有本地只读审查 |

判定：**源码现金顺序已确认；执行实现与细粒度历史收益认证尚未完成。** 缺口对应数据和执行阶段，不能把整个研究任务拒绝，也不能用代理成交回报冒充真实收到的成交/余额。本次没有修改原账、原源或补做行情。

薄审绑定：[源码owner证据](../code/EVIDENCE.md)、[my-quant有限本地盘点](../data_myquant/READOUT.md)、[TradingAlarm有限本地盘点](../data_tradingalarm/READOUT.md)。独审核对源与交付身份、源码摘录、盘点中的scope/UNKNOWN及收包/采集时钟解释；不重复24,985文件盘点、原账数字抽取或全池数据质量计算。
