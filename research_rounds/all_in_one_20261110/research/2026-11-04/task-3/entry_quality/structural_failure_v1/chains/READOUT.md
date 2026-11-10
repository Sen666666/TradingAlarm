# 原No60完整交易链：先有时钟和分母，再谈机制

状态：完成10条主链和3条附加赢家/回吐对照的只读取证；未建新账户，未提出已获证据支持的新交易规则。

取样固定为完整cycle终局净亏前5、Dec阶段财富最差旧周期、Dec新周期最差、10月8日后阶段最差旧周期、ACT受影响净亏最差、完整周期正贡献最大。附加上海电影、海能达、众生药业3个事先指定的真实赢家。结果只能描述这些链，不能当随机样本。主链36层，7个终局负周期合计 -48,071.12，仅占原1677周期毛负的 4.1747%；不由10个故事外推全账户修复。

完整JSON保留每个账户CLOSE的原量价（调整与原始坐标同时保存）、E0事件/确认pivot、I状态/floor/当日买事件、G1理由、source segment、CP canonical receipt/形成区间/新前沿ID/冻结scale/初始保护线、行业attempt/stage/授权、PVR/排序、真实CORE库存、含费remaining basis/浮盈、原intent/funding、实际退出part及请求/成交时间。prior保护线与post-CLOSE ratchet分开标示；无当日报价时保留实际source_day，不把前值冒充当日新证据。

## 可执行诊断的边界

T仅取该股实际首次fill之后、真实flat之前首次原events.parquet.event=-1，CLOSE以后才已知；负事件不等于原E0_target失效。A仅隔离T时既有库存：原控制也不再加入T后新合同，比较下一原合法OPEN退出与原库存原退出；必须按层扣除已锁ACT/I/CP，T+1、容量、停牌、权息可卖日、原pending与原费用不得放松。B仅看严格晚于T决策的原mobile合同拒绝范围，T前及T同日已funded/filled/pending不删除。两者是局部原股数/预算边界，不是账户增益；原full-flat只作事后评价截止，不能当新规则当时的reset。精算与不兼容项由 sibling executable_bounds 另行落盘，不把后验净额直接当少亏。

尤其B从首次负事件持续到原周期终了，比“-1暂停、下一+1恢复”更宽。盈新01-20已+1，01-21/24大亏追加会被精确恢复规则放行；不得拿宽B覆盖替该候选背书。

## 主链与对照

|类别|股票 / 原周期|层 / CORE-mobile|全周期净额|首负事件T|T时已持浮盈|T后原mobile合同|
|---|---|---|---:|---|---:|---:|
|主|盈新发展 000620.SZ 2022-01-11→2022-02-08|6 / 1-5|-17,850.15|2022-01-17|3,392.58|2|
|主|秦港股份 601326.SH 2023-05-08→2023-05-11|3 / 0-3|-6,133.10|2023-05-10|-3,809.53|0|
|主|银之杰 300085.SZ 2024-10-10→2024-10-11|1 / 0-1|-5,920.08|2024-10-10|-3,640.44|0|
|主|佛燃能源 002911.SZ 2022-07-26→2022-09-19|4 / 1-3|-5,033.25|2022-08-03|792.74|0|
|主|北方国际 000065.SZ 2023-03-16→2023-03-23|4 / 0-4|-4,871.20|2023-03-21|-1,902.21|0|
|主|供销大集 000564.SZ 2022-11-11→2022-12-16|7 / 1-6|4,478.32|2022-12-09|16,037.05|0|
|主|深深房Ａ 000029.SZ 2022-12-02→2022-12-08|3 / 0-3|-4,180.25|2022-12-06|-61.81|0|
|主|XD中国太 601601.SH 2024-09-02→2024-10-10|3 / 0-3|7,600.88|2024-09-09|-139.63|1|
|主|粤 传 媒 002181.SZ 2024-12-19→2024-12-25|1 / 0-1|-4,083.10|2024-12-24|-3,574.42|0|
|主|曙光数创 920808.BJ 2023-04-14→2023-05-08|4 / 0-4|75,440.87|2023-05-05|77,579.02|0|
|附对照|上海电影 601595.SH 2023-03-13→2023-05-15|9 / 1-8|48,847.91|2023-04-13|54,342.17|3|
|附对照|海能达 002583.SZ 2024-10-15→2024-11-27|3 / 1-2|21,949.16|2024-11-04|22,127.15|0|
|附对照|众生药业 002317.SZ 2022-10-14→2022-12-02|4 / 1-3|28,947.77|2022-10-25|3,781.31|1|

### 1. 盈新发展 000620.SZ — full_stock_cycle_endpoint_net_rank_1

首个负事件01-17时已有库存仍浮盈3392.58；01-19 CP请求卖首三mobile，01-20执行。随后新正向event也在01-20成立，01-21新S21、01-24新S63上确认支持了两次追加；它们最后合计亏10706.78。因而“-1暂停、+1恢复”不会挡这两笔。首仓CORE实付306.18，后续五mobile累计92622.48，是授权规模与连续尝试的具体样本；赢家也会如此扩张，不能由本例就设CORE比例或高点门。01-27 I卖单至02-08才真实成交，不能假设01-28任意全售。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|68 core/first|2022-01-10→2022-01-11|无|3.1206 / 2.2551|306.18|0.00|new_price_frontier_in_confirmed_up_structure|confirmed / 86.74|
|69 mobile/add|2022-01-11→2022-01-12|68|3.4281 / 3.0714|19,420.42|-5.18|new_price_frontier_in_confirmed_up_structure|confirmed / 91.18|
|75 mobile/add|2022-01-12→2022-01-13|68|3.7698 / 3.3755|19,339.38|1,457.40|new_price_frontier_in_confirmed_up_structure|confirmed / 94.23|
|78 mobile/add|2022-01-13→2022-01-14|68|4.1457 / 3.7121|16,058.45|4,978.02|new_price_frontier_in_confirmed_up_structure|confirmed / 95.98|
|113 mobile/add|2022-01-21→2022-01-24|68|4.1229 / 3.5539|18,988.17|55.82|new_S21_up_confirmation|confirmed / 84.78|
|122 mobile/add|2022-01-24→2022-01-25|68|4.5329 / 3.9041|18,816.07|1,401.65|new_S63_up_confirmation; new_price_frontier_in_confirmed_up_structure|confirmed / 89.19|

### 2. 秦港股份 601326.SH — full_stock_cycle_endpoint_net_rank_2

05-10首负事件与原三层CP卖单同CLOSE，05-11全售；没有事件后追加。前三个上涨确认与PVR升序发生在实际早期亏损之前，不能用事后CP reason证明信号无效。该链展示已进入仓位后的快速反转，负事件触发以后再加一退出器没有新增提前量。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|1305 mobile/reentry|2023-05-05→2023-05-08|无|4.6069 / 4.3946|17,935.37|0.00|new_price_frontier_in_confirmed_up_structure|expanded / 89.89|
|1314 mobile/add|2023-05-08→2023-05-09|无|5.0710 / 4.8373|5,431.14|-15.37|new_price_frontier_in_confirmed_up_structure|expanded / 92.80|
|1318 mobile/add|2023-05-09→2023-05-10|无|5.3313 / 5.0856|17,331.02|654.49|new_price_frontier_in_confirmed_up_structure|expanded / 94.93|

### 3. 银之杰 300085.SZ — full_stock_cycle_endpoint_net_rank_3

10-09授权、10-10 OPEN重入，10-10 CLOSE首负事件已同时触发原CP，10-11卖出。单mobile累计亏5920.08，首个可观察负事件不能倒填10-10 OPEN阻止成交；从当日收盘亏3640.44到最终亏损还含下一OPEN缺口及成本。把“事件后退出”写成能规避全额损失是错误时钟。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|1963 mobile/reentry|2024-10-09→2024-10-10|无|249.1159 / 216.5166|14,968.44|0.00|new_price_frontier_in_confirmed_up_structure|expanded / 98.28|

### 4. 佛燃能源 002911.SZ — full_stock_cycle_endpoint_net_rank_4

CORE先实际出资、三次mobile随后加仓；08-03首负事件同时原mobile CP已锁，08-04卖mobile。CORE直到09-16 I请求、09-19卖，CORE终局+121.28；不能把mobile保护失败与CORE I持有期统一归因，也不能因延长持有就称退出过晚。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|532 core/first|2022-07-25→2022-07-26|无|24.5508 / 17.7409|6,263.62|0.00|new_price_frontier_in_confirmed_up_structure|expanded / 90.79|
|543 mobile/add|2022-07-26→2022-07-27|532|27.0039 / 25.6311|15,013.68|616.38|new_price_frontier_in_confirmed_up_structure|expanded / 93.77|
|546 mobile/add|2022-07-28→2022-07-29|532|32.6755 / 31.0090|15,764.12|3,697.70|new_price_frontier_in_confirmed_up_structure|expanded / 97.04|
|548 mobile/add|2022-07-29→2022-08-01|532|34.3436 / 32.5920|15,295.84|4,958.58|new_price_frontier_in_confirmed_up_structure|expanded / 97.86|

### 5. 北方国际 000065.SZ — full_stock_cycle_endpoint_net_rank_5

03-21首负事件比03-22原CP请求早一个CLOSE，触发当时库存已亏1902.21，不能将该下跌算作可避免。四mobile已全部买完，没有后续可冻结新增；仅A原库存局部界限有范围，必须用03-22真实可成交OPEN、原费用/股数验证。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|1131 mobile/reentry|2023-03-15→2023-03-16|无|60.1021 / 55.7383|4,552.63|0.00|new_price_frontier_in_confirmed_up_structure|expanded / 92.12|
|1134 mobile/add|2023-03-16→2023-03-17|无|66.0997 / 61.3005|13,292.69|175.37|new_price_frontier_in_confirmed_up_structure|expanded / 94.89|
|1140 mobile/add|2023-03-17→2023-03-20|无|72.7265 / 66.9095|13,088.57|1,228.68|new_price_frontier_in_confirmed_up_structure|expanded / 96.58|
|1143 mobile/add|2023-03-20→2023-03-21|无|75.7463 / 69.6877|12,668.32|1,574.12|new_price_frontier_in_confirmed_up_structure|expanded / 97.48|

### 6. 供销大集 000564.SZ — worst_Dec2022_stage_wealth_in_complete_cycle

Nov30真实旧库存已知浮盈24524.05，Dec没有新买；Dec财富−20045.73，但该完整周期最终仍+4478.32。12-09首负事件时旧库存仍浮盈16037.05。此为已经成功趋势的利润回落，非连续首次失败；减少它不是天然研究目标。12-12 CP请求到12-14才成交，12-15 I到12-16，不能用事后峰值或请求日价格估算。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|816 core/reentry|2022-11-10→2022-11-11|无|1.3183 / 0.9372|139.08|0.00|new_price_frontier_in_confirmed_up_structure|probe / 87.36|
|817 mobile/add|2022-11-11→2022-11-14|816|1.3801 / 1.2932|14,776.54|-5.08|new_price_frontier_in_confirmed_up_structure|confirmed / 91.34|
|826 mobile/add|2022-11-18→2022-11-21|816|1.6376 / 1.5316|1,777.02|2,892.38|new_price_frontier_in_confirmed_up_structure|confirmed / 93.20|
|827 mobile/add|2022-11-21→2022-11-22|816|1.7200 / 1.6076|180.10|3,848.35|new_price_frontier_in_confirmed_up_structure|confirmed / 94.96|
|828 mobile/add|2022-11-22→2022-11-23|816|1.8024 / 1.6834|15,143.76|4,827.25|new_price_frontier_in_confirmed_up_structure|confirmed / 96.58|
|836 mobile/add|2022-11-23→2022-11-24|816|1.8951 / 1.7700|15,160.77|7,175.50|new_price_frontier_in_confirmed_up_structure|confirmed / 97.59|
|845 mobile/add|2022-11-24→2022-11-25|816|1.9878 / 1.8566|15,013.68|9,564.73|new_price_frontier_in_confirmed_up_structure|confirmed / 97.88|

### 7. 深深房Ａ 000029.SZ — worst_Dec2022_new_cycle_endpoint_net

Dec新重入后两个add全部在12-06首负事件前完成；首负时已亏61.81，12-07 CP、12-08卖。B后续风险冻结覆盖0，A仅可能提前一OPEN；本例不能支持普遍给首次缩量，也不能说缺CORE就是错误，曙光同样无CORE。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|868 mobile/reentry|2022-12-01→2022-12-02|无|13.5831 / 12.2064|14,632.46|0.00|new_price_frontier_in_confirmed_up_structure|expanded / 85.51|
|875 mobile/add|2022-12-02→2022-12-05|无|14.6149 / 13.1336|14,786.55|481.54|new_price_frontier_in_confirmed_up_structure|expanded / 90.09|
|880 mobile/add|2022-12-05→2022-12-06|无|15.7956 / 14.1000|1,393.80|3,250.99|new_price_frontier_in_confirmed_up_structure|expanded / 93.62|

### 8. XD中国太 601601.SH — worst_afterOct8_old_cycle_stage_wealth

10-08后阶段财富−4951.62，但完整周期+7600.88。09-09首负事件以后、09-23新正事件之前，09-18真实追加layer1931最终+2481.60；它是负leg冻结新增的直接赢家机会代价。三个mobile最终同10-09 CP→10-10退出。正常回吐与入场失败需分开。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|1904 mobile/reentry|2024-08-30→2024-09-02|无|43.1166 / 40.9203|11,871.69|0.00|new_E0_price_volume_up_event; new_S21_up_confirmation|confirmed / 58.03|
|1914 mobile/add|2024-09-06→2024-09-09|无|45.0804 / 42.7140|12,315.94|524.31|new_price_frontier_in_confirmed_up_structure|expanded / 76.58|
|1931 mobile/add|2024-09-18→2024-09-19|无|44.2949 / 41.9215|12,171.86|172.37|无当日新G1来源|expanded / 60.40|

### 9. 粤 传 媒 002181.SZ — worst_ACT_affected_cycle_endpoint_net

12-23已由ACT请求退出，首负event12-24在后、12-25才执行。任何原库存新退出不得篡改已锁ACT clock或把未成交日当自由次OPEN；A新增贡献0。没有后续mobile可拒，故负event控制没有这笔新增覆盖。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|2241 mobile/reentry|2024-12-18→2024-12-19|无|16.1079 / 13.6449|13,168.42|0.00|new_price_frontier_in_confirmed_up_structure|expanded / 91.65|

### 10. 曙光数创 920808.BJ — largest_positive_complete_cycle_control

全周期正贡献最大，四mobile、无CORE，逐次上行新前沿与PVR提升与多个亏损例共享；不能按这些来源剔除。05-05首负事件与原CP同CLOSE，05-08退出，原净+75440.87。不存在可由同一负事件提供的提前退出增量。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|1233 mobile/first|2023-04-13→2023-04-14|无|46.8600 / 42.4573|15,339.01|0.00|new_price_frontier_in_confirmed_up_structure|expanded / 80.63|
|1245 mobile/add|2023-04-17→2023-04-18|无|53.0000 / 47.7128|15,382.56|2,309.99|new_price_frontier_in_confirmed_up_structure|expanded / 86.89|
|1253 mobile/add|2023-04-19→2023-04-20|无|59.9700 / 53.7271|12,169.70|5,740.19|new_price_frontier_in_confirmed_up_structure|expanded / 93.14|
|1254 mobile/add|2023-04-20→2023-04-21|无|75.0600 / 66.8379|16,005.71|17,456.97|new_price_frontier_in_confirmed_up_structure|expanded / 95.37|

### 11. 上海电影 601595.SH — 2023_repair_multilayer_winner

原CORE+连续mobile扩张形成全周期+48847.91。04-13首负事件时已有mobile CP锁，CORE仍合法；后续三add净−3143.66，但CORE与前期扩张贡献巨大。不能删掉最终坏add后将释放资金当作可获得账户增益，也不能把整个赢家的回吐当初始失败。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|1115 core/reentry|2023-03-10→2023-03-13|无|16.5931 / 12.6903|6,258.62|0.00|new_price_frontier_in_confirmed_up_structure|probe / 89.21|
|1149 mobile/add|2023-03-20→2023-03-21|1115|18.2549 / 17.0521|12,891.45|991.38|new_price_frontier_in_confirmed_up_structure|confirmed / 87.32|
|1155 mobile/add|2023-03-21→2023-03-22|1115|18.9221 / 17.6947|13,737.94|1,891.93|new_price_frontier_in_confirmed_up_structure|confirmed / 91.47|
|1159 mobile/add|2023-03-22→2023-03-23|1115|20.8106 / 19.4606|12,892.45|5,130.99|new_price_frontier_in_confirmed_up_structure|expanded / 94.30|
|1168 mobile/add|2023-03-23→2023-03-24|1115|22.3465 / 20.8969|3,557.05|9,244.53|new_price_frontier_in_confirmed_up_structure|expanded / 95.83|
|1174 mobile/add|2023-03-27→2023-03-28|1115|23.9076 / 22.3567|9,180.31|13,329.48|new_price_frontier_in_confirmed_up_structure|expanded / 95.26|
|1255 mobile/add|2023-04-20→2023-04-21|1115|41.2938 / 38.3915|9,538.51|10,141.38|new_S63_up_confirmation; new_price_frontier_in_confirmed_up_structure|expanded / 90.23|
|1277 mobile/add|2023-04-25→2023-04-26|1115|45.4232 / 42.2306|7,129.12|13,066.87|new_price_frontier_in_confirmed_up_structure|expanded / 88.55|
|1278 mobile/add|2023-04-26→2023-04-27|1115|48.0292 / 44.0156|15,233.81|15,223.75|new_price_frontier_in_confirmed_up_structure|expanded / 90.92|

### 12. 海能达 002583.SZ — postOct8_fresh_start_winner

2024-10-14首次CORE后两次mobile扩张，全周期+21949.16；与银之杰同属震荡后的新上行机会却结果相反。11-04负event已同mobile CP，CORE原I维持至11-26请求；尾部不能靠“所有首仓等待”保护而无代价。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|1994 core/first|2024-10-14→2024-10-15|无|49.2306 / 42.5991|895.50|0.00|new_price_frontier_in_confirmed_up_structure|probe / 93.75|
|2017 mobile/add|2024-10-18→2024-10-21|1994|67.1582 / 59.1487|13,212.45|299.50|new_price_frontier_in_confirmed_up_structure|confirmed / 97.68|
|2039 mobile/add|2024-10-21→2024-10-22|1994|73.9021 / 63.6741|14,012.90|1,672.05|new_price_frontier_in_confirmed_up_structure|expanded / 98.06|

### 13. 众生药业 002317.SZ — Dec2022_old_profitable_giveback_control

10-25首负event时前三原层尚在，最终合计+27687.65；10-27新+1后第四mobile最终+1260.12。首负就全退会伤真实趋势延续，宽B“首次负之后直到原flat不再买”也误拒该赢家。Nov30旧浮盈38681.18、Dec回落9733.41仍终局+28947.77，不能以Dec终局回吐标签反推过早/过晚。

|层 / 动作|决策→实买|CORE已出资持有|决策C / 冻结floor（同调整坐标）|本次实际买款|当时原库存浮盈|G1当日新增理由|行业 / PVR|
|---|---|---|---:|---:|---:|---|---|
|714 core/reentry|2022-10-13→2022-10-14|无|70.5629 / 55.9814|2,988.73|0.00|new_price_frontier_in_confirmed_up_structure|probe / 84.38|
|722 mobile/add|2022-10-14→2022-10-17|714|70.9379 / 63.7022|13,521.82|37.27|new_price_frontier_in_confirmed_up_structure|confirmed / 83.61|
|776 mobile/add|2022-10-20→2022-10-21|714|83.9253 / 74.9299|10,631.15|3,179.46|new_price_frontier_in_confirmed_up_structure|expanded / 92.61|
|792 mobile/add|2022-10-27→2022-10-28|714|92.7398 / 85.2849|1,965.13|6,484.31|new_E0_price_volume_up_event; new_price_frontier_in_confirmed_up_structure|expanded / 89.30|

## 算法裁决

这批原链支持“相同上行确认、行业扩张和连续CP授权既出现在严重失败，也出现在稀疏大赢家”。没有发现重复消费同一个receipt或用新ID伪装无新证据的直接执行错误；每个原mobile的canonical新前沿/receipt可逐项追溯。行业授权持续本来就是预算存续，不能因未新发行业receipt便宣称无效。CORE存在与否也不能直接识别质量：若干最差周期无CORE，而最大正周期曙光同样无CORE。

事件早退最多在北方/深房等提供一个CLOSE的局部提前量；秦港/银之杰已与CP重叠，粤传媒已ACT锁。供销/众生/太保的阶段大亏主要包含此前真实已知浮盈回落，减少回吐不是自动正确的目标。需要等局部真实执行价验证才能说早一OPEN是否少亏，更不能说峰值可回收。

当前不应由这些案例新建“首仓缩量、旧高等待、CORE出资比例、负事件全退、首次负事件后不再买”规则。原量价负leg与持续I授权的分歧是可证伪诊断方向，必须使用全3436原实际动作、固定原83/94尾、真实强窗新启动的前向时钟覆盖验证；负事件后再出现原+1时要按真实恢复逐笔计，不能把宽上限当精确候选。若大额坏合同在原+1之后、或主损失已在首负前/已锁退出，冻结新增不能解决该失效点；若大量赢家扩张也处在同负leg，停止而不加冷却/高点/额外阈值硬救。

本交付结论为 NO_NEW_MECHANISM_PROMOTED；静态局部边界并不改变这个判定。原当前存续池、当前行业快照、OHLCV下一OPEN代理和真实竞价成交的差异沿原限制保留。
