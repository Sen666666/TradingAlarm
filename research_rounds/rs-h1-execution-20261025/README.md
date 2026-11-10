# RS-H1与买单有效期：固定E0全市场执行修正

本轮已完成，联合版本不晋升。12经济账户（T0/T1/S0/S1×base/cost2/delay1）、12真实技术前缀；各100万元、仅A股、同一2015—2026-10-22冻结数据。E0未改、换仓未加、旧结果保留，结果后交易规则修订0。

[交互报告](http://127.0.0.1:8783/report/) · [结论全文](CONCLUSION.md) · [事前协议](PROTOCOL.md) · [冻结身份](freeze.json) · [完成收据](complete.json)

| 策略 | 旧收益 / 日收盘最大回撤 | 新收益 / 回撤 | 新实际股票数 |
|---|---:|---:|---:|
| T0 | −46.20% / 74.94% | −66.64% / 75.58% | 231 |
| T1 | +28.67% / 65.25% | −65.84% / 83.33% | 317 |
| S0 | −68.84% / 81.60% | −85.92% / 92.33% | 283 |
| S1 | −56.48% / 77.69% | −56.57% / 77.45% | 192 |

RS缺失整批代码回退为0；所有买入订单最多跨一个市场日到首次成交，未成交/部分成交余额当天释放，重新竞争不保留预算、价格或优先级。新股仍需满足原E0预热，未改E0结构退出，也没有增加开盘破支持、保护距离筛选、止盈或换仓。

T1固定年度大赢家240窗参与过从6增至39，但普通损耗扩大、尾部实际贡献下降，不能把参与过当成抓住全年涨幅。T1决策收盘距支持中位从6.86%扩大到11.63%，原E0结构年龄中位14→25观察。短历史和完整历史两组均亏损；单项因果作用没有通过消融账户估计。原代码回退和陈旧意图的旧账户仍作为事实对照，不能据其某些收益较高便认领缺陷有效。

完整下载：

- [12账户新旧指标](comparison/paired-metrics.csv)、[年度](analysis-v2/annual.csv)、[阶段](analysis-v2/stages.csv)、[净值轨迹](analysis-v2/curves.csv)
- [实际行业对照](comparison/actual-industries-comparison.csv)、[实际股票对照](comparison/actual-stocks-comparison.csv)、[按年实际买入](comparison/annual-actual-buys-new.csv)、[逐笔成交](analysis-v2/fills.csv)、[持仓周期](analysis-v2/campaigns.csv)
- [大赢家及错过原因全表](comparison/winner-comparison.csv)、[错过时持仓快照](diagnosis/missed-winner-snapshots.json)、[IPO/预热边界](comparison/leading-winners-readiness.json)
- [短长历史贡献](diagnosis/history-attribution.csv)、[入场保护距离/结构年龄](entry-profiles/profiles.csv)
- [独立逐账核对](analysis-v2/independent-accounting.json)、[订单期限/E0退出核对](audit/order-lifecycle.json)、[RS验算](audit/h1-verification.json)、[真实前缀](technical-prefix-v2/summary.json)、[实现差异](audit/execution-diff.patch)

源数据只读复用旧有效inputs-v2/prepared-v2；5576原始股票池保留，策略1709合格股＋2市值未知、90行业。新建RS缓存覆盖全部账户日期，2015前交易日取已有行业报价日期并集（最早2007），不制造新行情或IPO历史。当前存续、当前市值与当前行业固定，有选样偏差，不是PIT或样本外。权益、源末日缺口及日线执行代理限制沿用旧结项。

核验：1709原型身份行、36,519独立RS算术行、1165截断向量；32项订单/账务行为测试＋1项分组恒等＋1项端到端重新竞争测试；34,392条经济日账独立重放；17,532条真实技术前缀日账精确一致；原30个算法登记文件未变。预计算Timestamp类型错误、预检时钟错误和旧测试夹具缺Rank的失败日志均保留，均在经济账户前修正；归因列标签澄清保留旧结果且数值完全不变，没有结果后交易规则修改。

不直接重跑本目录已有输出。执行来源为code/dispatch_accounts.py，输入身份为freeze.json；复现必须另设新输出并保留当轮代码/输入。first10/A13等继承名称是输入包兼容标识，实际本轮账户清单为12，未重跑B0。四个当前测试入口为test_h1_contract.py、test_sector_account.py、test_dispatch_accounts.py、test_runner_recompetition.py；test_history_runner.py仅复用旧夹具，里面的旧13账户/B0测试不是本轮验收口径。

本轮停止；ROT-01仍为遗留问题，不自动追加账户、寻参、补数或换仓。无港股、微信/Key、外部行情或实盘操作。
