# 两段五观察收盘低点改善L：完整原候选导出

`L_FEATURES.parquet`严格保留原PRIMARY的133713行/原candidate_index顺序及1660个sid；没有按实际获资、原利润、PVR是否ready或L结果删行。L=recent5_close_min/prior5_close_min−1；主线可显式rename为`low_improvement`，本文件保留原列`L`。

原PVR clock由既有`feature_design/features.py::original_observation_clock`直接提供：close及amount均正有限，原可选正/负mask原样，invalid/源段变化重启。只调用原exporter的`read_signal`读取并核SHA，未调用exporter.execute、compute_features或original_pvr。因子和金额口径不另改，没有未来pivot、asof或ffill。

每个可比block内，最近五个有效观察为t−4…t（含当日收盘），此前五个为t−9…t−5。这里的low是**收盘最小值**，不是OHLC的L，也不是已确认结构低点。相同最小值的日期取窗口内最早日；两组完整五个日期与close数值同时导出，故无隐含事后拐点选择。

结果：KNOWN133706；仅7行原block不足10观察而保NaN，未补0。其中2022—24为79889 known/3 warm，strong为53817/4 warm。具体7行见`EVIDENCE_CHECK.json`。源错误0。

四个原clock字段在133713候选上与原`features.parquet`逐行比较：valid、block、block_observation、segment均0差异。一个真实截断前缀检查：300058.SZ在2022-01-04截断为2077行，与3237行全源计算的全部共同列/行exact，未重算PVR。所有133706个known行再用导出的五+五close证据核算L exact；日期均有序、两窗不重叠，最近窗末日恰为decision day，0未来日期。

早Jan例：000028.SZ在2022-01-04的前窗为2021-12-21/22/23/24/27，收盘min37.081107961764985（12/23）；后窗12/28/29/30/31及1/4，min38.01538435697888（12/30）；L=0.02519548218940071。预2022历史没有丢失，未从reference_quotes的2022起点重暖。

schema含sid/day/window/decision_at/candidate_index、L/L_status、两窗low与最早min日期、十个close/日期证据、current_close_signal和原mask/block/source字段。原候选不含源行时会留NO_EXACT，源读取异常会留SOURCE_ERROR；本次没有这两类。L>0仅是两滚动五观察收盘min的相对改善，不证明HH/HL趋势或独立预测力。

输出SHA256：`807ab77070e5e3b820cd76bfc05e7af27ee2726eb14d52ec60c2e15d8bd10f2b`。RUN_RECEIPT绑定所有原输入与代码；PREFIX_CHECK、SMALL_EXAMPLES、EVIDENCE_CHECK提供定位证据。只有纯feature导出，0 PVR重算、0排序规则、0账户。
