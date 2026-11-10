# 盈新发展：原策略六层真实交易证据

范围仅000620.SZ的68、69、75、78、113、122层，2022-01-10信号至2022-02-08实际清仓。只原源码/原账，不含v3共享预算、候选数量、风险假说或新回测。金额单位人民币，信号15:10，实际成交09:30；表内cap、真实reserve target、实际filled是三个字段。

## 六笔真实买入

|层/角色|信号→实际OPEN|intent cap→下单target/filled|OPEN预留前available|实际价格|买费|原gross budget / CORE risk_budget|同股原股数|初始floor 调整/原始|
|---|---|---:|---:|---:|---:|---:|---:|---|
|68/core|2022-01-10→2022-01-11|3200→100/100|100,061.423240|3.011505|5.026712|8,804.370000 / 2,489.220370|0|2.255055048923375 / 1.979999999999999859515624618|
|69/mobile|2022-01-11→2022-01-12|6500→6300/6300|152,659.061074|3.081540|6.721995|19,618.637121 / —|100|3.071411301898207 / 2.696783114302186790939003270|
|75/mobile|2022-01-12→2022-01-13|5900→5700/5700|134,860.505680|3.391695|6.714807|19,664.004831 / —|6400|3.3755210238807845 / 2.963799766429140503387627174|
|78/mobile|2022-01-13→2022-01-14|5300→4200/4200|254,630.977468|3.821910|6.423814|19,500.428933 / —|12100|3.7120533313975996 / 3.259284335287634634016387313|
|113/mobile|2022-01-21→2022-01-24|5200→5100/5100|212,964.443891|3.721860|6.683658|19,087.008797 / —|100|3.553880661418941 / 3.120404405634801719785893253|
|122/mobile|2022-01-24→2022-01-25|4800→4700/4700|121,563.415982|4.00200|6.668394|19,204.073520 / —|5200|3.904117953737246 / 3.427922325927401819163579548|

3200是层68原intent的最大股数，真正提交的target就是100，实际也成交100；不是已下3200股只成交100。六笔均target=filled，实际before-reserve available按原audit现金事件逐项重建，并与全部726个原CLOSE available闭合。该现金是轮到该原reserve槽位时的余额，已反映此前其它原reserve，不是昨收现金，也没有借款。

## 原信号CLOSE与实际OPEN现金分列

|层|信号CLOSE NAV|信号CLOSE available|OPEN该笔reserve前available|原gross budget|原单笔CORE risk_budget|core_Q/mobile_Q|行业financial level|原slot→最终PVR slot / priority_rank|
|---|---:|---:|---:|---:|---:|---|---:|---|
|68|995,688.148106|98,284.768106|100,061.423240|8,804.370000|2,489.220370|True/True|1|26→6 / 92|
|69|980,931.856028|99,755.246028|152,659.061074|19,618.637121|—|True/True|1|17→0 / 0|
|75|983,200.241571|98,108.981571|134,860.505680|19,664.004831|—|True/True|1|10→0 / 5|
|78|975,021.446667|98,630.196667|254,630.977468|19,500.428933|—|True/True|1|4→0 / 10|
|113|954,350.439826|97,886.559826|212,964.443891|19,087.008797|—|True/True|1|1→1 / 22|
|122|960,203.675989|95,643.435989|121,563.415982|19,204.073520|—|True/True|1|1→1 / 17|

signal_CLOSE_available、OPEN_before_reserve_available来自不同时钟，不互相代替；mobile risk_budget原字段缺失记None，不填原CORE值。financial level是截至信号日最后一条原industry金融事件，不以未来期末level回填。原slot/最终PVR slot/priority_rank均保原字段，不把名次当预算。

## 每笔信号当时的原状态

|层|E0 / I / i_buy / grade|原G1 up_reasons|当日市场CP candidate|实际intent CP id|PVR排序分|行业stage|
|---|---|---|---:|---|---:|---|
|68|1/1/True/4.0|new_price_frontier_in_confirmed_up_structure|2.810155034450457|None：CORE未使用CP|86.73664520965536|confirmed|
|69|1/1/True/4.0|new_price_frontier_in_confirmed_up_structure|3.071411301898207|ea3c3f6f1a1f6b19053268b71212a5310615054843fb7277c22472f74b7a70b4|91.176721229945|confirmed|
|75|1/1/True/4.0|new_price_frontier_in_confirmed_up_structure|3.3755210238807845|cb4ee015605a8f1bc7718082b3728ba95743f2ebd6513afa852254b9ec875f6f|94.23125861750536|confirmed|
|78|1/1/True/4.0|new_price_frontier_in_confirmed_up_structure|3.7120533313975996|d92dbfe0c8423d3c6add2a10b01dacbfeb593a5fed8f86c33489426ffa68142a|95.98155345846149|confirmed|
|113|1/1/True/2.0|new_S21_up_confirmation|3.553880661418941|3f7cd620c648fe6c38d9a94f2b9efc74dc223a03d5b77ea941ee4e8125cea18f|84.77906806638596|confirmed|
|122|1/1/True/4.0|new_S63_up_confirmation|new_price_frontier_in_confirmed_up_structure|3.904117953737246|299b1a14b38ae6a6a838ed891abf78c0ad212862aae999f29b9524e00f9b748d|89.19234479341785|confirmed|

全部CP完整ID及canonical形成字段在SIX_SIGNAL_STATES.csv/ORIGINAL_SIX_LAYER_CHAIN.json。层68当天市场存在CP，但CORE intent CP1_id=None，实际初始线取原I；不能将市场CP标记写成CORE使用了CP。

PVR字段名称需分开：native_rank.py只新增`PVR_score/PVR_ready/priority_rank`并覆盖`rank`，保留原`score`；behavior_evidence.py把这个旧score明确称original_H1_score。成交字段名`pvr`承接旧intent score，和真正本轮PVR排序分不是同一字段。结构化文件同时保留PVR_priority_score、original_H1_intent_score、legacy_trade_field_named_pvr，不混为一个值。

## 六层实际退出part

|层|首次specific请求/原因|实际卖出|股数/价格|分摊卖费|net_cash|最终part reason|
|---|---|---|---:|---:|---:|---|
|68|2022-02-07 / I_structure_exit|2022-02-08|100 / 2.768615|0.356791|276.504709|I_structure_exit|
|69|2022-01-19 / CP1_add_protection|2022-01-20|6300 / 2.948525|23.938514|18,551.768986|CP1_add_protection|
|75|2022-01-19 / CP1_add_protection|2022-01-20|5700 / 2.948525|21.658656|16,784.933844|CP1_add_protection|
|78|2022-01-19 / CP1_add_protection|2022-01-20|4200 / 2.948525|15.959010|12,367.845990|CP1_add_protection|
|113|2022-01-27 / CP1_add_protection|2022-02-08|5100 / 2.768615|18.196362|14,101.740138|I_structure_exit|
|122|2022-01-27 / CP1_add_protection|2022-02-08|4700 / 2.768615|16.769197|12,995.721303|I_structure_exit|

原逻辑卖单只有两次真实fill：1/20共16200股，raw OPEN2.95、价2.948525、全单费61.5561795135；2/8共9900股，raw OPEN2.77、价2.768615、全单费35.32235008995。表中按原parts反算各层分摊费用，合计与全单费一致，没有每层重复最低佣金。

1/27 I仍on，首次卖单锁113/122是CP1_add_protection；2/7 Ioff才将CORE68并入已存在卖单。2/8所有parts最终reason写成I_structure_exit，不应倒填成1/27已经I退出。1/28与2/7未记录实际sell fill；所选原book/audit没有逐OPEN明确的窗口拒绝原因，保留“原pending/无实际fill，原因字段缺失”，不推断真实交易所跌停/停牌，也不假设未成交日可以成交。

## 源码入口与未保存字段

- [原planning/旧线检查→ratchet→新申请](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:213)：ACT/I优先退出，mobile先检查已有floor，未触才max原I/新CP；原CORE继续用I。
- [原opening](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/case-stage-ledger-20261031/v3/joint_v3.py:302)：先原退出和结算，再按rank/role顺序preview、route、reserve，之后检查执行窗口与fill。
- [真实known-OPEN reserve](/Users/bytedance/Documents/ChatGPT/money/research_rounds/lot-risk-allocation-20261029/code/study.py:94)：target=q、锁gross与费用，assert q<=intent.cap；audit分别保存target与frozen cap。
- [PVR排序字段绑定](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/native_rank.py:78)、[旧H1 score字段命名](/Users/bytedance/Documents/Codex/2026-10-29/task/research_rounds/pvr-slot1-native-readiness-20261101/behavior_evidence.py:36)、[trade.pvr=meta.score](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:71)：结构化保留两类分数。
- [原I事件/持有状态](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/policies_g1.py:20)、[原G1 fresh_up来源](/Users/bytedance/Documents/ChatGPT/money/research_rounds/b5-g1-20261025/code/grade.py:24)。
- [同股退出层合并](/Users/bytedance/Documents/ChatGPT/money/research_rounds/probe-pyramid-pilot-20261029/code/pilot.py:104)：后续请求会扩展已有单及reason，原created_at仍保留。

缺失：原账没有逐个被尝试股数的route/probe/sector/account约束完整评估日志，不能仅凭cap与target差异断言是哪一道门、也不能直接说现金不足。已保存的frozen intent、原reserve、funding、实际fill都原样保留。mobile原risk_budget字段不存在，记None，不能填入任何共享预算。

字段索引：ORIGINAL_SIX_LAYER_CHAIN.json是逐层完整原对象；SIX_BUYS.csv/SIX_SIGNAL_STATES.csv/SIX_LAYER_EXIT_PARTS.csv供对照；ORIGINAL_TWO_SELL_ORDERS.json保whole order+parts；ORIGINAL_DAILY_SOURCE_INDEX.json保1/10—2/8逐日原字段，已排除旧paper/v3字段。SOURCE_MANIFEST.json绑定原书、daily、源码和脚本。

## 逐日实际持仓与下一OPEN去向（追加原字段）

完整17日表：[ORIGINAL_DAILY_HOLDINGS.csv](ORIGINAL_DAILY_HOLDINGS.csv)，嵌套原层：[ORIGINAL_DAILY_HOLDINGS.json](ORIGINAL_DAILY_HOLDINGS.json)，逐层线对照：[ORIGINAL_DAILY_LAYER_FLOORS_LONG.csv](ORIGINAL_DAILY_LAYER_FLOORS_LONG.csv)。CORE有效线单独取last_core_line，原层floor也原样保留；旧线来自上一实际CLOSE或首填的冻结floor，raw仅除当日原factor。CORE字段是原I参考线，不把它冒称mobile CP检查。

|CLOSE|raw close|原股数|CP|原roles|下一OPEN|原下一OPEN结果|
|---|---:|---:|---|---|---|---|
|2022-01-10|2.74|0|True|['core', 'mobile']|2022-01-11|ACTUAL_NEXT_OPEN_RESERVED|
|2022-01-11|3.01|100|True|['mobile']|2022-01-12|ACTUAL_NEXT_OPEN_RESERVED|
|2022-01-12|3.31|6400|True|['mobile']|2022-01-13|ACTUAL_NEXT_OPEN_RESERVED|
|2022-01-13|3.64|12100|True|['mobile']|2022-01-14|ACTUAL_NEXT_OPEN_RESERVED|
|2022-01-14|3.78|16300|False|[]|2022-01-17|NO_INTENT_GENERATED_FROM_THIS_CLOSE|
|2022-01-17|3.59|16300|False|[]|2022-01-18|NO_INTENT_GENERATED_FROM_THIS_CLOSE|
|2022-01-18|3.28|16300|False|[]|2022-01-19|NO_INTENT_GENERATED_FROM_THIS_CLOSE|
|2022-01-19|2.99|16300|False|[]|2022-01-20|NO_INTENT_GENERATED_FROM_THIS_CLOSE|
|2022-01-20|3.29|100|True|['mobile']|2022-01-21|ACTUAL_NEXT_OPEN_REJECTED: cash_or_original_reserve,sector_capital|
|2022-01-21|3.62|100|True|['mobile']|2022-01-24|ACTUAL_NEXT_OPEN_RESERVED|
|2022-01-24|3.98|5200|True|['mobile']|2022-01-25|ACTUAL_NEXT_OPEN_RESERVED|
|2022-01-25|4.38|9900|True|['mobile']|2022-01-26|ACTUAL_NEXT_OPEN_REJECTED: industry_invalidated|
|2022-01-26|3.94|9900|False|[]|2022-01-27|NO_INTENT_GENERATED_FROM_THIS_CLOSE|
|2022-01-27|3.55|9900|False|[]|2022-01-28|NO_INTENT_GENERATED_FROM_THIS_CLOSE|
|2022-01-28|3.2|9900|False|[]|2022-02-07|NO_INTENT_GENERATED_FROM_THIS_CLOSE|
|2022-02-07|2.88|9900|False|[]|2022-02-08|NO_INTENT_GENERATED_FROM_THIS_CLOSE|
|2022-02-08|3.17|0|False|[]|2022-02-09|NO_INTENT_GENERATED_FROM_THIS_CLOSE|

1/20 CLOSE的mobile intent原cap5900，下一1/21 OPEN记录cash_or_original_reserve,sector_capital；1/25 CLOSE原cap4200，下一1/26 OPEN记录industry_invalidated。它们不是六笔实际成交之一。1/14 CLOSE原held=True、i_buy=True、CP=False、roles=[]、barriers=[]，原未生成新单，不是funding拒绝。1/10上午funding对应前一个native CLOSE（1/7），不能归到1/10晚上的CORE申请；链接依据与原preceding-clock字段已分列。

六笔roles/held/barriers、真实pool与reserved原记录见SIX_OPPORTUNITIES_POOLS_RESERVED.json/csv。CORE68真实reserve池为probe；五mobile为confirmed。reserved来自原opening成功分支，不代表route函数直接return字符串；精确静态代码见NO60_ACTIVE_ROUTE_SOURCE.txt及ROUTE_RESERVED_SOURCE_REFERENCE.json。没有重新调用route或求任何股数。
