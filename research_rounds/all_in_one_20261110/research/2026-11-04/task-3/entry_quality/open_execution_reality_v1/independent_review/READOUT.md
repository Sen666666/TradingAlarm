# 开盘执行时钟：独立源码复核

**结论：当前实现是“已知当日最终OPEN后定量/拒单，再以同OPEN加减5bp记成交”的日线执行代理。前收盘冻结的是信号、上界和预算；最终资助股数在OPEN事件内决定。源码没有证明这组数量和价格能在真实市场按同一开盘撮合实现。** 本次只读源码/规则JSON，无测试、模型、订单、回测或新执行方案；官方交易时段规则由主线程另行核查。

## 实际调用顺序

No60 [native_adapter.py:31](/Users/bytedance/Documents/Codex/2026-11-04/task/pvr_pool_feasibility/native_adapter.py:31)明确保留J.opening，route则使用P的覆盖版本。以下引用的是该生效路径。

| 时点 | 源码实际做什么 | 已冻结与新决策 |
|---|---|---|
| 前一CLOSE | [J:255–259](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:255)生成pending intent；CORE再resize | 信号、真实floor、预算、最大股数及排序来源已知；pending尚不是已提交交易所订单 |
| 下一OPEN事件 | [J:304–307](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:304)先尝试全部退出，随后settle/sync | 实际代理卖出及结算结果先改变后续可用资金 |
| 同一OPEN事件 | [J:311–318](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:311)直接读`raw.loc[day].open`，preview、route、reserve | 最终拒单/数量及池选择在看到该最终OPEN后确定；[LR:56–66](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:56)还依OPEN决定是否穿线、风险和资金可行量 |
| 同一OPEN事件 | [J:320–323](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:320)对已资助买单查询window，断言window价等于preview价后fill | [FastMarket:60–63](/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py:60)用`open*(1+slip)`买、`open*(1-slip)`卖；当前协议slip=5bp |

[LR.reserve_quantity:94–102](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:94)明确标注`known_open_funding=True`：原信号的`decision_at<at`，但这份买单对象、目标股数及现金reserve是在`at`才建立。保留前一CLOSE的signal_at不会把OPEN资金决策提前。原[事件循环:98–103](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/launch_v3.py:98)在同一OPEN时间戳内完成这些步骤，没有订单传输、交易所接收、撤单确认、队列或行情后到达成交的独立时钟。

## 日线窗口还有事后条件

[FastMarket:53–63](/Users/bytedance/Documents/ChatGPT/money/research_rounds/temperature-sizing-20261026/code/fast_market.py:53)用当日有效性/全日volume、是否high<=low，以及`min(过去20个正量日均量×participation_rate, 当日全日volume)`确定窗口/容量。它的execution_basis原文就是`explicit_daily_bar_proxy_past20_capacity_same_day_hlv_postcheck`。底层[ledger:688–734](/Users/bytedance/Documents/ChatGPT/money/research_rounds/rs-h1-execution-20261025/code/sector_account.py:688)按window价与容量生成部分或全量成交，不能从此推出开盘盘口上已有相应可成交量。

“先完成资金选择才查日高低量”只适用于该轮**买窗口**查询顺序。退出窗口在J304–307先执行；其事后窗口/容量决定卖出数量及可结算卖款，随后再资助新买。因此，全日字段可通过先卖后买的现金链间接影响本次OPEN的资金分配。这里没有把未来HLV直接塞入信号公式，但也不能称整个资助结果只依赖开盘前可观测信息。

## 三种说法的界限

- **“集合竞价提前下定额单”不足以解释本源码。** 金额预算可在前收盘已知；本源码却在最终OPEN已知后重算最大合法股数、拒绝穿线、按真实可用现金顺序reserve。提前提交的固定股数/限价单，或某种金额单，均不能仅凭名字证明等价于这个组合决策函数。本复核不假设券商条件单或服务端自动换算。
- **“9:25看到OPEN，9:30按同价成交”不是源码已提供的实现证明。** 当前OPEN日历时间戳为09:30；没有9:25观察、提交、确认和后续独立撮合路径。即使某市场能提前公布该开盘价，之后提交的订单仍需单独证明可成交时点、价格与数量；开盘价加5bp只是一项代理假设。具体竞价时段及订单可撤改规则以主线程官方核查为准。
- **“日高买、日低卖是保守收益下界”不成立为一般账户结论。** 对预先固定股数、固定交易集合，H/L替代可表达更差价格的静态压力；该极值何时出现、是否有足量可成交、是否能满足原退出与资金顺序，日线不能证明。只要按更差价格重新定量、拒单、结算或触发后续ACT/资金反馈，持仓路径与交易集合也会变，完整账户收益不保证单调下降。即使称压力代理，也必须保留这些限制，不能叫真实可执行成交或已证明的组合下界。

可据源码保留的表述是：**信号来自前一CLOSE，资金与最终数量在已知OPEN的事件中重核，成交使用冻结的日线代理及费用/容量规则。** 已有结果是在这套模拟约定下的账户结果；真实部署可实施性没有由当前日线代码、5bp或事件顺序单独认证。本次没有更改已有账户或源文件。
