# 2022 动态 A+B：baseline 与 freshUP 优先

**结论：fresh 优先在本次条件样本中小幅改善初仓入场时点和右尾，但没有明显提高整轮胜率，也未使净额转正。不能据此宣称完整策略有效或无效。**

只运行两条独立 FULL 动态消费者。市场信号、尺寸、费用、退出/追加、行业每日两槽均冻结；唯一差异为已知可行位置的 freshUP 优先。UNKNOWN relative 保留原可行位置，nonUP 不过滤。core 是各自 FULL 新回合的初始股数/入退场日/权益与独立 dated 买卖费诊断，不运行第三条动态策略。

## 主结果：当前封存输入下的条件执行

| 指标 | baseline | freshUP 优先 |
|---|---:|---:|
| 新许可 admitted | 2732 | 2735 |
| 实际条件入场 filled | 2725 | 2728 |
| 闭合 | 2627 | 2623 |
| 执行 UNKNOWN | 103 | 110 |
| CENSORED / NOFILL | 0 / 2 | 0 / 2 |
| 初仓胜数 / 闭合数 | 837 / 2627 | 840 / 2623 |
| 初仓条件胜率 | 31.8614% | 32.0244% |
| 初仓逐股净额合计（CNY） | -519206.62 | -504034.18 |
| 整轮胜数 / 闭合数 | 777 / 2627 | 776 / 2623 |
| 整轮条件胜率 | 29.5775% | 29.5844% |
| 整轮逐股净额合计（CNY） | -650787.37 | -634127.14 |
| 初仓 ≥50% 尾部 | 44 | 47 |
| 整轮 ≥50% 尾部 | 41 | 44 |

初仓净额差 +15172.43，整轮 +16660.23；初仓胜率 +0.1630 个百分点，整轮仅 +0.0070 个百分点。这些加总不是共享账户收益，交易数、资金占用和未知覆盖不相等，不能当成账户增益估计。

## 财务证据与共同分母

- 闭合但源覆盖不足为 11 / 10。证据可用闭合为 2616 / 2613，仍只表示既有本地非空来源的区间无行动证据或已审 NET80 行动情景，不是完整发行人权益/PIT认证。
- 证据可用初仓：834/2616=31.8807%，净额 -520189.70；837/2613=32.0321%，净额 -500939.03。
- 证据可用整轮：774/2616=29.5872%，净额 -651087.03；773/2613=29.5829%，净额 -630198.19。剔除覆盖不足后，整轮胜率差方向微幅反转，说明不能把极小百分点当稳健结论。
- 共同原市场 event：2553；共同闭合2454；双方证据可用共同闭合2445。全部2553个共同事件的入场、动作、claims、终态和收益一致。差额来自179个baseline独有与182个fresh独有事件，不来自共同行为漂移或旧回合股息串账。
- UNKNOWN 从103升至110，主要是未准入后续factor事件65→73，持有缺OPEN33→32；两臂均另有入场factor1与缺次OPEN4。UNKNOWN没有当作亏损或零收益。

## 新账本机制

- 仅按新账本同股、同实际退出日建立81个唯一配对。fresh更早35组：初仓差 +92071.99，整轮 +99821.04；更晚46组：初仓差 -61789.00，整轮 -66828.68。其余不同退出/不成对路径初仓合计差 -15110.55。提前改善与延后损伤并存。
- 其中601399.SH国机重装的新5月30日路径覆盖不足；证据可用早入配对仅34组，初仓差 +88162.39。不能把该不足路径的 +3909.60 混入证据可用机制。
- 182个新独有事件中，114个属于旧臂当天PASS_NOT_TOP2、fresh已知UP直接提升：106闭合，初仓39胜，净额 -4912.91；其余68个为状态链或其他槽位变化，63闭合。不能只展示三个新增赢家。
- 新增初仓≥50%尾部为金盘科技、爱旭股份、一品红。金盘fresh 6月2日入、baseline 6月21日入，同9月1日退出；爱旭fresh 5月5日入、baseline 7月7日入，同9月16日退出；一品红fresh 10月18日入、baseline 12月13日入，同2023年3月24日退出。
- 金盘、爱旭为当日fresh直接提升；一品红10月17日relative_event=0、可行rank仍2，为状态链间接获席。三只baseline均有其他时点持有，不是完全错过这些股票。
- baseline原初仓44个、整轮41个≥50%尾全部同event保留，无“旧尾消失但同股持有”误读。

## 回归与独立审查

- bridge-off：2022原两臂 ROUNDS/ACTIONS/DECISIONS/RANKING_AUDIT/END_STATES逐列对齐。
- 固定原2432许可：FULL 687/2345、86 UNKNOWN、1 NOFILL，保留11条原非strict条件路径；CORE回归737/2334、97 UNKNOWN、1 NOFILL。737仅为固定许可回归，不是本次动态目标。
- 426已审held现金事件两仓模式动作、真实登记Q、金额对齐；entry10共29个动作对齐。
- 4月29日实际输入截断：baseline消费者2885决策、1447动作、现金前缀相同。此为冻结信号输入的消费者前缀，不是重算上游信号或两臂全期截断。
- 微型边界：Q0 pending桥、应收/派息幂等、退出/UNKNOWN后claim、重入隔离、多事件、终点未付、strict zero gate、双保护转换；合成native sell_all释放后同日新edge可行，exitpending不释放，NOFILL不回填。
- 财务独审PASS：5467账本、829 claims、2553共同事件、5250闭合初仓与5229可用+21不足覆盖全部重算一致。
- 队列独审PASS：25834逐条state、5000队列、160 UNKNOWN可行槽、5453入场和14未确认的next共同OPEN、天华4月12日退出及4月29日slot2均一致。
- 实际顺序为小型合成单元→bridge-off→固定许可→一次动态两臂→有界前缀/边界复核。后两项在动态完成后通过；没有重新运行或调参动态实验。

## 使用限制

NET80是统一80%历史现金情景，不是真实个人税或到账时点；静态股票池/行业与source坐标为NON-PIT，历史实际可成交仍UNKNOWN。只准入402+24+10的436条有限经济事实，其他事件不因同股曾审核而放行。源覆盖不足不能仅剔除若干PnL后宣称整个动态队列完全认证。未扩展2024、原快入口、2026新生窗、共享资金账户或任何参数扫描。

## 文件和复跑

主表：report/PERFORMANCE.csv。逐回合：report/CORE_AND_FULL_ROUNDS.csv。覆盖：report/FINANCIAL_COVERAGE.csv。新旧独有与配对：report/NEW_LOST_ATTRIBUTION.csv、SAME_STOCK_EXIT_PAIRS.csv、TIMING_MECHANISM.csv、FRESH_ONLY_MECHANISM_DETAIL.csv。尾部：BASELINE_TAILS.csv、NEW_TAIL_SAME_STOCK_INTERVALS.csv。完整动态动作/队列/登记/claims：dynamic/。

解释器：/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python，使用 PYTHONDONTWRITEBYTECODE=1 和 -B。

已有阶段拒绝覆盖。若明确授权复跑，将 engine.py、run.py、report.py、prefix_check.py、boundary_check.py、mechanism.py 复制到本目录同级的新目录，保持父目录R不变，然后执行：

```sh
export PYTHONDONTWRITEBYTECODE=1
PY=/Users/bytedance/Documents/ChatGPT/money/TradingAlarm/research/.venv/bin/python
$PY -B run.py units
$PY -B run.py bridge_off
$PY -B run.py fixed
$PY -B run.py dynamic
$PY -B prefix_check.py
$PY -B boundary_check.py
$PY -B report.py
$PY -B mechanism.py
```

不要在原结果目录删除RUN_ONCE或覆盖数据；一次动态的engine/driver哈希保存在DYNAMIC_RUN_ONCE.json。最早bridge-off失败为旧跨窗全NaN审计列的schema比较问题，失败log留存；仅对expected全空缺列补NaN，实际值比较未放宽。

## 初仓净额范围补表（仅已审账本汇总）

report/CORE_PNL_SCOPE.csv 新增8行：两臂分别列条件闭合/证据可用闭合，再区分全持有期闭合与退出日不晚于2022-12-31的子集，提供总/均净额、胜负数（亏损组含零，另列严格负数与零）、盈利总额、亏损总额及两组均额。grossloss与meanloss为带负号金额；总额=盈利总额+带符号亏损总额。没有重算经济路径。

条件口径年内已平仓：baseline 2293回合，总净额-1275689.65元、均净额-556.34元，607胜/1686负（含零）；fresh 2293回合，总净额-1247458.99元、均净额-544.03元，611胜/1682负（含零）。这是“年内已平仓，不是年度账户收益/MTM”，未含2022年末未平仓市值或之后闭合收益，也不补猜UNKNOWN。

完整非闭合范围不变：baseline 103 UNKNOWN（98已确认入场、5未确认）+2 NOFILL；fresh 110 UNKNOWN（105已确认入场、5未确认）+2 NOFILL；均0 CENSORED。两臂各7个无确认入场=5 UNKNOWN+2 NOFILL。完整非闭合共105/112，未当亏损或零净额；年内子集也没有删除这些原总体范围，小表每行保留其完整计数。初仓全持有期与年内已平仓分母不得互换。

fresh排序实验至此封存停止，不继续调比例或再运行排序。
