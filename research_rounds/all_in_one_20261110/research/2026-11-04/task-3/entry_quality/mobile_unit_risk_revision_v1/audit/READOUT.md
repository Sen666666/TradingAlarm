# 九个固定原入场点：单笔风险与现金必要门独审

**局部算术通过；没有最终授信或替代账户收益结论。** 只使用父线程指定的盈新六层[68,69,75,78,113,122]与已保存海能达链三层[1994,2017,2039]，没有扩样本或按未来结果另选交易。

海能达来源为 [COMPLETE_ORIGINAL_CHAINS.json](/Users/bytedance/Documents/Codex/2026-11-04/task-3/entry_quality/structural_failure_v1/chains/COMPLETE_ORIGINAL_CHAINS.json) 的既有附加控制链，campaign_id=`2022_2024|002583.SZ|1|2024-10-15T09:30:00+08:00`。三笔分别是CORE Oct14→Oct15原100股、MOBILE Oct18→Oct21原1100股、MOBILE Oct21→Oct22原1000股。旧文件的winner标签只解释既有材料身份，不进入本次公式或新选样。

## 独立核法

1. 从原StockManifest绑定facts、CP1_input、CP1缓存，读取**当日CP features的s**，核对该决策前64个同source价格对应63个旧收益，严格排除当日收益。用的是原`1.4826×median(abs prior63 logreturn)`及原1e−8地板，不是receipt旧scale，也不是带S_MIN地板的z；没有重跑CP/I/PVR模型。
2. h来自该笔原冻结intent：CORE用原I线，MOBILE用当次原max(I,CP candidate)，在各时点用原factor转raw。独立Decimal精度50计算`h_stress=h×exp(−2s)`，买价含原5bp，假定卖出参考价再减5bp，原dated买卖费用各计一次。
3. 对两个角色统一核`R_order≤0.0025×signalNAV`，按dated BUY格点验证chosen及下一格。信号先冻新risk/stock10%上限；OPEN仅缩，冻结h/s不读取当日未来CLOSE。新风险定量替代旧MOBILE 2%gross，**没有用旧MOBILE sourcecap截新量**；旧cap只作对照。
4. 现金是各笔**真实原PVR预留槽位**：前一原CLOSE available，加该OPEN已经真实settle的净款，减目标reserve前其他实际预留gross＋fee，再扣原10%signalNAV现金底线。逐项对原audit截止和现金零组件核对，没有用信号日现金代替OPEN可用现金。

## 结果

| 股票/层 | 角色 | 原真实q | 新信号冻结q | OPEN风险＋stock上限 | 再经原槽现金必要门 |
|---|---|---:|---:|---:|---:|
| 盈新68 | CORE | 100 | 2800 | 2100 | **100** |
| 盈新69 | MOBILE | 6300 | 5400 | 4700 | 4700 |
| 盈新75 | MOBILE | 5700 | 4900 | 4200 | 4200 |
| 盈新78 | MOBILE | 4200 | 4400 | 3300 | 3300 |
| 盈新113 | MOBILE | 5100 | 3300 | 2900 | 2900 |
| 盈新122 | MOBILE | 4700 | 3000 | 3000 | 3000 |
| 海能达1994 | CORE | 100 | 1100 | 1000 | 1000 |
| 海能达2017 | MOBILE | 1100 | 800 | 800 | 800 |
| 海能达2039 | MOBILE | 1000 | 700 | 500 | 500 |

九点最低合法手在单笔R条件下都非0。盈新68的OPEN单笔风险局部量2100，原槽available只有100,061.4232403188545元；原10%signalNAV现金底线99,568.81481055140045元，剩492.60842976745405元，dated买价/费用仅容100股。该现金证据不证明它是原量唯一原因。

海能达三个原槽现金上限分别37000/21500/5400股，均未进一步压低1000/800/500。原CORE实际100也不能据此宣称可以扩成1000，因为池、行业和其他原门仍未核。

## 判定边界与版本

主要收据为 [NINE_FIXED_POINT_AUDIT.json](NINE_FIXED_POINT_AUDIT.json) 与 [audit_nine_fixed_points.py](audit_nine_fixed_points.py)。全部源SHA、原h/NAV/q、63时钟、费用、risk/stock格点、实际OPEN槽位现金均已核；浮点exp显示与独立Decimal50按1e−8元核同，整数股数精确一致。

绑定最终CARD SHA **39657c604d3f224e9b5f9d502f0b0bd3591de1fe569d390053b5c1ee40bd0bf3**。当前卡是stock并发0.5%currentNAV、industry并发1%currentNAV、live K含已付买费；本审没有计算这些并发ρ、池/行业完整占用或其他全组合准入，也没有套用已撤销的D历史硬门。

以上每行是自身原前缀的一次条件纸算，不能把修改后的量串成新资金序列。压力2s是预先固定的参考缓冲，不是95%界、法定涨跌幅或保证成交线；真实持有/退出合同仍是原h。没有计算新PNL、可避损或收益提升；0新账户、0模型、0参数扫描，停止扩展。
