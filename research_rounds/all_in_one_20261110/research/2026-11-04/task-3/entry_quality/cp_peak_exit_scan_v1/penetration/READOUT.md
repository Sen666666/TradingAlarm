# 原MOBILE旧线穿透：六股完整持有期

主表覆盖太保601601、中信建投601066、中金公司601995、人保601319、人寿601628、海能达002583的14个指定原MOBILE层，**从各层实际entry到退出前最后实际持有CLOSE的完整期间**，共209个原held-layer CLOSE点。原47点P10五股+海能达子集保留为P10_FIVE_PLUS_HAINENGDA_SUBSET_*，不是主范围。0账户/模型/回测/新策略/新指标。

`h`取当日CLOSE检查前已生效旧保护线：已有仓用前一原daily层floor；首持日用真实初始order floor，不能拿当日ratchet后新线替代。原当日更新后floor单独保留。所有raw分解先核前后factor与exact source observation，本样本209点同价域；跨factor/缺exact观察将UNKNOWN。CP/I检查仍按原代码先旧线检查后ratchet，不模拟重建持仓。

## 原首次穿线/请求事实

每股各层可共用一条旧线，下表合并同股同日同线。价格单位元/raw股，百分比统一除以前已知Cprev。

|股/层|原请求日 Cprev→C|已生效旧h|ΔC|Cprev−h / h−C|对应百分比分解|原代理fill日/价|
|---|---|---:|---:|---:|---|---|
|601601.SH / [1904, 1914, 1931]|2024-10-09 40.76→36.68|37.907142|4.080000|2.852858 / 1.227142|10.0098% = 6.9992% + 3.0107%|2024-10-10 / 36.661660|
|601066.SH / [1916, 1958]|2024-10-10 28.84→26.77|27.933240|2.070000|0.906760 / 1.163240|7.1775% = 3.1441% + 4.0334%|2024-10-11 / 26.246870|
|601995.SH / [1915]|2024-10-09 42.47→38.22|40.245270|4.250000|2.224730 / 2.025270|10.0071% = 5.2384% + 4.7687%|2024-10-10 / 38.500740|
|601319.SH / [1897, 1911, 1952]|2024-10-09 8.1→7.29|7.694382|0.810000|0.405618 / 0.404382|10.0000% = 5.0076% + 4.9924%|2024-10-10 / 7.256370|
|601628.SH / [1893, 1907, 1930]|2024-10-09 48.4→43.56|45.397655|4.840000|3.002345 / 1.837655|10.0000% = 6.2032% + 3.7968%|2024-10-10 / 43.258360|
|002583.SZ / [2017, 2039]|2024-11-04 25.38→22.84|23.637661|2.540000|1.742339 / 0.797661|10.0079% = 6.8650% + 3.1429%|2024-11-05 / 22.98850|

原14层第一次已存CLOSE≤旧线日期与第一次原CP1_add_protection层请求日期全部一致，对应6个股票事件。ΔC=(Cprev−h)+(h−C)仅是前收盘至当前收盘的价格恒等分解；正超线表示收盘已越线，不能说明盘中何时越线、线价可见、可成交或能按h卖出。实际请求、原whole-order receipt与代理fill单独保存，不把h换成卖价。

14个首持日的Cprev发生在该层买入前，不是持有成本；主表held_previous_CLOSE=False，quantity_weighted_*留空。即使手工乘股数也只是同股数价格分解，不能当真实持仓损益。ACTUAL_ENTRY_REFERENCE.csv单列原actual买时点、raw OPEN、5bp代理买价、实际模拟买费和初始线，没有重构一笔损失。其它日quantity_weighted_*仍是未含费的mark价差分解，不是新退出收益。

## 旧线来源与冻结尺度

209点中185点对应唯一原CP最大值来源；24点为I主导，明确不给CP scale。与structural owner的FLOOR_PROVENANCE.json逐行交叉：209旧/更新后floor完全一致，185个receipt_id/original_scale/scale_frozen_at完全一致，24个I源一致，0不一致。来源采用真正2024_full/inputs/MANIFEST.json及其stock-receipts SHA绑定，未误用universe refs.receipts的其它窗口。

|原事件|旧线形成receipt日|receipt_id|原冻结scale / 冻结日|
|---|---|---|---|
|601601.SH 2024-10-09|2024-10-08|f0446fe6f6ef01f58d7b5720b68290f150d3b7093bc0e67a26fbfa22deda314e|0.015834255171283874 / 2024-09-30|
|601066.SH 2024-10-10|2024-10-08|03de8dc8980503d4a690dcc2b8905eb0afe5da4c107c7a730ebc5c3ab5e7c784|0.012278331045111387 / 2024-09-30|
|601995.SH 2024-10-09|2024-10-08|8f8dae87bb9939266b1c67595b6d14f44d1a66bf94c7d03d8805b79595ee6ae4|0.011741314064419193 / 2024-09-30|
|601319.SH 2024-10-09|2024-10-08|1bc5f831663d24705194148b908e8a3c7237663ae32cffd5c98f4ada7aca05a6|0.011210639425874552 / 2024-09-30|
|601628.SH 2024-10-09|2024-10-08|e272fa910dc241b54467b8c7068ad3c3ed45742c26b9fdf80fa28941c451a220|0.013974536451277756 / 2024-09-30|
|002583.SZ 2024-11-04|2024-10-31|4b4720f2dac26ab8f8693a4de18086b8f524a780c55df860c560e744285143d2|0.03851125614147488 / 2024-10-29|

太保10/9所用旧线来自10/8 receipt f0446fe6…，scale=.015834255171283874冻结于9/30；海11/4旧线来自10/31 receipt4b4720f2…，scale=.03851125614147488冻结于10/29。不能用触发日current s/z或next_scale顶替。每日当日CP cache s/z、receipt/candidate/source day与旧线对应的frozen scale分列，含所有未穿线日。scale_id可跨股票同值，不能单独当全局identity。

## 下一日原代理价格评估列

209行均附expost_next_market_day、exact raw OPEN、raw OPEN×.9995卖价参考、nextO/currentC−1、next raw CLOSE、factor/segment/status。全部是**事后评估标签**，不进入旧线来源、穿线或A/B触发条件。没有调用market.window、容量/wholelot/资金/订单函数；O×.9995不是已证明可成交价或净收益。跨因子/段/缺观察将UNKNOWN；本样本209行都有exact同单位下一源bar。原actual fill字段另列，不以该参考覆盖真实模拟账fill。

人保CORE1884与海CORE1994只在CORE_I_APPENDIX.json，均未混入14个MOBILE层或CP触发表；I附录保持原既有范围，不宣称CP机制。所有receipt、fees和fill是原研究模拟账术语，不是实际broker ACK。

文件：MOBILE_DAILY_PENETRATION.csv/json为209点主表；ACTUAL_FIRST_CP_TRIGGER_POINTS.csv/json为14层首次请求；SIX_ORIGINAL_STOCK_TRIGGER_EVENTS.json为6事件；OLD_FLOOR_PROVENANCE.json保完整源凭证；ACTUAL_ENTRY_REFERENCE.csv保14原买单；EXPOST_NEXT_OPEN_JOIN_RECEIPT.json标事后join与旧字段未改；STRUCTURAL_OWNER_PROVENANCE_CROSSCHECK.json绑定双作者交叉SHA；SOURCE_MANIFEST.json保原提取源SHA。

## 追加：下一日完整HLV的事后标签

主表附actual runtime raw源的下一日HIGH/LOW/VOLUME/AMOUNT，以及原单一`reject_flat_day`过滤标签；全部标AFTER_NEXT_SESSION_FULL_BAR_ONLY，不进入A/B信号。标签false只说明H≤L这一项不拒，不能推定其它可交易状态、容量或成交。容量源码为前20正量均值×.01与当天完整量的较小值；本次没有调用window或重算capacity/候选fill。

海能达11/4原O=L=C=22.84，但H=26.15，V=472899434.99999994；11/5 O23/H23.7/L21.27/C22.32，V=448417365.00000006。11/4不是flat day，不能从O=C推导H=L，也不能据此认定原代理最早只能11/5卖。仍无法从日线证明22.82858或其它价为真实可成交价。原runtime manifest/raw SHA、protocol与源码45–64见HAINENGDA_HLV_PROXY_CHECK.json。
